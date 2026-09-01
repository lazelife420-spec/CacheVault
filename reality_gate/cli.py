"""Reality Gate CLI.

Command surface:
    reality-gate status
    reality-gate project list
    reality-gate pipeline validate CacheVault [--pipeline ...] [--base <ref>] [--force-tier]
    reality-gate run CacheVault [--pipeline ...] [--base <ref>] [--force-tier]
    reality-gate receipt verify <run-id>

Bare ``reality-gate run CacheVault`` defaults to the ``engineering`` pipeline.
An optional user alias is documented (e.g. ``Set-Alias rgate reality-gate``);
scripts, receipts, docs, and automation MUST use the canonical ``reality-gate``
name — never ``rg`` (that collides with ripgrep).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import __version__
from . import pipelines as P
from .receipts import verify_receipt
from .runner import RUNS_DIR, ROOT, git_head, resolve_pwsh, resolve_python, run_pipeline

_KNOWN_PROJECTS = {"cachevault", "cache-vault"}


def _detect_project() -> str:
    pp = ROOT / "pyproject.toml"
    if pp.is_file():
        m = re.search(r'name\s*=\s*"([^"]+)"', pp.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return "cache-vault"


def _check_project(name: str) -> bool:
    return name.lower().replace("_", "-") in _KNOWN_PROJECTS


def cmd_status(args: argparse.Namespace) -> int:
    py = resolve_python()
    pwsh = resolve_pwsh()
    head = git_head()
    proj = _detect_project()
    receipts = list(RUNS_DIR.glob("*.json")) if RUNS_DIR.exists() else []
    print(f"Reality Gate v{__version__}")
    print(f"repo:          {ROOT}")
    print(f"project:       {proj}")
    print(f"python:        {py}")
    print(f"pwsh:          {pwsh}")
    print(f"git head:      {head}")
    print(f"default tier:  {P.DEFAULT_TIER}")
    print(f"tiers:         {', '.join(P.TIERS)}")
    print(f"runs dir:      {RUNS_DIR}  ({len(receipts)} receipt(s))")
    return 0


def cmd_project_list(args: argparse.Namespace) -> int:
    print(_detect_project())
    return 0


def cmd_pipeline_validate(args: argparse.Namespace) -> int:
    if not _check_project(args.project):
        print(f"unknown project: {args.project}", file=sys.stderr)
        return 2
    return run_pipeline(args.pipeline, args.project, base=args.base,
                        force_tier=args.force_tier, dry_run=True)


def cmd_run(args: argparse.Namespace) -> int:
    if not _check_project(args.project):
        print(f"unknown project: {args.project}", file=sys.stderr)
        return 2
    tier = args.pipeline or P.DEFAULT_TIER
    return run_pipeline(tier, args.project, base=args.base,
                        force_tier=args.force_tier, dry_run=False)


def cmd_receipt_verify(args: argparse.Namespace) -> int:
    candidates = [RUNS_DIR / f"{args.run_id}.json", RUNS_DIR / args.run_id]
    path = next((c for c in candidates if c.exists()), None)
    if path is None:
        print(f"receipt not found: {args.run_id}", file=sys.stderr)
        return 2
    data, ok, actual, expected = verify_receipt(path)
    print(f"run_id:           {data.get('run_id')}")
    print(f"verdict_hash ok:  {ok}")
    if not ok:
        print(f"  expected: {expected}")
        print(f"  actual:   {actual}")
    v = data.get("verdict", {})
    print(f"tier:             {v.get('tier_requested')} -> {v.get('tier_effective')} "
          f"(escalated={v.get('escalated')})")
    print(f"overall_pass:     {v.get('overall_pass')}   exit_code: {v.get('exit_code')}")
    print("steps:")
    for s in v.get("steps", []):
        flag = "SKIP" if s.get("skipped") else ("PASS" if s.get("ok") else "FAIL")
        print(f"  [{flag}] {s.get('name')}: {s.get('summary')}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reality-gate",
        description="Reality Gate — tiered validation control plane for Cache Vault.",
    )
    p.add_argument("--version", action="version", version=f"reality-gate {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show gate / environment status").set_defaults(func=cmd_status)

    pp = sub.add_parser("project", help="project commands")
    pps = pp.add_subparsers(dest="project_command", required=True)
    pps.add_parser("list", help="list configured projects").set_defaults(func=cmd_project_list)

    pipe = sub.add_parser("pipeline", help="pipeline commands")
    pipes = pipe.add_subparsers(dest="pipeline_command", required=True)
    pv = pipes.add_parser("validate", help="dry-run: show the plan that WOULD run")
    pv.add_argument("project")
    pv.add_argument("--pipeline", choices=P.TIERS, default=P.DEFAULT_TIER)
    pv.add_argument("--base", default="HEAD", help="git ref to diff against")
    pv.add_argument("--force-tier", action="store_true",
                    help="pin the tier and DISABLE escalation (dev/validation only)")
    pv.set_defaults(func=cmd_pipeline_validate)

    run = sub.add_parser("run", help="execute a validation pipeline")
    run.add_argument("project")
    run.add_argument("--pipeline", choices=P.TIERS, help=f"default: {P.DEFAULT_TIER}")
    run.add_argument("--base", default="HEAD", help="git ref to diff against")
    run.add_argument("--force-tier", action="store_true",
                     help="pin the tier and DISABLE escalation (dev/validation only)")
    run.set_defaults(func=cmd_run)

    rec = sub.add_parser("receipt", help="receipt commands")
    recs = rec.add_subparsers(dest="receipt_command", required=True)
    rv = recs.add_parser("verify", help="verify a stored run receipt")
    rv.add_argument("run_id")
    rv.set_defaults(func=cmd_receipt_verify)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
