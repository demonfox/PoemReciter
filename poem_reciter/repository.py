from pathlib import Path
import re
from typing import Dict, List, Optional, Protocol

from poem_reciter.models import Poem

_HEADER_WITH_DYNASTY_RE = re.compile(r"^(.*?)\s*【(.+?)】\s*(.+)$")
_IGNORED_CHAR_RE = re.compile(r"[\s，。、！？；：“”‘’（）《》〈〉【】·,.\-!?;:\"'()\[\]<>]+")


def extract_poem_chars(text: str) -> str:
    """Return only the substantive characters of a poem line/body (ignoring spaces and punctuation)."""
    return _IGNORED_CHAR_RE.sub("", text)


def normalize_poem_text(raw_text: str) -> str:
    """Normalize poem text by trimming whitespace on each line and removing outer blank lines."""
    lines = [line.strip() for line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def parse_header(header: str) -> tuple[str, Optional[str], str]:
    """Extract (title, dynasty, author) from a poem header string."""
    cleaned = header.strip()
    match = _HEADER_WITH_DYNASTY_RE.match(cleaned)
    if match:
        return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()

    parts = cleaned.rsplit(None, 1)
    if len(parts) == 2:
        return parts[0].strip(), None, parts[1].strip()
    return cleaned, None, ""


class PoemRepository(Protocol):
    """Protocol for poem data access (allows swapping file storage for SQLite/DB later)."""

    def list_all(self) -> List[Poem]:
        ...

    def get_by_id(self, poem_id: int) -> Optional[Poem]:
        ...


class FilePoemRepository:
    """Loads poems from the plain-text Poems file."""

    def __init__(self, file_path: str | Path = "Poems") -> None:
        self.file_path = Path(file_path)
        self._poems_by_id: Dict[int, Poem] = {}
        self.reload()

    def reload(self) -> None:
        poems_by_id: Dict[int, Poem] = {}
        with self.file_path.open("r", encoding="utf-8") as f:
            for idx, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                header, raw_poem_text = line.split("：", 1)
                header = header.strip()
                expanded_text = raw_poem_text.replace("\\n", "\n")
                normalized_text = normalize_poem_text(expanded_text)
                title, dynasty, author = parse_header(header)
                poem = Poem(
                    id=idx,
                    header=header,
                    text=normalized_text,
                    title=title,
                    dynasty=dynasty,
                    author=author,
                )
                poems_by_id[poem.id] = poem
        self._poems_by_id = poems_by_id

    def list_all(self) -> List[Poem]:
        return list(self._poems_by_id.values())

    def get_by_id(self, poem_id: int) -> Optional[Poem]:
        return self._poems_by_id.get(poem_id)

