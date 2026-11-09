"""Every @register job is reachable from the worker.

The worker populates JOBS as a side effect of importing the modules that
own the decorators, so a job whose module is not in that import list is
simply absent at runtime.

That failure is invisible from the outside, which is why it needs a
test rather than care. `/api/assistant/ask` writes a "pending"
placeholder, dispatches and returns 200 immediately, so the API looks
healthy; the worker then raises KeyError *before* reaching the
try/except that would record the failure on the row. The message stays
"pending" for ever and the client polls an answer that is never coming.
`answer_question` shipped like that and broke every question asked in
production.

So this sweeps the source for @register and compares it against what
the worker's own import list produces, rather than listing jobs by
hand -- a new job is covered the moment it is written.
"""

from . import env_setup  # noqa: F401  (before any app import)

import ast
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def _registered_in_source() -> dict[str, str]:
    """Job name -> the module that declares it, found by reading the AST.

    Parsed rather than imported: importing every module to find the
    decorators would itself register them, which is precisely the thing
    under test.
    """
    found: dict[str, str] = {}
    for path in APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                # @register("name") -- a Call whose func is named register.
                if not isinstance(decorator, ast.Call):
                    continue
                func = decorator.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name != "register" or not decorator.args:
                    continue
                first = decorator.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    rel = path.relative_to(APP_DIR.parent)
                    found[first.value] = str(rel)
    return found


def _jobs_the_worker_sees() -> set[str]:
    """JOBS after running exactly the imports the worker handler does.

    Measured in a **subprocess**, which is the only way to get a true
    answer. conftest imports app.main, and app.main includes every
    router -- so by the time a test runs, this process has already
    imported app.api.assistant and registered its jobs no matter what
    the worker imports. Checking JOBS in-process passes whether or not
    the bug is present, which is a test that proves nothing.

    A fresh interpreter imports only what the handler imports.
    """
    source = (APP_DIR / "lambda_worker.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("api"):
            modules.extend(alias.name for alias in node.names)

    assert modules, (
        "lambda_worker.handler has no `from .api import ...`; this test "
        "can no longer tell what the worker registers"
    )

    imports = "; ".join(f"import app.api.{m}" for m in modules)
    probe = (
        "import tests.env_setup\n"
        f"{imports}\n"
        "from app.core.background import JOBS\n"
        "print(','.join(sorted(JOBS)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=APP_DIR.parent, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"probing the worker's imports failed:\n{result.stderr[-2000:]}"
    )
    return set(filter(None, result.stdout.strip().split(",")))


def test_the_worker_can_run_every_registered_job():
    declared = _registered_in_source()
    reachable = _jobs_the_worker_sees()

    missing = {name: mod for name, mod in declared.items() if name not in reachable}
    assert not missing, (
        "These jobs are dispatched but the worker cannot run them, so the "
        "work is dropped and whatever row tracks it is never updated. Add "
        "the module to the import in lambda_worker.handler: "
        + ", ".join(f"{n} (declared in {m})" for n, m in sorted(missing.items()))
    )


@pytest.mark.parametrize("job", ["answer_question", "import_paper_url",
                                 "confirm_paper", "import_paper_pdf"])
def test_known_jobs_stay_reachable(job):
    """Names the jobs that exist today, so deleting one is deliberate.

    The sweep above passes vacuously if every @register disappears; this
    fails instead.
    """
    assert job in _jobs_the_worker_sees()
