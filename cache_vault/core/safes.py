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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "builtin": self.builtin,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Safe:
        return cls(
            id=data["id"],
            name=data["name"],
            builtin=bool(data.get("builtin", False)),
            created_at=data.get("created_at") or models.now_iso(),
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
            Safe(id=sid, name=name, builtin=True)
            for sid, name in _BUILTIN.items()
            if sid != SAFE_IGNORE
        ]

    def list_all(self, *, include_ignore: bool = False) -> list[Safe]:
        builtins = [
            Safe(id=sid, name=name, builtin=True)
            for sid, name in _BUILTIN.items()
            if include_ignore or sid != SAFE_IGNORE
        ]
        user = self._user_safes()
        return builtins + user

    def list_destinations(self) -> list[Safe]:
        """Safes that can receive captured items (excludes Ignore)."""
        return self.list_all(include_ignore=False)

    def resolve(self, safe_id: str | None) -> Safe | None:
        sid = (safe_id or "").strip() or SAFE_DEFAULT
        if sid in _BUILTIN:
            return Safe(id=sid, name=_BUILTIN[sid], builtin=True)
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

    def rename(self, safe_id: str, name: str) -> Safe | None:
        name = (name or "").strip()
        if not name or safe_id in _BUILTIN:
            return None
        user = self._user_safes()
        for i, s in enumerate(user):
            if s.id == safe_id:
                user[i] = Safe(
                    id=s.id, name=name, builtin=False, created_at=s.created_at,
                )
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
