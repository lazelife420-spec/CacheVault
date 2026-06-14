"""Search-query parsing.

Parses a raw search box string into a :class:`SearchQuery` that
:meth:`VaultStorage.list_clips` understands. Supports the documented syntax::

    type:link github
    type:code python
    source:cursor
    sensitive:true
    pinned:true

Unknown ``key:value`` tokens are treated as plain text so the box never
silently swallows a search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import models


_TYPE_ALIASES = {
    "link": models.CLASS_LINK,
    "url": models.CLASS_LINK,
    "path": models.CLASS_PATH,
    "file": models.CLASS_PATH,
    "code": models.CLASS_CODE,
    "command": models.CLASS_COMMAND,
    "cmd": models.CLASS_COMMAND,
    "email": models.CLASS_EMAIL,
    "phone": models.CLASS_PHONE,
    "plain": models.CLASS_PLAIN,
}

_TRUE = {"true", "1", "yes", "y", "on"}
_FALSE = {"false", "0", "no", "n", "off"}

_TOKEN_RE = re.compile(r"(\w+):(\S+)")


@dataclass
class SearchQuery:
    filter_name: str = "all"
    text: str = ""
    type_filter: str | None = None
    source: str | None = None
    sensitive: bool | None = None
    pinned: bool | None = None


def _to_bool(value: str) -> bool | None:
    v = value.lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return None


def parse(raw: str, filter_name: str = "all") -> SearchQuery:
    """Turn a raw search string into a :class:`SearchQuery`."""
    query = SearchQuery(filter_name=filter_name)
    if not raw:
        return query

    free_terms: list[str] = []
    pos = 0
    for m in _TOKEN_RE.finditer(raw):
        # capture any free text between tokens
        free_terms.append(raw[pos:m.start()])
        pos = m.end()
        key, value = m.group(1).lower(), m.group(2)
        if key == "type" and value.lower() in _TYPE_ALIASES:
            query.type_filter = _TYPE_ALIASES[value.lower()]
        elif key == "source":
            query.source = value
        elif key == "sensitive":
            b = _to_bool(value)
            if b is None:
                free_terms.append(m.group(0))
            else:
                query.sensitive = b
        elif key == "pinned":
            b = _to_bool(value)
            if b is None:
                free_terms.append(m.group(0))
            else:
                query.pinned = b
        else:
            # Not a recognised token — keep it as free text.
            free_terms.append(m.group(0))
    free_terms.append(raw[pos:])

    query.text = " ".join(" ".join(free_terms).split()).strip()
    return query
