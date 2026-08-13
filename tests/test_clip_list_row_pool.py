"""Deterministic reuse tests A-M for ClipList row pooling.

Navigation used to destroy every row and rebuild it: ClipList.clear() tore down
~48 widgets per row, which on a 120-row view is a multi-second synchronous
freeze. Pooling replaces that with rebinding an existing row tree in place.

What each test has to prove is therefore not "the list shows the right clips"
(true before pooling too) but "the same widget tree is still there afterwards".
Row reuse is asserted by *slot identity* wherever possible -- the _RowSlot
object and its .row widget must be the same Python objects across a
navigation. That is a direct observation of the thing being claimed, and
unlike the pool counters it cannot be satisfied by a rebuild that happens to
produce equal numbers. See test_l for what the counters do and do not report.

Every test here fails on parent a40f20f, where _RowSlot, pool_stats() and
dispose_pool() do not exist at all (the module has no pooling API to import),
so the file cannot even be collected there. That is verified in the control
worktree rather than asserted here.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cache_vault.core import clip_metadata, models
from cache_vault.core.models import Clip, now_iso
from cache_vault.ui.clip_list import (
    POOL_USER_CEILING,
    ROW_POOL_CAP,
    ClipList,
    _is_packed,
)

# Render batches are chunked across after(5) ticks, so a render is not finished
# when render_batched() returns. _render() below drives it to real completion.
_PUMP_LIMIT = 20_000


class _Event:
    """Minimal stand-in for a Tk event.

    state must be a real int: the click handler tests it against the Ctrl and
    Shift masks, and a MagicMock would satisfy both and silently route a plain
    click into Ctrl+click's toggle path.
    """

    def __init__(self, state: int = 0, x_root: int = 0, y_root: int = 0):
        self.state = state
        self.x_root = x_root
        self.y_root = y_root


def _clip(**kw) -> Clip:
    """Build a Clip using only fields the real 29-field dataclass defines."""
    base = {
        "id": "abc123",
        "content_type": "text",
        "content": "hello",
        "preview": "hello",
        "classification": models.CLASS_PLAIN,
        "title": "",
        "source_app": "test",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    base.update(kw)
    return Clip(**base)


def _clips(n: int, tag: str) -> list[Clip]:
    return [_clip(id=f"{tag}{i}", content=f"{tag} content {i}",
                  preview=f"{tag} preview {i}", title=f"{tag.title()} {i}")
            for i in range(n)]


def _render(cl: ClipList, clips: list[Clip], **kw) -> None:
    """Drive render_batched to genuine completion.

    Completion is observed through the on_complete callback the production
    code already fires, not by guessing at elapsed time or batch counts.
    """
    done: list[int] = []
    cl.render_batched(list(clips), on_complete=lambda: done.append(1), **kw)
    for _ in range(_PUMP_LIMIT):
        if done:
            break
        cl.update()
    assert done, "render_batched never signalled completion"
    assert cl._render_job is None, "a render job was still pending at completion"


@pytest.fixture
def cl(tk_root):
    lst = ClipList(tk_root, on_select=MagicMock())
    lst.pack(fill="both", expand=True)
    yield lst
    try:
        lst.destroy()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# A -- a same-length navigation reuses every row tree in place.
# ---------------------------------------------------------------------------

def test_a_same_length_reuses_every_row(cl):
    _render(cl, _clips(5, "old"))
    before = list(cl._active_slots)
    before_rows = [s.row for s in before]
    assert len(before) == 5
    cl.reset_pool_stats()

    _render(cl, _clips(5, "new"))
    after = list(cl._active_slots)

    # The identity claim: same slot objects, same widgets, same order.
    assert after == before, "every slot object must survive a same-length nav"
    assert [s.row for s in after] == before_rows, "row widgets must be reused"

    stats = cl.pool_stats()
    assert stats["created"] == 0, "no row may be built for a same-length nav"
    assert stats["destroyed"] == 0, "no row may be destroyed for a same-length nav"
    assert stats["active"] == 5

    # Reused rows show the new content, not the previous occupant's.
    for i, slot in enumerate(after):
        assert slot.clip.id == f"new{i}"
        assert slot.title_lbl.cget("text") == f"New {i}"


# ---------------------------------------------------------------------------
# B -- surplus rows are pooled, not destroyed, when fewer clips render.
# ---------------------------------------------------------------------------

def test_b_fewer_clips_hides_surplus_rows(cl):
    _render(cl, _clips(5, "a"))
    kept = list(cl._active_slots[:2])
    cl.reset_pool_stats()

    _render(cl, _clips(2, "b"))

    stats = cl.pool_stats()
    assert stats["active"] == 2, "only 2 rows should remain active"
    assert list(cl._active_slots) == kept, "the surviving rows keep their position"
    assert stats["hidden"] == 3, "the 3 surplus rows should be pooled"
    assert stats["destroyed"] == 0, "surplus rows must not be destroyed"
    assert stats["free"] == 3
    assert stats["retained"] == 5, "the pool still owns all 5 trees"


# ---------------------------------------------------------------------------
# C -- a deficit is filled from the free pool before anything is built.
# ---------------------------------------------------------------------------

def test_c_more_clips_reuses_pooled_rows_before_building(cl):
    _render(cl, _clips(5, "a"))
    _render(cl, _clips(2, "b"))          # 2 active, 3 pooled
    assert cl.pool_stats()["free"] == 3
    cl.reset_pool_stats()

    _render(cl, _clips(5, "c"))          # needs 3 more: all 3 come from the pool

    stats = cl.pool_stats()
    assert stats["active"] == 5
    assert stats["reused"] == 3, "the 3 extra rows must come from the pool"
    assert stats["created"] == 0, "nothing may be built while the pool has rows"
    assert stats["free"] == 0


def test_c2_growing_past_the_pool_builds_only_the_shortfall(cl):
    _render(cl, _clips(2, "a"))
    cl.reset_pool_stats()

    _render(cl, _clips(6, "b"))          # 2 reused in place, 4 genuinely new

    stats = cl.pool_stats()
    assert stats["active"] == 6
    assert stats["created"] == 4, "only the shortfall may be built"
    assert stats["destroyed"] == 0


# ---------------------------------------------------------------------------
# D -- rebinding replaces every piece of clip-owned state.
# ---------------------------------------------------------------------------

def test_d_rebind_replaces_all_clip_state(cl):
    _render(cl, _clips(3, "old"))
    _render(cl, [_clip(id="x0", content="alpha", preview="alpha preview",
                       title="Alpha Title", is_pinned=True)])

    slot = cl._active_slots[0]
    assert slot.clip.id == "x0"
    assert slot.title_lbl.cget("text") == "Alpha Title"
    assert "alpha preview" in slot.preview_lbl.cget("text")
    # Nothing from the previous occupant may survive on the reused tree.
    assert "Old 0" not in slot.title_lbl.cget("text")
    assert "old content 0" not in slot.preview_lbl.cget("text")


# ---------------------------------------------------------------------------
# E -- the trail (star / collection / hash) is resynced on rebind.
# ---------------------------------------------------------------------------

def test_e_trail_synced_on_rebind(cl):
    _render(cl, _clips(3, "a"))
    assert cl._active_slots[0].trail_state == ()

    _render(cl, [_clip(id="big", content="big", preview="big", title="Big",
                       is_pinned=True, collection="MyColl",
                       content_hash="deadbeef")])
    slot = cl._active_slots[0]
    assert slot.trail_state == ("star", "collection", "hash")
    for attr in ("star_lbl", "collection_lbl", "hash_lbl"):
        assert _is_packed(getattr(slot, attr)), f"{attr} should be shown"

    # Back to a plain clip: the whole trail must come off the reused row.
    _render(cl, _clips(1, "plain"))
    slot = cl._active_slots[0]
    assert slot.trail_state == (), "trail must be empty for a plain clip"
    for attr in ("star_lbl", "collection_lbl", "hash_lbl"):
        assert not _is_packed(getattr(slot, attr)), f"{attr} should be hidden"


# ---------------------------------------------------------------------------
# F -- label chips are resynced on rebind and their widgets are pooled too.
# ---------------------------------------------------------------------------

def test_f_chips_synced_on_rebind(cl, monkeypatch):
    monkeypatch.setattr(
        clip_metadata, "labels_for_clip",
        lambda c: ["LabelA", "LabelB"] if c.id == "with_labels" else [],
    )

    _render(cl, [_clip(id="plain", content="x", preview="x")])
    assert cl._active_slots[0].chip_slots == []

    _render(cl, [_clip(id="with_labels", content="y", preview="y")])
    slot = cl._active_slots[0]
    assert len(slot.chip_slots) == 2
    assert _is_packed(slot.chip_slots[0][0])
    assert slot.chip_slots[0][2].cget("text") == "LabelA"
    assert slot.chip_slots[1][2].cget("text") == "LabelB"
    chip_widgets = [c[0] for c in slot.chip_slots]

    # Back to an unlabelled clip: chips unpacked but retained for reuse.
    _render(cl, [_clip(id="plain", content="x", preview="x")])
    slot = cl._active_slots[0]
    assert len(slot.chip_slots) == 2, "chip widgets survive for reuse"
    assert [c[0] for c in slot.chip_slots] == chip_widgets, "same chip widgets"
    assert not _is_packed(slot.chip_slots[0][0]), "chips must be hidden"
    assert not _is_packed(slot.chip_slots[1][0])


# ---------------------------------------------------------------------------
# G -- selection styling is repainted on rebind.
# ---------------------------------------------------------------------------

def test_g_selection_repainted_on_rebind(cl):
    clips = _clips(3, "a")
    _render(cl, clips)
    cl.set_selected_ids([clips[0].id])
    slot0 = cl._active_slots[0]
    # The badge text is static; being *packed* is what shows selection.
    assert _is_packed(slot0.selected_badge), "row 0 should show as selected"

    cl.clear_selection()
    _render(cl, _clips(3, "b"))

    slot = cl._active_slots[0]
    assert slot is slot0, "row 0 was reused"
    assert not _is_packed(slot.selected_badge), (
        "the reused row must not still look selected")
    assert not _is_packed(slot.action_bar), (
        "the reused row must not keep the selected row's action bar")
    assert slot.action_bar_clip_id is None


# ---------------------------------------------------------------------------
# H -- dispose_pool() is a real destruction path.
# ---------------------------------------------------------------------------

def test_h_dispose_pool_destroys_everything(cl):
    _render(cl, _clips(5, "a"))
    _render(cl, _clips(2, "b"))          # 2 active + 3 pooled
    assert cl.pool_stats()["retained"] == 5
    rows = [s.row for s in cl._active_slots] + [s.row for s in cl._free_slots]

    cl.dispose_pool()

    stats = cl.pool_stats()
    assert stats["active"] == 0
    assert stats["free"] == 0
    assert stats["retained"] == 0
    for row in rows:
        assert not row.winfo_exists(), "every pooled tree must be destroyed"


# ---------------------------------------------------------------------------
# I -- the USER-object ceiling stays inside the process quota.
# ---------------------------------------------------------------------------

def test_i_user_ceiling_is_within_quota():
    # Measured quota on the target machine is 10,000 USER objects per process
    # (registry USERProcessHandleQuota); the ceiling must leave headroom for
    # menus, dialogs and the rest of the shell.
    assert 0 < POOL_USER_CEILING <= 10_000


# ---------------------------------------------------------------------------
# J -- a released row is inert, not merely invisible.
# ---------------------------------------------------------------------------

def test_j_released_row_has_no_stale_content(cl):
    secret = "SECRET-PRIVATE-CLIP-BODY"
    _render(cl, [_clip(id=f"s{i}", content=secret, preview=secret,
                       title=secret, collection="Private",
                       content_hash="abc") for i in range(5)])

    _render(cl, [])                       # e.g. a filter that matches nothing

    assert cl.pool_stats()["active"] == 0
    assert cl.pool_stats()["free"] == 5

    for slot in cl._free_slots:
        assert slot.clip is None, "a released row must not reference its clip"
        assert slot.title_lbl.cget("text") == ""
        assert slot.preview_lbl.cget("text") == ""
        assert slot.meta_lbl.cget("text") == ""
        assert slot.badge_lbl.cget("text") == ""
        assert slot.trail_state == ()
        for attr in ("star_lbl", "collection_lbl", "hash_lbl"):
            lbl = getattr(slot, attr)
            if lbl is not None and lbl.winfo_exists():
                assert lbl.cget("text") == "", f"{attr} still holds text"
        for _chip, _dot, text in slot.chip_slots:
            assert text.cget("text") == "", "a chip still holds its label"


def test_j2_no_pooled_widget_anywhere_still_shows_the_clip(cl):
    """Belt-and-braces: walk the real widget tree, not just the slot handles."""
    secret = "SECRET-PRIVATE-CLIP-BODY"
    _render(cl, [_clip(id=f"s{i}", content=secret, preview=secret, title=secret)
                 for i in range(4)])
    _render(cl, [])

    def texts(widget):
        found = []
        for child in widget.winfo_children():
            try:
                value = child.cget("text")
            except Exception:  # noqa: BLE001
                value = None
            if isinstance(value, str) and value:
                found.append(value)
            found.extend(texts(child))
        return found

    assert secret not in texts(cl), "clip text is still discoverable in the tree"


# ---------------------------------------------------------------------------
# K -- event bindings resolve the current occupant after rebind.
# ---------------------------------------------------------------------------

def test_k_event_bindings_resolve_correct_clip(cl):
    first = _clips(3, "a")
    _render(cl, first)
    slot0 = cl._active_slots[0]

    _render(cl, [_clip(id="rebound", content="rebound", preview="rebound")])
    slot = cl._active_slots[0]

    assert slot is slot0, "the first row was reused, not replaced"
    assert slot.clip.id == "rebound", "slot.clip must track the new occupant"
    assert slot.clip is not first[0]

    # A click on the reused row must select the new clip, not the old one.
    # The handlers were bound once at row creation and were never reinstalled,
    # so this is what proves they resolve the occupant through the slot.
    on_select = cl._on_select
    on_select.reset_mock()
    cl._slot_click(_Event(), slot)
    assert on_select.call_count == 1
    assert on_select.call_args[0][0].id == "rebound"


def test_k2_released_row_click_is_inert(cl):
    """A pooled row must not act on the clip it used to hold."""
    _render(cl, _clips(3, "a"))
    slot = cl._active_slots[-1]
    _render(cl, _clips(1, "b"))          # slot is released to the pool

    assert slot in cl._free_slots
    assert slot.clip is None
    cl._on_select.reset_mock()
    assert cl._slot_click(_Event(), slot) == "break"
    assert cl._on_select.call_count == 0, "a pooled row must ignore clicks"


# ---------------------------------------------------------------------------
# L -- what the pool counters do and do not report.
# ---------------------------------------------------------------------------

def test_l_pool_stats_counters(cl):
    _render(cl, _clips(5, "a"))
    stats = cl.pool_stats()
    assert stats["created"] == 5
    assert stats["reused"] == 0          # nothing was in the pool to reuse
    assert stats["active"] == 5
    assert stats["high_water"] == 5

    # Rows released to the pool and then taken back out are counted as reused.
    _render(cl, _clips(2, "b"))
    cl.reset_pool_stats()
    _render(cl, _clips(5, "c"))
    stats = cl.pool_stats()
    assert stats["reused"] == 3
    assert stats["created"] == 0
    assert stats["high_water"] == 5, "high_water is not cleared by a reset"


def test_l2_in_place_rebind_is_reported_separately(cl):
    """A same-length navigation reuses every row *in place*.

    Those rows never reach the free pool, so _acquire_slot never sees them and
    'reused' cannot report them -- which once left the most common transition
    there is showing zero on every counter despite reusing all 120 rows. They
    are counted as 'rebound' instead, keeping 'reused' meaning strictly "taken
    back out of the free pool".
    """
    _render(cl, _clips(20, "a"))
    slots = list(cl._active_slots)
    cl.reset_pool_stats()

    _render(cl, _clips(20, "b"))

    assert list(cl._active_slots) == slots, "every row really was reused"
    stats = cl.pool_stats()
    assert stats["rebound"] == 20, "in-place reuse must be reported"
    assert stats["created"] == 0
    assert stats["reused"] == 0, "'reused' stays pool-refill only"
    assert stats["hidden"] == 0
    assert stats["destroyed"] == 0


def test_l3_rebound_counts_only_rows_reused_in_place(cl):
    """Growing from the free pool reports 'reused'; the rows already on screen
    report 'rebound'. The two must not double-count."""
    _render(cl, _clips(5, "a"))
    _render(cl, _clips(2, "b"))          # 2 active, 3 pooled
    cl.reset_pool_stats()

    _render(cl, _clips(5, "c"))          # 2 rebound in place + 3 out of pool

    stats = cl.pool_stats()
    assert stats["rebound"] == 2
    assert stats["reused"] == 3
    assert stats["created"] == 0
    assert stats["active"] == 5


# ---------------------------------------------------------------------------
# Navigation is atomic: no row may show the previous query.
# ---------------------------------------------------------------------------

def _visible_title(slot):
    """The title the underlying tkinter.Label really holds.

    Read through the private Tk widget rather than CTkLabel.cget so this is an
    observation of what is on screen, independent of the cached value that
    _set() consults when it decides whether a configure can be skipped.
    """
    inner = getattr(slot.title_lbl, "_label", None)
    return inner.cget("text") if inner is not None else slot.title_lbl.cget("text")


def test_navigation_is_atomic_no_stale_rows_on_return(cl):
    """When render_batched returns, every reusable row already shows the new
    query.

    Chunking the rebind pass across after() ticks was measured as an
    alternative: it cut the synchronous cost from ~30ms to ~2ms but left 112
    of 120 rows displaying the previous query for ~108ms. Rebinding is cheap
    enough that this is not a trade worth making, and this test is what stops
    it being made by accident.
    """
    _render(cl, _clips(40, "old"))
    assert all(_visible_title(s).startswith("Old") for s in cl._active_slots)

    # Deliberately NOT pumped: inspect the moment control comes back.
    cl.render_batched(_clips(40, "new"))
    cl.update_idletasks()

    stale = [s for s in cl._active_slots if _visible_title(s).startswith("Old")]
    assert stale == [], (
        f"{len(stale)} rows still showed the previous query when "
        "render_batched returned")


def test_unchanged_properties_are_not_reconfigured(cl):
    """The rebind stays exhaustive, but skips Tk calls that change nothing.

    Re-rendering the identical clips must therefore issue no property sets at
    all, while a real content change must still be applied.
    """
    clips = _clips(10, "a")
    _render(cl, clips)

    import customtkinter as ctk

    seen: list[tuple[str, object]] = []
    real = ctk.CTkLabel.configure

    def spy(self, require_redraw=False, **kwargs):
        seen.extend(kwargs.items())
        return real(self, require_redraw=require_redraw, **kwargs)

    ctk.CTkLabel.configure = spy
    try:
        _render(cl, [_clip(id=c.id, content=c.content, preview=c.preview,
                           title=c.title) for c in clips])
        unchanged = list(seen)

        seen.clear()
        _render(cl, _clips(10, "b"))
        changed = list(seen)
    finally:
        ctk.CTkLabel.configure = real

    assert unchanged == [], (
        f"re-rendering identical clips still set {len(unchanged)} properties")
    assert any(k == "text" for k, _v in changed), (
        "a real content change must still reach the widget")


def test_all_groups_collapsed_completes(cl):
    """Every group collapsed means real clips but zero rows.

    render_batched must still complete rather than indexing into the empty row
    list -- the path that produced an IndexError while the rebind pass was
    being restructured.
    """
    clips = _clips(6, "a")
    _render(cl, clips, group_by="date")
    assert cl._active_slots, "sanity: grouped render produced rows"

    # Collapse every group that the grouped render produced.
    from cache_vault.core import grouping
    for title in grouping.group_clips(clips, "date"):
        cl._collapsed_groups.add(("date", title))

    _render(cl, clips, group_by="date")
    assert cl.pool_stats()["active"] == 0, "no rows while all groups collapsed"


# ---------------------------------------------------------------------------
# M -- the "+N more" footer survives pool cycling and always shows the
#      current count.
# ---------------------------------------------------------------------------

def test_m_more_footer_survives_pool_cycle(cl):
    _render(cl, _clips(5, "a"), more_count=42)
    assert cl._more_label is not None
    assert "42" in cl._more_label.cget("text")
    label = cl._more_label

    _render(cl, _clips(2, "b"), more_count=7)
    assert cl._more_label is label, "the footer widget is reused"
    assert "7" in cl._more_label.cget("text")
    assert "42" not in cl._more_label.cget("text")

    # A render with nothing held back must take the footer off screen.
    _render(cl, _clips(2, "c"), more_count=0)
    assert not _is_packed(cl._more_label)


# ---------------------------------------------------------------------------
# Cap guard -- the pool may never retain more rows than the view can show.
# ---------------------------------------------------------------------------

def test_pool_cap_matches_shell_constant():
    from cache_vault.ui.shell import MAX_VISIBLE_CLIPS
    assert ROW_POOL_CAP == MAX_VISIBLE_CLIPS, (
        f"ROW_POOL_CAP ({ROW_POOL_CAP}) != MAX_VISIBLE_CLIPS "
        f"({MAX_VISIBLE_CLIPS})")


def test_pool_never_retains_more_than_the_cap(cl):
    """The free pool is bounded: rows beyond the cap are destroyed, not kept."""
    _render(cl, _clips(ROW_POOL_CAP + 10, "a"))
    assert cl.pool_stats()["active"] == ROW_POOL_CAP + 10

    _render(cl, [])

    stats = cl.pool_stats()
    assert stats["free"] <= ROW_POOL_CAP, "the free pool must respect the cap"
    assert stats["destroyed"] >= 10, "rows beyond the cap must be destroyed"
