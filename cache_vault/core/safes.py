"""Local vault Safes — named destinations for captured items.

Safes are logical sections in the local vault, not encrypted containers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from . import models

SAFE_DEFAULT = "default"
SAFE_TEMPORARY = "temporary"
SAFE_IGNORE = "ignore"

SAFE_PREFIX = "safe:"
SAFE_WORDING = "Safes organize your vault items. They are not encryption unless encryption is added later."

SAFE_STYLES: dict[str, dict[str, str]] = {
    SAFE_DEFAULT: {"name": "Default Safe", "icon": "◈", "accent": "#1A9E8C", "visual_style": "default"},
    "temporary": {"name": "Temporary Safe", "icon": "◇", "accent": "#C9A24D", "visual_style": "temporary"},
    "receipts": {"name": "Receipts Safe", "icon": "⬢", "accent": "#C9A24D", "visual_style": "receipts"},
    "phone": {"name": "Phone Inbox Safe", "icon": "▣", "accent": "#1A9E8C", "visual_style": "phone"},
    "work": {"name": "Work Safe", "icon": "▤", "accent": "#7A848E", "visual_style": "work"},
    "personal": {"name": "Personal Safe", "icon": "◆", "accent": "#9B7BC9", "visual_style": "personal"},
    "code": {"name": "Code Safe", "icon": "</>", "accent": "#5CB85C", "visual_style": "code"},
    "screenshots": {"name": "Screenshots Safe", "icon": "▦", "accent": "#4DA3C9", "visual_style": "screenshots"},
    "links": {"name": "Links Safe", "icon": "🔗", "accent": "#1A9E8C", "visual_style": "links"},
}

_BUILTIN: dict[str, str] = {
    SAFE_DEFAULT: "Default Safe",
    SAFE_TEMPORARY: "Temporary Safe",
    SAFE_IGNORE: "Ignore / Do Not Save",
}


@dataclass
class Safe:
    id: str
    name: str
    builtin: bool = False
    created_at: str = field(default_factory=models.now_iso)
    icon: str = "◈"
    accent: str = "#1A9E8C"
    description: str = ""
    default_capture: str = models.CAPTURE_AUTO
    show_in_sidebar: bool = True
    favorite: bool = False
    receipt_label: str = ""
    visual_style: str = "default"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "builtin": self.builtin,
            "created_at": self.created_at,
            "icon": self.icon,
            "accent": self.accent,
            "description": self.description,
            "default_capture": self.default_capture,
            "show_in_sidebar": self.show_in_sidebar,
            "favorite": self.favorite,
            "receipt_label": self.receipt_label,
            "visual_style": self.visual_style,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Safe:
        style = SAFE_STYLES.get(str(data.get("visual_style") or "default"), SAFE_STYLES[SAFE_DEFAULT])
        return cls(
            id=data["id"],
            name=data["name"],
            builtin=bool(data.get("builtin", False)),
            created_at=data.get("created_at") or models.now_iso(),
            icon=str(data.get("icon") or style["icon"]),
            accent=str(data.get("accent") or style["accent"]),
            description=str(data.get("description") or ""),
            default_capture=str(data.get("default_capture") or models.CAPTURE_AUTO),
            show_in_sidebar=bool(data.get("show_in_sidebar", True)),
            favorite=bool(data.get("favorite", False)),
            receipt_label=str(data.get("receipt_label") or ""),
            visual_style=str(data.get("visual_style") or style["visual_style"]),
        )


class SafeRegistry:
    """Resolve Safes from settings + built-in defaults."""

    def __init__(self, settings):
        self._settings = settings

    def _user_safes(self) -> list[Safe]:
        raw = getattr(self._settings, "user_safes", None) or []
        out: list[Safe] = []
        for item in raw:
            if isinstance(item, dict) and item.get("id") and item.get("name"):
                out.append(Safe.from_dict(item))
        return out

    def _persist_user(self, safes: list[Safe]) -> None:
        self._settings.user_safes = [s.to_dict() for s in safes if not s.builtin]

    def builtin_safes(self) -> list[Safe]:
        return [
            self._builtin_safe(sid, name)
            for sid, name in _BUILTIN.items()
            if sid != SAFE_IGNORE
        ]

    def _builtin_safe(self, sid: str, name: str) -> Safe:
        style = SAFE_STYLES.get(sid, SAFE_STYLES[SAFE_DEFAULT])
        return Safe(
            id=sid,
            name=name,
            builtin=True,
            icon=style["icon"],
            accent=style["accent"],
            visual_style=style["visual_style"],
        )

    def list_all(self, *, include_ignore: bool = False) -> list[Safe]:
        builtins = [
            self._builtin_safe(sid, name)
            for sid, name in _BUILTIN.items()
            if include_ignore or sid != SAFE_IGNORE
        ]
        user = [s for s in self._user_safes() if s.show_in_sidebar or include_ignore]
        return builtins + user

    def list_destinations(self) -> list[Safe]:
        """Safes that can receive captured items (excludes Ignore)."""
        return self.list_all(include_ignore=False)

    def resolve(self, safe_id: str | None) -> Safe | None:
        sid = (safe_id or "").strip() or SAFE_DEFAULT
        if sid in _BUILTIN:
            return self._builtin_safe(sid, _BUILTIN[sid])
        for s in self._user_safes():
            if s.id == sid:
                return s
        if sid == SAFE_DEFAULT:
            return Safe(id=SAFE_DEFAULT, name=_BUILTIN[SAFE_DEFAULT], builtin=True)
        return None

    def default_safe(self) -> Safe:
        sid = getattr(self._settings, "default_safe_id", None) or SAFE_DEFAULT
        return self.resolve(sid) or Safe(
            id=SAFE_DEFAULT, name=_BUILTIN[SAFE_DEFAULT], builtin=True,
        )

    def is_ignore(self, safe_id: str | None) -> bool:
        return (safe_id or "").strip() == SAFE_IGNORE

    def create(self, name: str) -> Safe:
        name = (name or "").strip()
        if not name:
            raise ValueError("Safe name required")
        safe = Safe(id=uuid.uuid4().hex, name=name, builtin=False)
        user = self._user_safes()
        user.append(safe)
        self._persist_user(user)
        return safe

    def update_customization(self, safe_id: str, **changes) -> Safe | None:
        if safe_id in _BUILTIN:
            return None
        user = self._user_safes()
        for i, safe in enumerate(user):
            if safe.id != safe_id:
                continue
            data = safe.to_dict()
            for key in (
                "name",
                "icon",
                "accent",
                "description",
                "default_capture",
                "show_in_sidebar",
                "favorite",
                "receipt_label",
                "visual_style",
            ):
                if key in changes:
                    data[key] = changes[key]
            updated = Safe.from_dict(data)
            user[i] = updated
            self._persist_user(user)
            return updated
        return None

    def rename(self, safe_id: str, name: str) -> Safe | None:
        name = (name or "").strip()
        if not name or safe_id in _BUILTIN:
            return None
        user = self._user_safes()
        for i, s in enumerate(user):
            if s.id == safe_id:
                data = s.to_dict()
                data["name"] = name
                user[i] = Safe.from_dict(data)
                self._persist_user(user)
                return user[i]
        return None

    def delete(self, safe_id: str) -> bool:
        if safe_id in _BUILTIN:
            return False
        user = [s for s in self._user_safes() if s.id != safe_id]
        if len(user) == len(self._user_safes()):
            return False
        self._persist_user(user)
        return True

    def filter_key(self, safe_id: str) -> str:
        return f"{SAFE_PREFIX}{safe_id}"

    def safe_id_from_filter(self, filter_name: str) -> str | None:
        if filter_name.startswith(SAFE_PREFIX):
            return filter_name[len(SAFE_PREFIX):]
        return None
