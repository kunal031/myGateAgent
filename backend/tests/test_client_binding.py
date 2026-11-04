"""The browser's fetch must be called bound to the global object.

Not a Python test of Python code: this guards a TypeScript bug that
reached a running browser, and the repository has no JS test runner. It
runs the real transport under tsx with a fetch that behaves like
window.fetch -- throwing unless `this` is the global -- and asserts the
client does not trip it.

The bug: ApiClient stored `globalThis.fetch` as a bare reference and
called it as `this.fetchImpl(...)`, so `this` became the ApiClient
instance and the browser raised

    Failed to execute 'fetch' on 'Window': Illegal invocation

on every request, including sign-in. The interceptor this class replaced
bound it with `.bind(window)` for exactly this reason; the bind was lost
in the refactor and no test covered it because the Node tests call fetch
in a context where the detached call happens to work.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"

PROBE = r"""
import { ApiClient, MemoryTokenStore } from "./src/lib/client/index";

const real = globalThis.fetch;
function windowFetch(this: unknown, ...args: unknown[]) {
  if (this !== globalThis) {
    throw new TypeError(
      "Failed to execute 'fetch' on 'Window': Illegal invocation",
    );
  }
  return (real as never as (...a: unknown[]) => Promise<Response>)(...args);
}
Object.defineProperty(globalThis, "fetch", {
  value: windowFetch, writable: true, configurable: true,
});

// Port 9 (discard) refuses fast, so the request fails on connection --
// any error EXCEPT "Illegal invocation" means fetch was bound correctly.
const api = new ApiClient({
  baseUrl: "http://127.0.0.1:9",
  store: new MemoryTokenStore(),
});
api.get("/x").then(
  () => { console.log("UNEXPECTED_SUCCESS"); },
  (e) => {
    console.log(/Illegal invocation/.test(e.message) ? "DETACHED" : "BOUND");
  },
);
"""


@pytest.mark.skipif(shutil.which("npx") is None, reason="npx not available")
def test_browser_fetch_is_called_bound(tmp_path):
    probe = FRONTEND / "__fetch_binding_probe.ts"
    probe.write_text(PROBE)
    try:
        result = subprocess.run(
            ["npx", "tsx", probe.name],
            cwd=FRONTEND, capture_output=True, text=True, timeout=300,
        )
    finally:
        probe.unlink(missing_ok=True)

    assert "DETACHED" not in result.stdout, (
        "ApiClient called fetch detached from the global object. In a "
        "browser this is 'Illegal invocation' on every request.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr[-600:]}"
    )
    assert "BOUND" in result.stdout, (
        f"probe did not run.\nstdout: {result.stdout}\n"
        f"stderr: {result.stderr[-600:]}"
    )
