"""Reality Gate runner: plan + execute a validation tier.

Shells out to the SAME proven primitives that scripts/ci_local_full.ps1 uses
(python -m compileall, scan_claims.py, scan_secrets.py, pytest, app.py
--selftest, headless smokes) so the non-canonical tiers are genuine subsets of
the canonical work. The canonical tier delegates to ci_local_full.ps1 verbatim.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from . import pipelines as P
from .change_map import Resolution, resolve_diff
from .receipts import verdict_hash, write_receipt

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "reality_gate" / "runs"

# Inline preflight: refuse to claim PASS if required runtime deps are missing.
# Mirrors the preflight block in scripts/ci_local_full.ps1.
PREFLIGHT_CODE = (
    "import importlib.util, sys\n"
    'req = ["cryptography", "customtkinter", "PIL", "zeroconf"]\n'
    'if sys.platform.startswith("win"):\n'
    '    req.append("win32api")\n'
    'missing = [m for m in req if importlib.util.find_spec(m) is None]\n'
    'print("python " + sys.version.split()[0])\n'
    'print("missing=" + (",".join(missing) if missing else "none"))\n'
    "sys.exit(1 if missing else 0)\n"
)


@dataclass
class StepResult:
    name: str
    kind: str
    ok: bool
    returncode: int
    duration: float
    summary: str
    log_path: str
    skipped: bool = False


# ---------------------------------------------------------------------------
# Environment + git helpers
# ---------------------------------------------------------------------------


def resolve_python() -> str:
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv.exists():
        return str(venv)
    return sys.executable


def resolve_pwsh() -> str:
    return shutil.which("pwsh") or shutil.which("powershell") or "pwsh"


def _git(args: list[str]) -> str | None:
    try:
        r = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git_head() -> str:
    return _git(["rev-parse", "HEAD"]) or "(not a git repo)"


def git_short() -> str:
    return _git(["rev-parse", "--short", "HEAD"]) or "nogit"


def git_changed_paths(base: str = "HEAD") -> list[str]:
    if _git(["rev-parse", "--is-inside-work-tree"]) is None:
        return []
    diff = _git(["diff", "--name-only", base]) or ""
    paths = [l for l in diff.splitlines() if l.strip()]
    untracked = _git(["ls-files", "--others", "--exclude-standard"]) or ""
    paths += [l for l in untracked.splitlines() if l.strip()]
    return sorted(set(paths))


def _tracked_any(targets: list[str]) -> bool:
    out = _git(["ls-files", *targets]) or ""
    return bool(out.strip())


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _touches_command_center(res: Resolution) -> bool:
    return any("command_center" in p for p in res.changed_paths)


def build_plan(tier: str, res: Resolution) -> list[dict]:
    if tier == "canonical":
        return [{"name": "canonical", "kind": "canonical_ps1"}]

    steps: list[dict] = [
        {"name": "preflight", "kind": "preflight"},
        {"name": "compileall", "kind": "compileall"},
        {"name": "scan_claims", "kind": "scan_claims"},
        {"name": "scan_secrets", "kind": "scan_secrets"},
    ]

    if tier == "fast":
        if res.lanes:
            steps.append({"name": "pytest-diff", "kind": "pytest", "targets": res.lanes})
        else:
            steps.append(
                {"name": "pytest-diff", "kind": "pytest", "targets": [], "skipped": True,
                 "note": "no changed-module lanes selected"}
            )

    elif tier == "engineering":
        targets = _dedupe(list(res.lanes) + list(P.SAFETY_SPINE))
        steps.append({"name": "pytest-lanes+spine", "kind": "pytest", "targets": targets})
        steps.append({"name": "selftest", "kind": "selftest"})
        smoke = "command_center_runtime_proof.py"
        if _touches_command_center(res):
            steps.append({"name": "smoke-command-center", "kind": "smoke", "smoke": smoke})
        else:
            steps.append(
                {"name": "smoke-command-center", "kind": "smoke", "smoke": smoke,
                 "skipped": True, "note": "command_center not in diff"}
            )

    elif tier == "product":
        steps.append({"name": "pytest-full", "kind": "pytest", "targets": ["tests/"]})
        steps.append({"name": "selftest", "kind": "selftest"})
        for s in P.SMOKES:
            steps.append({"name": f"smoke-{s[:-3]}", "kind": "smoke", "smoke": s})
        for name, files in P.SUBSETS.items():
            steps.append(
                {"name": f"subset-{name}", "kind": "subset", "subset": name, "targets": list(files)}
            )

    return steps


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _parse_summary(out: bytes, kind: str) -> str:
    try:
        text = out.decode("utf-8", errors="replace")
    except Exception:
        text = str(out)
    if kind in ("pytest", "subset"):
        for line in reversed(text.splitlines()):
            if re.search(r"\d+\s+(?:passed|failed|skipped|error)", line):
                return line.strip()[:160]
        return "(no pytest summary)"
    if kind == "canonical_ps1":
        for line in reversed(text.splitlines()):
            if "CACHE VAULT LOCAL CI:" in line:
                return line.strip()[:160]
        return "(no canonical summary)"
    lines = [l for l in text.splitlines() if l.strip()]
    return lines[-1].strip()[:160] if lines else "(no output)"


def execute_step(step: dict, py: str, pwsh: str, logs_dir: Path) -> StepResult:
    if step.get("skipped"):
        return StepResult(step["name"], step["kind"], True, 0, 0.0,
                          step.get("note", "skipped"), "", True)

    kind = step["kind"]
    if kind == "preflight":
        args = [py, "-c", PREFLIGHT_CODE]
    elif kind == "compileall":
        args = [py, "-m", "compileall", "-q", "cache_vault"]
    elif kind == "scan_claims":
        args = [py, "scripts/scan_claims.py"]
    elif kind == "scan_secrets":
        args = [py, "scripts/scan_secrets.py"]
    elif kind == "pytest":
        targets = step.get("targets", [])
        if not targets:
            return StepResult(step["name"], kind, True, 0, 0.0,
                              "no targets (skipped)", "", True)
        args = [py, "-m", "pytest", "-rs", "--color=no", *targets]
    elif kind == "selftest":
        args = [py, "app.py", "--selftest"]
    elif kind == "smoke":
        args = [py, f"scripts/{step['smoke']}"]
    elif kind == "subset":
        if step["subset"] == "command-center" and not _tracked_any(step["targets"]):
            return StepResult(step["name"], kind, True, 0, 0.0,
                              "command-center subset skipped (untracked)", "", True)
        args = [py, "-m", "pytest", "-rs", "--color=no", *step["targets"]]
    elif kind == "canonical_ps1":
        args = [pwsh, "-NoProfile", "-File", "scripts/ci_local_full.ps1"]
    else:
        return StepResult(step["name"], kind, False, 99, 0.0,
                           f"unknown step kind: {kind}", "", False)

    log_path = logs_dir / f"{step['name']}.log"
    t0 = time.time()
    proc = subprocess.run(args, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    dur = time.time() - t0
    log_path.write_bytes(proc.stdout)
    ok = proc.returncode == 0
    summary = _parse_summary(proc.stdout, kind)
    return StepResult(
        step["name"], kind, ok, proc.returncode, dur, summary,
        str(log_path.relative_to(ROOT)), False,
    )


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------


def _print_plan(tier_req: str, effective: str, res: Resolution, plan: list[dict], forced_note: str) -> None:
    print(f"\n===== REALITY GATE — plan (dry run) =====")
    if effective != tier_req:
        print(f"tier: {tier_req} -> {effective} (ESCALATED)")
    else:
        print(f"tier: {effective}")
    if forced_note:
        print(forced_note)
    print(f"changed files: {len(res.changed_paths)}")
    if effective != tier_req:
        esc = [r for r in res.reasons if "non-source" not in r and "no dedicated" not in r]
        if esc:
            print("escalation reasons:")
            for r in esc:
                print(f"  - {r}")
    if res.lanes:
        print(f"selected lanes ({len(res.lanes)}):")
        for l in res.lanes:
            print(f"  - {l}")
    print("steps that WOULD run:")
    for s in plan:
        tag = "skip" if s.get("skipped") else "run"
        extra = ""
        if s["kind"] == "pytest" and s.get("targets"):
            extra = f"  [{len(s['targets'])} target(s)]"
        elif s["kind"] == "subset":
            extra = f"  [{s.get('subset')}]"
        print(f"  [{tag}] {s['name']} ({s['kind']}){extra}")
    print("========================================\n")


def _print_step_live(r: StepResult) -> None:
    flag = "SKIP" if r.skipped else ("PASS" if r.ok else "FAIL")
    print(f"  [{flag}] {r.name} ({r.duration:.1f}s) {r.summary}")


def _print_summary(overall: bool, effective: str, results: list[StepResult], receipt_path: Path) -> None:
    print("\n----------------------------------------")
    print(f"REALITY GATE: {'PASS' if overall else 'FAIL'}  (tier {effective})")
    for r in results:
        flag = "SKIP" if r.skipped else ("PASS" if r.ok else "FAIL")
        print(f"  [{flag}] {r.name}: {r.summary}")
    print(f"receipt: {receipt_path.relative_to(ROOT)}")
    print("----------------------------------------")


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def run_pipeline(
    tier_requested: str,
    project: str,
    base: str = "HEAD",
    force_tier: bool = False,
    dry_run: bool = False,
) -> int:
    py = resolve_python()
    pwsh = resolve_pwsh()
    changed = git_changed_paths(base)
    res = resolve_diff(changed)

    if force_tier:
        effective = tier_requested
        forced_note = "note: escalation DISABLED (--force-tier)"
    else:
        effective = P.max_tier(tier_requested, res.forced_tier) or tier_requested
        forced_note = ""

    plan = build_plan(effective, res)

    if dry_run:
        _print_plan(tier_requested, effective, res, plan, forced_note)
        return 0

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    logs_dir = RUNS_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)

    print(f"\n===== REALITY GATE — {project} =====")
    if effective != tier_requested:
        print(f"tier: {tier_requested} -> {effective} (ESCALATED)")
    else:
        print(f"tier: {effective}")
    if forced_note:
        print(forced_note)
    print(f"diff base: {base}   changed files: {len(res.changed_paths)}")
    if effective != tier_requested:
        esc = [r for r in res.reasons if "non-source" not in r and "no dedicated" not in r]
        for r in esc:
            print(f"  - {r}")

    results: list[StepResult] = []
    for step in plan:
        r = execute_step(step, py, pwsh, logs_dir)
        results.append(r)
        _print_step_live(r)
        if not r.ok and not r.skipped:
            # Keep going so the receipt records every step, but a failure means
            # the overall verdict is FAIL regardless of later steps.
            pass

    overall = all(r.ok for r in results)
    exit_code = 0 if overall else 1

    verdict = {
        "project": project,
        "tier_requested": tier_requested,
        "tier_effective": effective,
        "escalated": effective != tier_requested,
        "force_tier": force_tier,
        "diff_base": base,
        "changed_files": res.changed_paths,
        "selected_lanes": res.lanes,
        "overall_pass": overall,
        "exit_code": exit_code,
        "steps": [
            {
                "name": r.name,
                "kind": r.kind,
                "ok": r.ok,
                "returncode": r.returncode,
                "skipped": r.skipped,
                "duration_s": round(r.duration, 1),
                "summary": r.summary,
            }
            for r in results
        ],
    }

    ts = time.strftime("%Y%m%d-%H%M%S")
    run_id = f"{ts}-{effective}-{git_short()}"
    receipt = {
        "run_id": run_id,
        "reality_gate_version": __version__,
        "git_head": git_head(),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "verdict": verdict,
        "verdict_hash": verdict_hash(verdict),
    }
    receipt_path = RUNS_DIR / f"{run_id}.json"
    write_receipt(receipt_path, receipt)

    _print_summary(overall, effective, results, receipt_path)
    return exit_code
