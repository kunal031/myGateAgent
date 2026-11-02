"""A second model to fall back to when Gemini's free quota runs out.

A free Gemini key returns 429 RESOURCE_EXHAUSTED once the daily budget is
spent, and 429 is deliberately **not** in the retry list -- retrying a
quota error just spends the next day's budget to fail again. Before this,
that meant the assistant and card generation simply stopped until the
quota reset.

Written against the OpenAI chat-completions shape rather than a vendor
SDK, because Groq, Mistral, Together and OpenRouter all speak it. Swapping
provider is then a base URL and a model name in `.env`, not a code change
or another dependency -- and `httpx` is already pinned.

**Structured output is the part that matters.** Six call sites ask for
JSON, one with a Pydantic schema, and a fallback that returns prose where
the caller expects JSON fails later and less obviously than one that
returns nothing. So a requested schema is forwarded as `json_schema` when
the provider supports it and degraded to `json_object` plus an instruction
otherwise. Groq's strict mode guarantees adherence on gpt-oss and qwen3.8;
elsewhere it is best effort, which is still better than prose.

This is a safety net, not a second primary. The models differ in quality,
so the answer a student gets during a quota outage may be weaker -- which
is why `fallback_used` is returned and surfaced rather than hidden.
"""

import json
import logging
from typing import Any

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

#: Providers whose JSON-schema mode is known to work. Others still get
#: json_object, which constrains the output to valid JSON without
#: enforcing the shape.
_SCHEMA_CAPABLE_HINTS = ("gpt-oss", "qwen", "mistral-large", "ministral")


class FallbackNotConfigured(RuntimeError):
    """No fallback key is set, so there is nothing to fall back to."""


def configured() -> bool:
    return bool(settings.FALLBACK_API_KEY.strip())


def _supports_schema(model: str) -> bool:
    lowered = model.lower()
    return any(hint in lowered for hint in _SCHEMA_CAPABLE_HINTS)


def _strictify(node: Any) -> Any:
    """Make a JSON Schema acceptable to strict constrained decoding.

    Groq rejects a strict schema unless **every** object sets
    `additionalProperties: false`, and Pydantic does not emit it:

        400 invalid JSON schema for response_format:
            `additionalProperties:false` must be set on every object

    Strict mode also requires every property to be listed as required,
    since constrained decoding cannot choose to omit a field.

    Recursive because a schema nests -- $defs, arrays of objects, nested
    models -- and setting it only at the top passes a local check and
    fails at the provider.
    """
    if isinstance(node, list):
        return [_strictify(item) for item in node]
    if not isinstance(node, dict):
        return node

    out = {key: _strictify(value) for key, value in node.items()}
    if out.get("type") == "object" or "properties" in out:
        out.setdefault("additionalProperties", False)
        if "properties" in out:
            out["required"] = list(out["properties"])
    return out


def _schema_of(response_schema: Any) -> dict | None:
    """Turn whatever the caller passed into a JSON Schema dict.

    Callers pass a Pydantic model describing the output, a plain dict, a
    google-genai `types.Schema`, or nothing.

    The genai case is the trap. `types.Schema` is itself a Pydantic
    model, so calling model_json_schema() on it returns the **meta**
    schema -- a description of what a schema looks like, not of the card
    being generated. Sending that asked Groq to generate a schema, and it
    rejected the request outright:

        400 unsupported schema node of type []interface {}
            at #/$defs/Schema/properties/required

    which would have made card generation fail on the fallback rather
    than merely degrade. Converted properly where genai offers it, and
    otherwise returned as None so the caller drops to json_object --
    valid JSON with the shape asked for in words, which is weaker but
    works.
    """
    if response_schema is None:
        return None
    if isinstance(response_schema, dict):
        return response_schema

    # google-genai types.Schema: convert the instance's own contents, not
    # the class's metaschema.
    if type(response_schema).__name__ == "Schema":
        dump = getattr(response_schema, "model_dump", None)
        if callable(dump):
            raw = dump(exclude_none=True, mode="json")
            return _genai_to_json_schema(raw)
        return None

    schema_fn = getattr(response_schema, "model_json_schema", None)
    if callable(schema_fn):
        return schema_fn()
    return None


def _genai_to_json_schema(node: Any) -> Any:
    """Translate a dumped genai Schema into ordinary JSON Schema.

    genai spells types in upper case ("OBJECT", "ARRAY") and uses
    `nullable`; JSON Schema wants lower case. Small, but the difference
    between a schema a provider accepts and a 400.
    """
    if isinstance(node, list):
        return [_genai_to_json_schema(item) for item in node]
    if not isinstance(node, dict):
        return node

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "type" and isinstance(value, str):
            out["type"] = value.lower()
        elif key == "nullable":
            continue          # expressed differently in JSON Schema
        else:
            out[key] = _genai_to_json_schema(value)
    return out


def generate_text(
    prompt: str,
    *,
    system_instruction: str | None = None,
    response_mime_type: str | None = None,
    response_schema: Any = None,
    temperature: float = 0.2,
    model: str | None = None,
    timeout: float | None = None,
) -> str:
    """Generate with the fallback provider. Mirrors ai.client.generate_text."""
    if not configured():
        raise FallbackNotConfigured(
            "No FALLBACK_API_KEY is set, so there is no second model to use "
            "when Gemini's quota is exhausted."
        )

    chosen = model or settings.FALLBACK_MODEL
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": chosen,
        "messages": messages,
        "temperature": temperature,
    }

    wants_json = (response_mime_type or "").startswith("application/json")
    if wants_json:
        schema = _schema_of(response_schema)
        if schema and _supports_schema(chosen):
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "strict": True,
                                "schema": _strictify(schema)},
            }
        else:
            payload["response_format"] = {"type": "json_object"}
            if schema:
                # json_object guarantees valid JSON but not the shape, so
                # the shape is asked for in words. Weaker than constrained
                # decoding and far better than hoping.
                messages[-1]["content"] += (
                    "\n\nReply with JSON matching exactly this schema:\n"
                    + json.dumps(schema)
                )

    try:
        response = httpx.post(
            f"{settings.FALLBACK_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.FALLBACK_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout or settings.GEMINI_REQUEST_TIMEOUT_MS / 1000,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Fallback provider unreachable: {exc}") from exc

    if response.status_code != 200:
        # Logged in full, raised in brief: the body names the cause and
        # can carry the key's own quota state, which is not for callers.
        logger.warning("Fallback provider returned %s: %s",
                       response.status_code, response.text[:300])
        raise RuntimeError(
            f"Fallback provider returned {response.status_code}"
        )

    data = response.json()
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError("Fallback reply had no content") from exc
