"""Gemini model roles.

Single place to swap models. Verified working: google-genai 2.29.0 with
gemini-3.8-flash for vision, generation, and Search grounding.
"""

from ..core.config import settings

# Vision transcription, card/question generation, the assistant.
PRIMARY = settings.GEMINI_MODEL_PRIMARY

# Cheap classification and tagging passes.
LIGHT = settings.GEMINI_MODEL_LIGHT
