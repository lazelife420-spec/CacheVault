"""Vault Macros — saved macro/snippet vault with Macro Safes and smart filters.

Macro Safes are logical groupings only — not encrypted containers.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable

from . import models, safe_io

# --- Trigger / output --------------------------------------------------------
TRIGGER_NONE = "none"
TRIGGER_TEXT_SHORTCUT = "text_shortcut"
TRIGGER_HOTKEY = "hotkey"
TRIGGER_MENU_ONLY = "menu_only"

TRIGGER_TYPES = (
    TRIGGER_NONE,
    TRIGGER_TEXT_SHORTCUT,
    TRIGGER_HOTKEY,
    TRIGGER_MENU_ONLY,
)

OUTPUT_CLIPBOARD_PASTE = "clipboard_paste"
OUTPUT_KEYSTROKE = "keystroke"

OUTPUT_MODES = (OUTPUT_CLIPBOARD_PASTE, OUTPUT_KEYSTROKE)

# --- Smart types (classification suggestions) --------------------------------
SMART_EMAIL_TEMPLATE = "email_template"
SMART_SAVED_REPLY = "saved_reply"
SMART_SIGNATURE = "signature"
SMART_ADDRESS_CONTACT = "address_contact"
SMART_CODE_SNIPPET = "code_snippet"
SMART_COMMAND = "command"
SMART_FORM_FILLIN = "form_fillin"
SMART_LINK = "link"
SMART_PERSONAL_TEMPLATE = "personal_template"

SMART_TYPES = (
    SMART_EMAIL_TEMPLATE,
    SMART_SAVED_REPLY,
    SMART_SIGNATURE,
    SMART_ADDRESS_CONTACT,
    SMART_CODE_SNIPPET,
    SMART_COMMAND,
    SMART_FORM_FILLIN,
    SMART_LINK,
    SMART_PERSONAL_TEMPLATE,
)

SMART_TYPE_LABELS: dict[str, str] = {
    SMART_EMAIL_TEMPLATE: "Email Templates",
    SMART_SAVED_REPLY: "Saved Replies",
    SMART_SIGNATURE: "Signatures",
    SMART_ADDRESS_CONTACT: "Addresses / Contact",
    SMART_CODE_SNIPPET: "Code Snippets",
    SMART_COMMAND: "Commands",
    SMART_FORM_FILLIN: "Forms / Fill-ins",
    SMART_LINK: "Links",
    SMART_PERSONAL_TEMPLATE: "Personal Templates",
}

# --- Macro Safes -------------------------------------------------------------
MACRO_SAFE_PREFIX = "macro_safe:"
BUILTIN_MACRO_SAFE_MACRO = "macro-safe"
BUILTIN_MACRO_SAFE_EMAIL = "email-templates"
BUILTIN_MACRO_SAFE_REPLIES = "saved-replies"
BUILTIN_MACRO_SAFE_CODE = "code-snippets"
BUILTIN_MACRO_SAFE_COMMANDS = "commands"
BUILTIN_MACRO_SAFE_PERSONAL = "personal-templates"

STARTER_MACRO_SAFES: tuple[tuple[str, str], ...] = (
    (BUILTIN_MACRO_SAFE_MACRO, "Macro Safe"),
    (BUILTIN_MACRO_SAFE_EMAIL, "Email Templates"),
    (BUILTIN_MACRO_SAFE_REPLIES, "Saved Replies"),
    (BUILTIN_MACRO_SAFE_CODE, "Code Snippets"),
    (BUILTIN_MACRO_SAFE_COMMANDS, "Commands"),
    (BUILTIN_MACRO_SAFE_PERSONAL, "Personal Templates"),
)

# --- Smart filter keys -------------------------------------------------------
MACRO_FILTER_PREFIX = "macro:"
MACRO_FILTER_ALL = "macro:all"
MACRO_FILTER_FAVORITES = "macro:favorites"
MACRO_FILTER_RECENTLY_USED = "macro:recently_used"
MACRO_FILTER_RECENTLY_CREATED = "macro:recently_created"
MACRO_FILTER_RECENTLY_EDITED = "macro:recently_edited"
MACRO_FILTER_DISABLED = "macro:disabled"
MACRO_FILTER_BROKEN = "macro:broken"
MACRO_FILTER_HOTKEY_CONFLICTS = "macro:hotkey_conflicts"
MACRO_FILTER_NO_TRIGGER = "macro:no_trigger"
MACRO_FILTER_TEXT_SHORTCUTS = "macro:text_shortcuts"
MACRO_FILTER_HOTKEY_MACROS = "macro:hotkey_macros"
MACRO_FILTER_MENU_ONLY = "macro:menu_only"
MACRO_FILTER_CLIPBOARD_MODE = "macro:clipboard_paste_mode"
MACRO_FILTER_KEYSTROKE_MODE = "macro:keystroke_mode"
MACRO_FILTER_SENSITIVE = "macro:sensitive_confirm"
MACRO_FILTER_HAS_RECEIPTS = "macro:has_receipts"
MACRO_FILTER_NEVER_USED = "macro:never_used"
MACRO_FILTER_FAILED_LAST = "macro:failed_last_run"
MACRO_FILTER_IMPORTED = "macro:imported"
MACRO_FILTER_EXPORTED = "macro:exported"
MACRO_FILTER_MISSING_SAFE = "macro:missing_safe"

CORE_MACRO_FILTERS: tuple[tuple[str, str], ...] = (
    (MACRO_FILTER_ALL, "All Macros"),
    (MACRO_FILTER_FAVORITES, "Favorites"),
    (MACRO_FILTER_RECENTLY_USED, "Recently Used"),
    (MACRO_FILTER_RECENTLY_CREATED, "Recently Created"),
    (MACRO_FILTER_RECENTLY_EDITED, "Recently Edited"),
    (MACRO_FILTER_DISABLED, "Disabled"),
    (MACRO_FILTER_BROKEN, "Broken / Needs Attention"),
    (MACRO_FILTER_HOTKEY_CONFLICTS, "Hotkey Conflicts"),
    (MACRO_FILTER_NO_TRIGGER, "No Trigger Assigned"),
    (MACRO_FILTER_TEXT_SHORTCUTS, "Text Shortcuts"),
    (MACRO_FILTER_HOTKEY_MACROS, "Hotkey Macros"),
    (MACRO_FILTER_MENU_ONLY, "Menu Only"),
    (MACRO_FILTER_CLIPBOARD_MODE, "Clipboard Paste Mode"),
    (MACRO_FILTER_KEYSTROKE_MODE, "Keystroke Mode"),
)

CONTENT_MACRO_FILTERS: tuple[tuple[str, str], ...] = tuple(
    (f"macro:type:{t}", SMART_TYPE_LABELS[t]) for t in SMART_TYPES
)

SAFETY_MACRO_FILTERS: tuple[tuple[str, str], ...] = (
    (MACRO_FILTER_SENSITIVE, "Sensitive / Confirm Before Use"),
    (MACRO_FILTER_HAS_RECEIPTS, "Has Receipts"),
    (MACRO_FILTER_NEVER_USED, "Never Used"),
    (MACRO_FILTER_FAILED_LAST, "Failed Last Run"),
    (MACRO_FILTER_IMPORTED, "Imported"),
    (MACRO_FILTER_EXPORTED, "Exported"),
    (MACRO_FILTER_MISSING_SAFE, "Missing Safe"),
)

RESERVED_HOTKEYS = frozenset({
    "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+z", "ctrl+y", "ctrl+a",
    "ctrl+shift+v", "ctrl+shift+c", "ctrl+alt+c", "ctrl+shift+x",
    "win+v", "alt+tab", "ctrl+shift+m",
})

DEFAULT_MACRO_MENU_HOTKEY = "ctrl+shift+m"


def default_macros_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "CacheVault" / "macros.json"


def normalize_hotkey(spec: str) -> str:
    return "+".join(p.strip().lower() for p in (spec or "").split("+") if p.strip())


@dataclass
class MacroSafe:
    id: str
    name: str
    builtin: bool = False
    created_at: str = field(default_factory=models.now_iso)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "builtin": self.builtin,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MacroSafe:
        return cls(
            id=data["id"],
            name=data["name"],
            builtin=bool(data.get("builtin", False)),
            created_at=data.get("created_at") or models.now_iso(),
        )


class MacroSafeRegistry:
    """Macro Safes — separate from clip capture Safes."""

    _STARTER_IDS = {sid for sid, _ in STARTER_MACRO_SAFES}

    def __init__(self, settings):
        self._settings = settings

    def _user_safes(self) -> list[MacroSafe]:
        raw = getattr(self._settings, "user_macro_safes", None) or []
        out: list[MacroSafe] = []
        for item in raw:
            if isinstance(item, dict) and item.get("id") and item.get("name"):
                out.append(MacroSafe.from_dict(item))
        return out

    def _persist_user(self, safes: list[MacroSafe]) -> None:
        self._settings.user_macro_safes = [s.to_dict() for s in safes if not s.builtin]

    def list_all(self) -> list[MacroSafe]:
        builtins = [
            MacroSafe(id=sid, name=name, builtin=True)
            for sid, name in STARTER_MACRO_SAFES
        ]
        user = [s for s in self._user_safes() if s.id not in self._STARTER_IDS]
        seen = {s.id for s in builtins}
        merged = builtins + [s for s in user if s.id not in seen]
        return merged

    def resolve(self, safe_id: str | None) -> MacroSafe | None:
        sid = (safe_id or "").strip() or BUILTIN_MACRO_SAFE_MACRO
        for s in self.list_all():
            if s.id == sid:
                return s
        return None

    def default_safe(self) -> MacroSafe:
        sid = getattr(self._settings, "default_macro_safe_id", None) or BUILTIN_MACRO_SAFE_MACRO
        return self.resolve(sid) or MacroSafe(
            id=BUILTIN_MACRO_SAFE_MACRO, name="Macro Safe", builtin=True,
        )

    def create(self, name: str, *, safe_id: str | None = None) -> MacroSafe:
        name = (name or "").strip()
        if not name:
            raise ValueError("Macro Safe name required")
        sid = safe_id or uuid.uuid4().hex
        if sid in self._STARTER_IDS:
            existing = self.resolve(sid)
            if existing:
                return existing
        safe = MacroSafe(id=sid, name=name, builtin=sid in self._STARTER_IDS)
        if safe.builtin:
            return safe
        user = self._user_safes()
        if any(s.id == sid for s in user):
            return self.resolve(sid)  # type: ignore[return-value]
        user.append(safe)
        self._persist_user(user)
        return safe

    def ensure_starter_safes(self) -> list[MacroSafe]:
        """Mark starter Macro Safes available once; never overwrite user Safes."""
        if getattr(self._settings, "macro_starter_safes_initialized", False):
            return []
        self._settings.macro_starter_safes_initialized = True
        return [
            MacroSafe(id=sid, name=name, builtin=True)
            for sid, name in STARTER_MACRO_SAFES
        ]

    def filter_key(self, safe_id: str) -> str:
        return f"{MACRO_SAFE_PREFIX}{safe_id}"


@dataclass
class Macro:
    id: str
    name: str
    body: str = ""
    description: str = ""
    safe_id: str = BUILTIN_MACRO_SAFE_MACRO
    smart_type: str = SMART_PERSONAL_TEMPLATE
    trigger_type: str = TRIGGER_MENU_ONLY
    trigger_value: str = ""
    output_mode: str = OUTPUT_CLIPBOARD_PASTE
    enabled: bool = True
    favorite: bool = False
    sensitive_confirm: bool = False
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=models.now_iso)
    updated_at: str = field(default_factory=models.now_iso)
    last_used_at: str | None = None
    run_count: int = 0
    last_run_failed: bool = False
    imported: bool = False
    exported: bool = False
    receipt_count: int = 0
    template_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Macro:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    def content_hash(self) -> str:
        return models.content_hash(self.body or "")


def suggest_smart_type(body: str, name: str = "") -> str:
    """Heuristic suggestion only — user can override."""
    text = (body or "").strip()
    low = text.lower()
    name_low = (name or "").lower()

    if re.match(r"https?://", text, re.I):
        return SMART_LINK
    if "@" in text and re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
        if "signature" in name_low or re.search(r"(regards|sincerely|best,)", low):
            return SMART_SIGNATURE
        return SMART_EMAIL_TEMPLATE
    if re.search(r"\b(thanks for|thank you for|hi there|dear \w+|following up)\b", low):
        return SMART_SAVED_REPLY
    if re.search(r"\b(street|avenue|city|state|zip|postal)\b", low) and text.count("\n") >= 2:
        return SMART_ADDRESS_CONTACT
    if re.search(r"^(sudo|npm |git |cd |python |pip |curl |ssh )", low):
        return SMART_COMMAND
    if re.search(r"[{}();=<>]|def |function |import |class ", text):
        return SMART_CODE_SNIPPET
    if re.search(r"\{\w+\}|\[.*\]", text) and text.count("\n") <= 5:
        return SMART_FORM_FILLIN
    if "signature" in name_low:
        return SMART_SIGNATURE
    return SMART_PERSONAL_TEMPLATE


MACRO_TEMPLATES: dict[str, dict] = {
    "blank": {
        "name": "New blank macro",
        "body": "",
        "smart_type": SMART_PERSONAL_TEMPLATE,
        "description": "Empty macro — add your own text.",
    },
    "email_signature": {
        "name": "Email signature",
        "body": "Best regards,\nYour Name\nYour Title\nyour.email@example.com",
        "smart_type": SMART_SIGNATURE,
        "description": "Standard email signature block.",
    },
    "saved_reply": {
        "name": "Saved reply",
        "body": "Hi,\n\nThanks for reaching out. \n\nBest,\n",
        "smart_type": SMART_SAVED_REPLY,
        "description": "Common reply template.",
    },
    "address_block": {
        "name": "Address / contact block",
        "body": "Your Name\n123 Main Street\nCity, ST 12345\nphone@example.com",
        "smart_type": SMART_ADDRESS_CONTACT,
        "description": "Multiline address or contact info.",
    },
    "code_snippet": {
        "name": "Code snippet",
        "body": "def example():\n    return True\n",
        "smart_type": SMART_CODE_SNIPPET,
        "description": "Code block macro.",
    },
    "command_snippet": {
        "name": "Command snippet",
        "body": "git status",
        "smart_type": SMART_COMMAND,
        "description": "Shell or CLI command.",
    },
    "datetime_snippet": {
        "name": "Date/time snippet",
        "body": "{date} {time}",
        "smart_type": SMART_FORM_FILLIN,
        "description": "Insert date/time placeholders (expand manually).",
    },
    "clipboard_wrapper": {
        "name": "Clipboard wrapper",
        "body": "Before: {clipboard}\nAfter text here.",
        "smart_type": SMART_PERSONAL_TEMPLATE,
        "description": "Wraps current clipboard content with {clipboard}.",
    },
}


class MacroStore:
    """Persisted macro records in macros.json."""

    def __init__(self, path: str | os.PathLike | None = None):
        self._path = Path(path or default_macros_path())

    def load_all(self) -> list[Macro]:
        if not self._path.is_file():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except OSError:
            return []
        except json.JSONDecodeError:
            safe_io.quarantine_corrupt(self._path)  # preserve, don't overwrite
            return []
        items = data.get("macros") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        return [Macro.from_dict(m) for m in items if isinstance(m, dict)]

    def save_all(self, macros: list[Macro]) -> None:
        payload = {"version": 1, "macros": [m.to_dict() for m in macros]}
        safe_io.atomic_write_text(
            self._path, json.dumps(payload, indent=2), keep_backup=True,
        )

    def get(self, macro_id: str) -> Macro | None:
        for m in self.load_all():
            if m.id == macro_id:
                return m
        return None

    def upsert(self, macro: Macro) -> Macro:
        macros = self.load_all()
        macro.updated_at = models.now_iso()
        for i, m in enumerate(macros):
            if m.id == macro.id:
                macros[i] = macro
                self.save_all(macros)
                return macro
        macros.append(macro)
        self.save_all(macros)
        return macro

    def delete(self, macro_id: str) -> bool:
        macros = self.load_all()
        new = [m for m in macros if m.id != macro_id]
        if len(new) == len(macros):
            return False
        self.save_all(new)
        return True


def macro_issues(
    macro: Macro,
    *,
    registry: MacroSafeRegistry,
    all_macros: list[Macro],
    settings,
) -> list[str]:
    issues: list[str] = []
    if not (macro.body or "").strip():
        issues.append("empty_body")
    if macro.trigger_type == TRIGGER_NONE or (
        macro.trigger_type in (TRIGGER_HOTKEY, TRIGGER_TEXT_SHORTCUT)
        and not (macro.trigger_value or "").strip()
    ):
        issues.append("no_trigger")
    if macro.output_mode not in OUTPUT_MODES:
        issues.append("invalid_output_mode")
    if registry.resolve(macro.safe_id) is None:
        issues.append("missing_safe")
    if macro.last_run_failed:
        issues.append("failed_last_run")
    if macro.sensitive_confirm and not getattr(settings, "macro_sensitive_confirmation", True):
        issues.append("sensitive_unsafe_settings")
    hk = normalize_hotkey(macro.trigger_value)
    if macro.trigger_type == TRIGGER_HOTKEY and hk:
        if hk in RESERVED_HOTKEYS:
            issues.append("hotkey_conflict")
        for other in all_macros:
            if other.id == macro.id or other.trigger_type != TRIGGER_HOTKEY:
                continue
            if normalize_hotkey(other.trigger_value) == hk:
                issues.append("hotkey_conflict")
                break
    return issues


def is_broken(macro: Macro, **ctx) -> bool:
    return bool(macro_issues(macro, **ctx))


def has_hotkey_conflict(macro: Macro, **ctx) -> bool:
    return "hotkey_conflict" in macro_issues(macro, **ctx)


def apply_macro_filter(
    macros: list[Macro],
    filter_key: str,
    *,
    registry: MacroSafeRegistry,
    settings,
) -> list[Macro]:
    ctx = {"registry": registry, "all_macros": macros, "settings": settings}
    fk = filter_key or MACRO_FILTER_ALL

    if fk.startswith(MACRO_SAFE_PREFIX):
        sid = fk[len(MACRO_SAFE_PREFIX):]
        return [m for m in macros if m.safe_id == sid]

    if fk.startswith("macro:type:"):
        stype = fk.split(":", 2)[2]
        return [m for m in macros if m.smart_type == stype]

    if fk == MACRO_FILTER_ALL:
        return list(macros)
    if fk == MACRO_FILTER_FAVORITES:
        return [m for m in macros if m.favorite]
    if fk == MACRO_FILTER_RECENTLY_USED:
        used = [m for m in macros if m.last_used_at]
        return sorted(used, key=lambda m: m.last_used_at or "", reverse=True)
    if fk == MACRO_FILTER_RECENTLY_CREATED:
        return sorted(macros, key=lambda m: m.created_at, reverse=True)
    if fk == MACRO_FILTER_RECENTLY_EDITED:
        return sorted(macros, key=lambda m: m.updated_at, reverse=True)
    if fk == MACRO_FILTER_DISABLED:
        return [m for m in macros if not m.enabled]
    if fk == MACRO_FILTER_BROKEN:
        return [m for m in macros if is_broken(m, **ctx)]
    if fk == MACRO_FILTER_HOTKEY_CONFLICTS:
        return [m for m in macros if has_hotkey_conflict(m, **ctx)]
    if fk == MACRO_FILTER_NO_TRIGGER:
        return [m for m in macros if "no_trigger" in macro_issues(m, **ctx)]
    if fk == MACRO_FILTER_TEXT_SHORTCUTS:
        return [m for m in macros if m.trigger_type == TRIGGER_TEXT_SHORTCUT]
    if fk == MACRO_FILTER_HOTKEY_MACROS:
        return [m for m in macros if m.trigger_type == TRIGGER_HOTKEY]
    if fk == MACRO_FILTER_MENU_ONLY:
        return [m for m in macros if m.trigger_type == TRIGGER_MENU_ONLY]
    if fk == MACRO_FILTER_CLIPBOARD_MODE:
        return [m for m in macros if m.output_mode == OUTPUT_CLIPBOARD_PASTE]
    if fk == MACRO_FILTER_KEYSTROKE_MODE:
        return [m for m in macros if m.output_mode == OUTPUT_KEYSTROKE]
    if fk == MACRO_FILTER_SENSITIVE:
        return [m for m in macros if m.sensitive_confirm]
    if fk == MACRO_FILTER_HAS_RECEIPTS:
        return [m for m in macros if m.receipt_count > 0]
    if fk == MACRO_FILTER_NEVER_USED:
        return [m for m in macros if m.run_count == 0 and not m.last_used_at]
    if fk == MACRO_FILTER_FAILED_LAST:
        return [m for m in macros if m.last_run_failed]
    if fk == MACRO_FILTER_IMPORTED:
        return [m for m in macros if m.imported]
    if fk == MACRO_FILTER_EXPORTED:
        return [m for m in macros if m.exported]
    if fk == MACRO_FILTER_MISSING_SAFE:
        return [m for m in macros if "missing_safe" in macro_issues(m, **ctx)]
    return list(macros)


def search_macros(
    macros: list[Macro],
    query: str,
    *,
    registry: MacroSafeRegistry,
    search_content: bool = False,
) -> list[Macro]:
    q = (query or "").strip().lower()
    if not q:
        return macros
    out: list[Macro] = []
    for m in macros:
        safe = registry.resolve(m.safe_id)
        safe_name = (safe.name if safe else "").lower()
        hay = [
            m.name.lower(),
            m.description.lower(),
            m.trigger_value.lower(),
            m.smart_type.lower(),
            safe_name,
            " ".join(t.lower() for t in m.tags),
        ]
        if search_content:
            hay.append(m.body.lower())
        if any(q in part for part in hay if part):
            out.append(m)
    return out


def macro_filter_counts(
    macros: list[Macro],
    *,
    registry: MacroSafeRegistry,
    settings,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    all_filters = CORE_MACRO_FILTERS + CONTENT_MACRO_FILTERS + SAFETY_MACRO_FILTERS
    for key, _label in all_filters:
        counts[key] = len(apply_macro_filter(macros, key, registry=registry, settings=settings))
    for safe in registry.list_all():
        counts[registry.filter_key(safe.id)] = len(
            apply_macro_filter(macros, registry.filter_key(safe.id), registry=registry, settings=settings)
        )
    return counts


def create_from_template(
    template_id: str,
    *,
    safe_id: str | None = None,
    registry: MacroSafeRegistry,
    suggest: bool = True,
) -> Macro:
    tpl = MACRO_TEMPLATES.get(template_id)
    if tpl is None:
        raise ValueError(f"Unknown template: {template_id}")
    body = tpl.get("body", "")
    smart_type = tpl.get("smart_type", SMART_PERSONAL_TEMPLATE)
    if suggest:
        smart_type = suggest_smart_type(body, tpl.get("name", ""))
    sid = safe_id or registry.default_safe().id
    return Macro(
        id=uuid.uuid4().hex,
        name=tpl.get("name", "Macro"),
        body=body,
        description=tpl.get("description", ""),
        safe_id=sid,
        smart_type=smart_type,
        template_id=template_id,
    )


@dataclass
class SetupChoices:
    default_macro_safe_id: str = BUILTIN_MACRO_SAFE_MACRO
    macro_menu_hotkey: str = DEFAULT_MACRO_MENU_HOTKEY
    default_output_mode: str = OUTPUT_CLIPBOARD_PASTE
    text_shortcuts_enabled: bool = True
    macro_hotkeys_enabled: bool = True
    restore_clipboard: bool = False
    sensitive_confirmation: bool = True
    create_starter_safes: bool = True


def complete_macro_setup(
    settings,
    *,
    choices: SetupChoices | None = None,
    record_receipt: Callable[[str, dict], None] | None = None,
) -> dict:
    """First-run setup — never overwrites existing user Macro Safes."""
    choices = choices or SetupChoices()
    registry = MacroSafeRegistry(settings)
    created_safes: list[MacroSafe] = []
    if choices.create_starter_safes:
        created_safes = registry.ensure_starter_safes()

    settings.vault_macros_enabled = True
    settings.default_macro_safe_id = choices.default_macro_safe_id or BUILTIN_MACRO_SAFE_MACRO
    settings.macro_menu_hotkey = choices.macro_menu_hotkey or DEFAULT_MACRO_MENU_HOTKEY
    settings.macro_default_output_mode = choices.default_output_mode
    settings.macro_text_shortcuts_enabled = choices.text_shortcuts_enabled
    settings.macro_hotkeys_enabled = choices.macro_hotkeys_enabled
    settings.macro_restore_clipboard_after_paste = choices.restore_clipboard
    settings.macro_sensitive_confirmation = choices.sensitive_confirmation
    settings.vault_macros_setup_completed = True
    settings.save()

    payload = {
        "action": "vault_macros_setup_completed",
        "timestamp": models.now_iso(),
        "success": True,
        "starter_safes_created": len(created_safes),
        "default_macro_safe_id": settings.default_macro_safe_id,
        "macro_menu_hotkey": settings.macro_menu_hotkey,
    }
    if record_receipt:
        record_receipt("vault_macros_setup_completed", payload)
    return {
        "ok": True,
        "created_safes": [s.to_dict() for s in created_safes],
        "settings": payload,
    }


def build_macro_manifest_entries(macros: list[Macro], registry: MacroSafeRegistry) -> list[dict]:
    """Manifest entries for macro proof-pack export."""
    entries: list[dict] = []
    for m in macros:
        safe = registry.resolve(m.safe_id)
        entries.append({
            "item_type": "vault_macro",
            "macro_id": m.id,
            "name": m.name,
            "safe_id": m.safe_id,
            "safe_name": safe.name if safe else None,
            "smart_type": m.smart_type,
            "smart_type_label": SMART_TYPE_LABELS.get(m.smart_type, m.smart_type),
            "trigger_type": m.trigger_type,
            "trigger_value": m.trigger_value or None,
            "output_mode": m.output_mode,
            "enabled": m.enabled,
            "favorite": m.favorite,
            "sensitive_confirm": m.sensitive_confirm,
            "run_count": m.run_count,
            "receipt_count": m.receipt_count,
            "content_hash": m.content_hash(),
            "includes_macro_body": True,
            "body_length": len(m.body or ""),
            "created_at": m.created_at,
            "updated_at": m.updated_at,
            "last_used_at": m.last_used_at,
            "tags": list(m.tags),
        })
    return entries


def export_macros_proof_pack(
    macros: list[Macro],
    registry: MacroSafeRegistry,
    dest: Path,
    *,
    include_body: bool = True,
) -> dict:
    """Write a macro proof manifest JSON (explicit about body inclusion)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "document_type": "cache_vault_macro_proof_export",
        "macro_count": len(macros),
        "includes_macro_body": include_body,
        "items": [],
    }
    for entry in build_macro_manifest_entries(macros, registry):
        if not include_body:
            entry.pop("content_hash", None)
        manifest["items"].append(entry)
        if include_body:
            m = next((x for x in macros if x.id == entry["macro_id"]), None)
            if m:
                entry["macro_body_included"] = True
                entry["body_preview_length"] = min(len(m.body or ""), 80)
    dest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def inspector_warnings(macro: Macro, **ctx) -> list[str]:
    labels = {
        "hotkey_conflict": "Hotkey conflict",
        "no_trigger": "No trigger assigned",
        "empty_body": "Macro body is empty",
        "missing_safe": "Macro Safe is missing",
        "failed_last_run": "Last run failed",
        "sensitive_unsafe_settings": "Sensitive macro with confirmation disabled globally",
        "invalid_output_mode": "Invalid output mode",
    }
    return [labels[k] for k in macro_issues(macro, **ctx) if k in labels]
