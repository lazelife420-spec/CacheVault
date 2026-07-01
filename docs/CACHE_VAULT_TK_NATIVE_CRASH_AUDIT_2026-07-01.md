# Cache Vault - Tk Native Crash Audit (2026-07-01)

Surgical audit of two prime suspects behind the recurring native crash:
cross-thread Tk access and image/PhotoImage lifecycle.

## 1. Windows crash signature

Extracted from `%LOCALAPPDATA%\CrashDumps\` minidumps and Windows Event Log
(Event ID 1000), consistent across every crash:

- Faulting module: `tk86t.dll` 8.6.2.15 (threaded Tcl/Tk)
- Exception: `0xc0000005` ACCESS_VIOLATION
- Fault offset: `0xd780f` - **identical every crash** (deterministic)
- Faulting instruction: `mov rdx, qword ptr [rax+28h]` with `rax = 0`
  -> NULL-pointer dereference (read of address `0x28`)
- Dumps present: 6/19, 6/25, and 4x on 6/30 (21:50, 21:55, 22:08, 22:13)
- Thread layout at fault: default thread idle in `NtWaitForMultipleObjects`,
  a separate thread faulted inside `tk86t`; `tcl86t` + two `python313` worker
  threads also active. Stack unsymbolizable past `tk86t+0xd780f` (no public
  Tk/Python symbols; frames do not unwind).

### The crashing binary was the OLD rc1 Downloads build

`cdb` process identity in the dump:

```
name: C:\Users\KickA\Downloads\Compressed\CacheVault-v0.1.5-rc1-windows\CacheVault.exe
```

Every dump was produced by the **rc1** build the user ran from Downloads, not
rc2 or rc3. The crash is **long-standing** (>= 6/19), not introduced by rc2/rc3.

### Why rc3 faulthandler is still required for final proof

The dump cannot show the Python call site (no symbols; broken unwind past the
Tk frame). The rc3 diagnostic build arms `faulthandler` -> `crash_native.log`,
which on the next fault prints a per-thread Python + C traceback naming the
exact widget/image operation and the thread it ran on. That is the only way to
convert "definite thread-safety violation exists" into "this exact call caused
this exact crash."

## 2. Cross-thread Tk audit

Marshaling infrastructure (correct, thread-safe):
- `shell._call_on_main(fn)` -> `self._main_thread_calls.put(fn)` (`queue.Queue`)
- `shell._pump_main_thread()` drains the queue on the Tk main thread every 50ms

| Source thread | File:Line | Tk/UI touched | Marshaled? | Risk | Fix |
|---|---|---|---|---|---|
| clipboard-monitor | core/clipboard.py `_emit` -> `_on_clip` | none (calls `_on_clip_captured`) | Yes - `_on_clip_captured` uses `_call_on_main` (shell.py:1617) | Low | none |
| hotkey-listener / multi-hotkey | core/hotkey.py `_run` | none (invokes `on_activate`) | Yes - shell callbacks use `_call_on_main` (3088, 1771-1777) | Low | none |
| macro-shortcut-listener | core/macro_shortcut_listener.py `_run` | none (invokes `on_match` / `schedule_main`) | Yes - `schedule_main=_call_on_main` (shell.py:361) | Low | none |
| tray (pystray) | shell.py 377-387 | menu/window ops | Yes - all callbacks use `_call_on_main` | Low | none |
| mobile-bridge (serve_forever) | core/mobile/bridge.py 181-190 | none directly | Yes - `on_notice`/`schedule_main` marshaled (shell.py 329, 361) | Low | none |
| **mobile-bridge-sync** | **shell.py `_sync_bridge` (~3049-3057)** | **`self.after(0, self.refresh)` + `self._alive()` (`winfo_viewable`/`state`)** | **NO - called directly from worker thread** | **HIGH** | **marshal via `_call_on_main` (PATCHED)** |
| foreground tracker | shell.py `_track_foreground_window` | Tk reads | N/A - scheduled via `self.after` on main thread | Low | none |

Core modules (`clipboard`, `hotkey`, `macro_shortcut_listener`, `bridge`) import
no Tk and cannot touch widgets directly - they only invoke callbacks. The
`winfo_id()` calls in `core/win_mouse.py:104` and `core/paste_delivery.py:79`
run on the main thread (installed via `self.after`). The only shell-defined
`threading.Thread` target is `_sync_bridge`, and it was the only place shell
code ran on a worker thread while touching Tk.

## 3. Image / PhotoImage lifecycle audit

`CTkImage`/`PhotoImage`/`ImageTk` usage is centralized: the only creation site
in the codebase is `preview.py`. `clip_list.py` and `clip_grid.py` render no
images.

| Aspect | File:Line | Finding | Risk |
|---|---|---|---|
| Image creation | preview.py 418-420 | `ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)` assigned to `self._image_ref`, then `self._image_label.configure(image=self._image_ref)` | Low |
| Reference retention | preview.py 57, 403, 418, 428 | `self._image_ref` held on the long-lived panel instance; cleared to `None` only alongside a `configure(image=None)` | Low - correct persistent-owner pattern |
| PIL lifetime | preview.py 407-419 | `with Image.open(...) as img:` then `thumb = img.convert(...).resize(...)`; `CTkImage` is built from `thumb` (an independent image), so closing `img` does not free the retained pixels | Low |
| Async race | preview.py `_render_image_preview` | Loader (`load_asset`) is synchronous, on the main thread; no background thread updates the label | Low - no race |

No image-lifetime bug found. Image refs are retained by the owning panel and
rendering is synchronous on the main thread.

## 4. Likely culprit ranking

1. **HIGH - cross-thread `self.after`/`winfo` in `_sync_bridge`.** Calling
   `Tk.after()` and `winfo_*`/`state()` from the `mobile-bridge-sync` worker
   thread manipulates Tcl's timer/event structures off the main thread. This is
   exactly the failure class that yields a native NULL-deref access violation in
   `tk86t.dll`/`tcl86t.dll`. This is the leading candidate and was patched.
2. **LOW - image/PhotoImage lifecycle.** Correct retention + synchronous main-
   thread rendering; no bug found. Not patched.

## 5. Smallest safe patch plan (applied)

`cache_vault/ui/shell.py`, `_sync_bridge` `finally` block:

```python
# before
finally:
    if self._alive():
        self.after(0, self.refresh)

# after
finally:
    # Marshal back to the Tk main thread: self.after()/winfo_*/state()
    # are not thread-safe and calling them from this worker corrupts
    # Tcl/Tk state (native access violation in tk86t.dll).
    self._call_on_main(lambda: self._alive() and self.refresh())
```

`_call_on_main` enqueues onto a `queue.Queue` (thread-safe); the enqueued
callback then runs on the Tk main thread via `_pump_main_thread`, where
`_alive()` and `refresh()` are safe to call. No other paths were changed.

## 6. What still needs faulthandler confirmation

- The dumps prove a native Tk NULL-deref but cannot name the Python frame. The
  patch removes a *definite* cross-thread Tk violation, but does not by itself
  *prove* it caused the specific "while getting photos" crash (mobile-bridge
  sync only spawns when bridge state needs syncing).
- Definitive proof requires reproducing under the rc3 diagnostic build and
  capturing `%LOCALAPPDATA%\CacheVault\crash_native.log`. If it still faults,
  the traceback will identify the exact call and thread; if it no longer faults
  after this change, that corroborates the cross-thread hypothesis.

## 7. Status

- Definite bug found: **yes** (cross-thread Tk in `_sync_bridge`).
- Code changed: **yes** (one call path in `shell.py`, marshaled to main thread).
- Crash status: **hardened, NOT proven fixed.** Do not claim fixed.
- rc1 and rc2 unchanged; rc3 remains diagnostic-only. No upload/tag/proof.
- Next reproduction step: run `C:\Users\KickA\Desktop\CacheVault\dist\CacheVault.exe`
  (rc3), reproduce the photo/screenshot flow, and send `crash_native.log`.
