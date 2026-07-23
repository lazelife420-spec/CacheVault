"""Tk / CustomTkinter availability probe for UI tests.

The probe constructs a real ``tk.Tk()`` instance so that runner-image
environments where ``import tkinter`` succeeds but the Tcl/Tk runtime files
(``tk.tcl``, ``init.tcl``, ``vistaTheme.tcl``, ...) are missing or broken are
detected here rather than inside individual test bodies.

``probe_tk_ui()`` returns ``(True, "")`` only when the full stack --
tkinter import, ``tk.Tk()`` construction, ``ttk.Label``, and
``customtkinter.CTk()`` -- all succeed without raising.

The probe runs in a child subprocess.  The child emits a single line of JSON
on stdout and exits.  The parent parses it strictly.  A timeout or crash
raises ``TkProbeTimeout`` or ``TkProbeCrash`` respectively so that the 17
modules that call ``probe_tk_ui()`` at import time never silently convert an
infrastructure defect into skipped tests.

Child status values
-------------------
"available"     -- Tk and CustomTkinter are fully functional.
"unavailable"   -- A recognized environment deficiency (missing TCL runtime,
                   no display, etc.) was detected.  Only this status may cause
                   @skipif-decorated tests to be skipped.
"defect"        -- A widget-construction exception that is NOT a recognized
                   environment failure.  The parent raises ``TkProbeCrash`` so
                   the test session fails loudly instead of skipping silently.
"""

from __future__ import annotations

import functools
import json
import subprocess
import sys

# ---------------------------------------------------------------------------
# Known environment-failure tokens.  Any exception whose str() contains one
# of these is classified as "unavailable" (environment deficiency), not a
# code defect.  See the original implementation for the rationale.
# ---------------------------------------------------------------------------
_TCL_UNAVAILABLE_TOKENS = (
    "tk.tcl",
    "init.tcl",
    "ttk",
    ".tcl",
    "Tk",
    "vistaTheme",
    "Can't find",
    "wasn't installed",
    "tcl_findLibrary",
    "invalid command name",
)


def _tcl_unavailable(exc: BaseException) -> bool:
    msg = str(exc)
    return any(token in msg for token in _TCL_UNAVAILABLE_TOKENS)


# ---------------------------------------------------------------------------
# Exceptions raised by the parent when the child cannot return a clean result.
# ---------------------------------------------------------------------------

class TkProbeTimeout(RuntimeError):
    """Raised when the probe child process does not complete within the timeout.

    Do NOT catch this in test modules.  Let it propagate so the session fails
    loudly rather than silently skipping tests.
    """

    def __init__(self, timeout_s: float, stdout: str, stderr: str) -> None:
        self.timeout_s = timeout_s
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(
            f"Tk probe timed out after {timeout_s}s.  "
            f"stdout={stdout!r}  stderr={stderr[:200]!r}"
        )


class TkProbeCrash(RuntimeError):
    """Raised when the probe child crashes, emits invalid JSON, or reports a
    widget-construction defect that is not a recognized environment failure.

    Do NOT catch this in test modules.  It represents a real infrastructure or
    application defect, not an unavailable environment.
    """

    def __init__(self, reason: str, stdout: str, stderr: str) -> None:
        self.reason = reason
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(
            f"Tk probe crash/defect: {reason}  "
            f"stdout={stdout!r}  stderr={stderr[:200]!r}"
        )


# ---------------------------------------------------------------------------
# Child probe script.
# Emits one JSON line.  No CacheVault imports.  No mainloop().  No dialogs.
# ---------------------------------------------------------------------------
_PROBE_SCRIPT = r"""
import json, sys, traceback

TCL_TOKENS = (
    "tk.tcl", "init.tcl", "ttk", ".tcl", "Tk", "vistaTheme",
    "Can't find", "wasn't installed", "tcl_findLibrary",
    "invalid command name",
)

def _is_env_failure(exc):
    msg = str(exc)
    return any(t in msg for t in TCL_TOKENS)

def _emit(status, reason="", exc_type="", tb=""):
    print(json.dumps({
        "status": status,
        "reason": reason,
        "exception_type": exc_type,
        "traceback": tb,
    }), flush=True)

try:
    import tkinter as tk
    from tkinter import ttk
except Exception as exc:
    _emit("unavailable", f"tkinter unavailable: {exc}",
          type(exc).__name__, traceback.format_exc())
    sys.exit(0)

root = None
try:
    root = tk.Tk()
    root.withdraw()
    ttk.Label(root, text="probe")
    root.update_idletasks()
except Exception as exc:
    tb = traceback.format_exc()
    if _is_env_failure(exc):
        _emit("unavailable", f"Tk/ttk runtime unavailable: {str(exc)[:240]}",
              type(exc).__name__, tb)
    else:
        _emit("defect", f"Tk init defect: {str(exc)[:240]}",
              type(exc).__name__, tb)
    sys.exit(0)
finally:
    if root is not None:
        try:
            root.destroy()
        except Exception:
            pass

try:
    import customtkinter as ctk
except Exception as exc:
    _emit("unavailable", f"customtkinter unavailable: {exc}",
          type(exc).__name__, traceback.format_exc())
    sys.exit(0)

ctk_root = None
ctk_top = None
try:
    ctk_root = ctk.CTk()
    ctk_root.withdraw()
    ctk_top = ctk.CTkToplevel(ctk_root)
    ctk_top.withdraw()
    ctk_top.update_idletasks()
    _emit("available")
except Exception as exc:
    tb = traceback.format_exc()
    if _is_env_failure(exc):
        _emit("unavailable", f"CustomTkinter/Tk runtime unavailable: {str(exc)[:240]}",
              type(exc).__name__, tb)
    else:
        _emit("defect", f"CustomTkinter init defect: {str(exc)[:240]}",
              type(exc).__name__, tb)
finally:
    for w in (ctk_top, ctk_root):
        if w is not None:
            try:
                w.destroy()
            except Exception:
                pass
"""

_PROBE_TIMEOUT_S = 10.0


def probe_tk_ui() -> tuple[bool, str]:
    """Return ``(ok, reason)``.

    ``ok`` is ``True`` only when the Tk/CustomTkinter stack is fully available.
    ``ok`` is ``False`` only when a recognized *environment* deficiency is
    detected (missing runtime, no display, etc.).

    Raises
    ------
    TkProbeTimeout
        If the child process does not complete within ``_PROBE_TIMEOUT_S``
        seconds.  The caller must NOT suppress this -- it means the probe
        itself hung and tests decorated with ``@skipif(not ok)`` must NOT
        silently skip.
    TkProbeCrash
        If the child process crashes without emitting valid JSON, or emits a
        "defect" status (widget-construction error that is not a recognized
        environment failure).  Again, the caller must NOT suppress this.

    Caching
    -------
    Only ``(True, "")`` and ``(False, "<env reason>")`` outcomes are cached.
    Timeout and crash results propagate as exceptions and are therefore never
    cached by ``@lru_cache``.
    """
    return _probe_cached()


@functools.lru_cache(maxsize=1)
def _probe_cached() -> tuple[bool, str]:
    """Inner cached implementation.  Only called from ``probe_tk_ui()``."""
    proc = subprocess.Popen(
        [sys.executable, "-c", _PROBE_SCRIPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=_PROBE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise TkProbeTimeout(_PROBE_TIMEOUT_S, stdout or "", stderr or "")

    raw = stdout.strip()
    if not raw:
        raise TkProbeCrash(
            f"child exited with code {proc.returncode} and produced no output",
            stdout,
            stderr,
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TkProbeCrash(
            f"child output is not valid JSON: {exc}",
            stdout,
            stderr,
        ) from exc

    status = data.get("status")
    reason = data.get("reason", "")

    if status == "available":
        return True, ""
    if status == "unavailable":
        return False, reason
    if status == "defect":
        raise TkProbeCrash(
            f"widget-construction defect (not an environment failure): {reason}",
            stdout,
            stderr,
        )
    # Unknown status value -- treat as crash.
    raise TkProbeCrash(
        f"child emitted unknown status {status!r}: {raw}",
        stdout,
        stderr,
    )


# ---------------------------------------------------------------------------
# Utilities used by test bodies.
# ---------------------------------------------------------------------------

def wait_for_refresh(app, timeout: float = 6.0) -> None:
    """Pump the Tk loop until an async refresh started by ``refresh()`` /
    ``_do_refresh_sync()`` has finished applying its snapshot.

    ``refresh()`` debounces via ``self.after(50, self._do_refresh_sync)``,
    and the DB work then happens on a worker thread and lands back on the
    Tk thread via ``after(...)``;  a bare ``app.update()`` right after
    calling ``refresh()``/``_do_refresh_sync()`` is no longer enough to
    observe the result.  Checks ``_refresh_job`` (the pending debounce timer)
    as well as ``_refresh_workers_in_flight`` -- checking only the latter
    would race a call that hasn't reached ``_do_refresh_sync`` yet and
    return immediately, before the counter is ever incremented.  Raises
    ``AssertionError`` if the refresh hasn't settled within ``timeout``
    seconds, since a test that silently checked stale/empty state would be
    worse than a loud failure.
    """
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.update()
        if (
            getattr(app, "_refresh_job", None) is None
            and getattr(app, "_refresh_workers_in_flight", 0) == 0
        ):
            return
        time.sleep(0.01)
    raise AssertionError(f"refresh did not settle within {timeout}s")
