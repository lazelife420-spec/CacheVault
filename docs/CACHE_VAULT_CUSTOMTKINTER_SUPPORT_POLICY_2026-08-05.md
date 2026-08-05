# CustomTkinter Support Policy (2026-08-05)

## Summary

Cache Vault pins **`customtkinter==6.0.0`** exactly. This is a reproducibility
requirement, not a preference: the Windows wheel-scroll patch
(`cache_vault/ui/scroll_patch.py`) depends on **private** CustomTkinter APIs
that change across releases, so any unpinned range risks shipping a packaged
build that crashes on the first mouse-wheel event.

## Authoritative dependency input

Every real install path resolves CustomTkinter from **`requirements.txt`**:

| Path                 | Command                                             | Source            |
|----------------------|-----------------------------------------------------|-------------------|
| Developer install    | `pip install -r requirements.txt` (README)          | `requirements.txt`|
| CI (`ci.yml`)        | `pip install ... -r requirements.txt`               | `requirements.txt`|
| Packaged EXE build   | `packaging/build_exe.ps1` → `pip install -r requirements.txt pyinstaller` | `requirements.txt`|
| Release (`release.yml`) | `pip install -r requirements-dev.txt` (`-r requirements.txt`) then `build_exe.ps1` | `requirements.txt`|

`pyproject.toml` `[project].dependencies` governs only `pip install .` /
wheel-based installs of the `cache-vault` package. Its own comment mandates it
be kept "in lockstep with requirements.txt", so it carries the same exact pin.

## Evidence

Introspection of `CTkScrollableFrame` (no Tk root) across versions on Python
3.13 (the release/CI target). Methodology: one **fresh isolated virtualenv per
version**, each provisioned with the auxiliary runtime packages available in a
normal CacheVault environment (`setuptools`, `packaging`, `darkdetect`) so that
an incidental missing package cannot mask the real class API.

| Version | Imports on 3.13 | `_mouse_wheel_all` | `_check_if_valid_scroll` | `check_if_master_is_canvas` |
|---------|-----------------|--------------------|--------------------------|-----------------------------|
| 5.2.0   | Yes             | Yes | **No**  | Yes |
| 5.2.1   | Yes             | Yes | **No**  | Yes |
| 5.2.2   | Yes             | Yes | **No**  | Yes |
| 6.0.0 (latest) | Yes      | Yes | **Yes** | No  |

The patch calls `self._check_if_valid_scroll(...)`, which exists **only in
6.0.0**. Every 5.2.x release lacks it and instead exposes the old
`check_if_master_is_canvas`, so the corrected patch would raise `AttributeError`
on the first wheel event on any 5.2.x (the original packaged-crash signature).
6.0.0 is the latest release, so there is no newer compatible version to include
in a range.

(Earlier notes claiming 5.2.0/5.2.1 fail to import on Python 3.13 were an
artifact of a minimal environment missing `distutils`/`packaging`; with the
auxiliary packages present, all four versions import cleanly. The decisive fact
is the presence of `_check_if_valid_scroll`, not import behavior.)

## Private APIs the patch depends on

Class-level (verified by the compatibility probe):

- `CTkScrollableFrame._mouse_wheel_all`
- `CTkScrollableFrame._check_if_valid_scroll`

Instance-only (created in `__init__`; cannot be verified without a Tk root, so
they are intentionally **not** required by the probe): `_parent_canvas`
(CTkScrollableFrame), `_textbox` (CTkTextbox).

## Runtime safety net

`cache_vault/ui/scroll_patch.py::verify_scroll_patch_compatibility()` is a
non-mutating probe (no Tk root, no patch install) that raises
`ScrollPatchIncompatibleError` naming the detected version and any missing
attribute. It runs:

- inside `install_windows_scroll_patch()` before the monkey patch is applied
  (so GUI startup fails loudly and clearly instead of crashing at wheel time);
- inside `app.py --selftest` before it reports success (so CI and the packaged
  self-test fail on an incompatible bundled CustomTkinter — closing the gap
  where `--selftest` previously returned before touching `scroll_patch`).

## Changing the pin in future

If CustomTkinter is upgraded, re-run the introspection above, confirm both
required class-level attributes still exist, update the pin in **both**
`requirements.txt` and `pyproject.toml`, rebuild the packaged EXE, and run the
packaged `--selftest` plus a wheel smoke on the scrollable views.
