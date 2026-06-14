"""Rule-based smart classifiers.

The handoff is explicit: *initial rule-based classifiers are enough, no AI*.
Each clip is given exactly one primary :data:`classification` plus a bag of
:data:`tags` (extra detections) and a small ``metadata`` dict used by the
preview panel.

Precedence matters. ``git clone https://…`` is a *command*, not a *link*, so
commands are evaluated before links.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from . import models


# --- Regexes ---------------------------------------------------------------
URL_RE = re.compile(r"\bhttps?://[^\s<>\"')]+", re.IGNORECASE)
# A bare-domain URL like "github.com/foo" — kept conservative (known-ish TLDs).
BARE_DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|gov|edu|co|ai|app|sh)"
    r"(?:/[^\s]*)?$",
    re.IGNORECASE,
)
WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/](?:[^<>:\"|?*\r\n]*)$")
UNC_PATH_RE = re.compile(r"^\\\\[^\\/:*?\"<>|\r\n]+\\[^\r\n]+$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMAIL_FIND_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Phone: optional +, 7-15 digits with common separators. Conservative.
PHONE_RE = re.compile(
    r"^\+?\d{0,3}[\s.\-]?\(?\d{2,4}\)?(?:[\s.\-]?\d{2,4}){2,4}$"
)

CODE_KEYWORDS = re.compile(
    r"\b(def|class|function|const|let|var|import|from|return|public|private|"
    r"static|void|async|await|=>|lambda|struct|enum|interface)\b"
)

# Leading token → shell guess. Order-independent lookup.
COMMAND_WORDS = {
    "git": "Git",
    "python": "Bash",
    "python3": "Bash",
    "pip": "Bash",
    "pip3": "Bash",
    "npm": "Bash",
    "npx": "Bash",
    "yarn": "Bash",
    "pnpm": "Bash",
    "node": "Bash",
    "curl": "Bash",
    "wget": "Bash",
    "ssh": "Bash",
    "scp": "Bash",
    "docker": "Bash",
    "kubectl": "Bash",
    "cargo": "Bash",
    "go": "Bash",
    "make": "Bash",
    "sudo": "Bash",
    "apt": "Bash",
    "brew": "Bash",
    "powershell": "PowerShell",
    "pwsh": "PowerShell",
    "winget": "PowerShell",
    "choco": "PowerShell",
    "get-childitem": "PowerShell",
    "set-location": "PowerShell",
    "cd": "Shell",
    "ls": "Bash",
    "dir": "CMD",
    "cls": "CMD",
    "echo": "Shell",
}


@dataclass
class Classification:
    classification: str = models.CLASS_PLAIN
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def _first_token(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return text.split()[0].lower()


def _looks_like_command(text: str) -> tuple[bool, dict]:
    first = _first_token(text)
    # A path that merely starts with "go"/"cd" shouldn't be a command unless
    # it has command-ish shape, but keyword match on the first token is the
    # documented heuristic and works well for copied commands.
    if first in COMMAND_WORDS:
        return True, {"shell": COMMAND_WORDS[first]}
    # Flag-style detection: a single line containing recognisable CLI flags.
    if "\n" not in text.strip() and re.search(r"(?:^|\s)(--?[A-Za-z][\w-]*)", text):
        # Require at least one word before the flag so plain prose with a
        # stray hyphen isn't caught.
        if re.match(r"^\S+\s+-", text.strip()):
            return True, {"shell": "Shell"}
    return False, {}


def _looks_like_path(text: str) -> tuple[bool, dict]:
    candidate = text.strip().strip('"').strip("'")
    if WINDOWS_PATH_RE.match(candidate) or UNC_PATH_RE.match(candidate):
        name = os.path.basename(candidate.replace("\\", "/").rstrip("/"))
        _, ext = os.path.splitext(name)
        parent = os.path.dirname(candidate.replace("/", "\\"))
        return True, {
            "path": candidate,
            "file_name": name,
            "extension": ext.lstrip("."),
            "parent": parent,
        }
    return False, {}


def _link_metadata(url: str) -> dict:
    m = re.match(r"^(?P<scheme>[a-z]+)://(?P<host>[^/\s]+)", url, re.IGNORECASE)
    if m:
        return {"scheme": m.group("scheme").lower(), "domain": m.group("host").lower()}
    host = url.split("/", 1)[0]
    return {"scheme": "http", "domain": host.lower()}


def _looks_like_code(text: str) -> tuple[bool, dict]:
    stripped = text.strip()
    lines = stripped.splitlines()
    multiline_indented = len(lines) > 1 and any(
        ln.startswith((" ", "\t")) for ln in lines[1:]
    )
    has_keyword = bool(CODE_KEYWORDS.search(stripped))
    has_braces = bool(re.search(r"[{};]", stripped)) and (
        ";" in stripped or "{" in stripped
    )
    score = sum([multiline_indented, has_keyword, has_braces])
    if score >= 2 or (multiline_indented and has_keyword):
        return True, {"probable_language": _guess_language(stripped)}
    return False, {}


def _guess_language(text: str) -> str:
    if re.search(r"\b(def|import|from|lambda|self)\b", text) and ":" in text:
        return "python"
    if re.search(r"\b(const|let|var|function|=>|console\.log)\b", text):
        return "javascript"
    if re.search(r"\b(public|private|static|void|class)\b.*[{;]", text):
        return "java/c-like"
    if re.search(r"#include|std::", text):
        return "c++"
    return "unknown"


def classify(content: str) -> Classification:
    """Return the primary classification + tags + metadata for ``content``."""
    result = Classification()
    if content is None:
        return result
    text = content.strip()
    if not text:
        return result

    tags: list[str] = []

    # Collect secondary detections as tags regardless of the primary winner.
    urls = URL_RE.findall(text)
    if urls:
        tags.append(models.CLASS_LINK)
    emails = EMAIL_FIND_RE.findall(text)
    if emails:
        tags.append(models.CLASS_EMAIL)

    # --- Precedence ladder ---
    is_cmd, cmd_meta = _looks_like_command(text)
    if is_cmd:
        result.classification = models.CLASS_COMMAND
        result.metadata = cmd_meta
        result.tags = _dedupe(tags)
        return result

    single_line = "\n" not in text

    if single_line and (URL_RE.match(text) or BARE_DOMAIN_RE.match(text)):
        result.classification = models.CLASS_LINK
        result.metadata = _link_metadata(text)
        result.tags = _dedupe(tags)
        return result

    is_path, path_meta = _looks_like_path(text)
    if is_path:
        result.classification = models.CLASS_PATH
        result.metadata = path_meta
        result.tags = _dedupe(tags)
        return result

    if single_line and EMAIL_RE.match(text):
        result.classification = models.CLASS_EMAIL
        result.metadata = {"address": text, "domain": text.split("@", 1)[1].lower()}
        result.tags = _dedupe(tags)
        return result

    # Phone only when the whole clip is plausibly one number with enough digits.
    digits = re.sub(r"\D", "", text)
    if single_line and PHONE_RE.match(text) and 7 <= len(digits) <= 15:
        result.classification = models.CLASS_PHONE
        result.metadata = {"digits": digits}
        result.tags = _dedupe(tags)
        return result

    is_code, code_meta = _looks_like_code(text)
    if is_code:
        result.classification = models.CLASS_CODE
        result.metadata = code_meta
        result.tags = _dedupe(tags)
        return result

    if urls:
        # Free text that merely contains a URL.
        result.classification = models.CLASS_LINK
        result.metadata = _link_metadata(urls[0])
        result.tags = _dedupe(tags)
        return result

    result.classification = models.CLASS_PLAIN
    result.tags = _dedupe(tags)
    return result


def _dedupe(items: list[str]) -> list[str]:
    seen: list[str] = []
    for it in items:
        if it not in seen:
            seen.append(it)
    return seen
