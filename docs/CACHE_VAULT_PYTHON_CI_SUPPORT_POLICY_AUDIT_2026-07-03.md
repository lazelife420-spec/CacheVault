# Cache Vault — Python CI Support Policy Audit

Date: 2026-07-03
Branch: `audit/python-ci-support-policy`
Base: `release/v0.1.4-public-distribution` @ `8bbdac9`
Type: **Audit only. No code changes.**

Trigger: PR #12 (docs-only Settings audit) was blocked three consecutive
times by the `test (3.11)` CI job hanging ~20–28 minutes while `3.12`/`3.13`
each completed in ~2 minutes. This audit exists to decide whether 3.11
should keep gating merges, independent of PR #12, which stays untouched.

---

## Files audited

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `pyproject.toml`
- `packaging/cache_vault.spec`, `packaging/build_exe.ps1`, `packaging/package_release.ps1`
- `README.md`, `CHANGELOG.md` (no `CONTRIBUTING.md` exists)
- GitHub branch protection via `gh api repos/.../branches/<branch>/protection`

## What Python versions does Cache Vault claim to support?

Exactly one explicit claim exists in the whole repo:

```toml
# pyproject.toml
requires-python = ">=3.10"
```

No `README.md`, `CHANGELOG.md`, or dev-setup doc states a Python version
requirement (there is no `CONTRIBUTING.md` or `.python-version` file
either). Notably, **CI doesn't even test the declared floor** — the
`ci.yml` matrix is `["3.11", "3.12", "3.13"]`; 3.10 is never exercised
despite being the only version the package metadata says it supports.

## What version builds the packaged EXE?

**Python 3.13, exclusively.** `.github/workflows/release.yml` (triggered
on `v*` tags — the actual release pipeline) pins:

```yaml
- name: Set up Python 3.13
  uses: actions/setup-python@v6
  with:
    python-version: "3.13"
```

and every subsequent release step (tests, selftest, `packaging/build_exe.ps1`
→ PyInstaller, metadata verification, artifact packaging, GitHub Release
publish) runs inside that same 3.13 environment. `packaging/cache_vault.spec`
has no Python-version pin of its own — it simply inherits whatever
interpreter invokes PyInstaller, which in the only pipeline that ships a
release is 3.13.

## Does the public app need Python 3.11?

**No.** End users install and run `CacheVault.exe`, a one-file PyInstaller
bundle built once (on 3.13) in `release.yml`. Nothing in `packaging/` or
the shipped artifact depends on, references, or is re-built per Python
version. Once the EXE exists, the interpreter used to build it is
irrelevant to how it runs on a user's machine.

## Is 3.11 only a developer/source compatibility target?

**Yes.** 3.11's only appearance anywhere in the repo is as one of three
entries in `ci.yml`'s test matrix. It doesn't build anything, isn't
referenced in packaging or release tooling, and isn't named as a
requirement in any doc. Its sole function today is verifying the source
tree and test suite behave under that interpreter — a source-compatibility
signal, not a shipping requirement.

## Can 3.11 be removed from required CI or made optional?

**Yes, with no branch-protection changes needed, because none exist today.**

```
$ gh api repos/lazelife420-spec/CacheVault/branches/release%2Fv0.1.4-public-distribution/protection
Branch not protected (404)

$ gh api repos/lazelife420-spec/CacheVault/branches/master/protection
Branch not protected (404)
```

Neither `release/v0.1.4-public-distribution` nor `master` has any GitHub
branch-protection rule, which means there is **no repository-enforced
required status check today** — "all 3 jobs must be green before merge"
has been a process/agent discipline choice, not a GitHub-configured gate.
Practically, this means:
- Demoting 3.11 (e.g. `continue-on-error: true` on that matrix leg, or
  moving it to a separate non-blocking workflow, or dropping it from the
  matrix entirely) is a small, self-contained edit to `ci.yml` alone.
- No branch-protection "required checks" list needs to be touched, because
  none is configured to reference `test (3.11)` in the first place.
- If branch protection is ever added later, whoever configures it should
  simply list `test (3.12)` and `test (3.13)` as required and leave 3.11
  out (or non-required), consistent with the recommendation below.

## Recommendation

Matches your stated call, and the evidence supports it:

```
Required CI:      Python 3.12, Python 3.13
Non-blocking:      Python 3.11 (compatibility signal only)
```

3.13 is both a required check and the exact version that builds the
shipped EXE — keeping it required is the highest-value gate. 3.12 is
already the fastest/most reliable leg observed. 3.11 sits closest to the
declared `>=3.10` floor and is worth keeping as a compatibility signal, but
given it has now hung 3/3 times for 20–28 minutes on this runner pool while
contributing zero release-build value, it should not be allowed to block
merges by itself.

## Final verdict

**AUDIT_ONLY / NO_CODE_CHANGES.**

This branch modifies no workflow, packaging, or source file — only this
receipt. `.github/workflows/ci.yml` is unchanged; PR #12 is untouched.
Any change to CI policy (e.g. `continue-on-error` on the 3.11 leg) is a
separate, explicit follow-up for you to approve.
