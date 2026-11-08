from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Poem:
    """Represents a single poem entry."""
    id: int
    header: str
    text: str
    title: str = ""
    dynasty: Optional[str] = None
    author: str = ""

    @property
    def lines(self) -> List[str]:
        return self.text.split("\n") if self.text else []

    def to_prompt_dict(self) -> dict:
        """Serialize prompt metadata without revealing the poem body."""
        return {
            "id": self.id,
            "header": self.header,
            "title": self.title,
            "dynasty": self.dynasty,
            "author": self.author,
            "line_count": len(self.lines),
        }


@dataclass(frozen=True)
class LineComparison:
    """Comparison result for a single line."""
    line_number: int
    expected: str
    actual: str
    is_correct: bool
    total_chars: int = 0
    matched_chars: int = 0
    correct_chars: int = 0
    wrong_chars: int = 0
    extra_chars: int = 0
    char_diffs: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "line_number": self.line_number,
            "expected": self.expected,
            "actual": self.actual,
            "is_correct": self.is_correct,
            "total_chars": self.total_chars,
            "matched_chars": self.matched_chars,
            "correct_chars": self.correct_chars,
            "wrong_chars": self.wrong_chars,
            "extra_chars": self.extra_chars,
            "char_diffs": self.char_diffs,
        }


@dataclass(frozen=True)
class EvaluationResult:
    """Result of checking a user's poem recitation."""
    poem_id: int
    header: str
    is_correct: bool
    expected_text: str
    submitted_text: str
    line_comparisons: List[LineComparison] = field(default_factory=list)
    total_chars: int = 0
    correct_chars: int = 0
    wrong_chars: int = 0
    extra_chars: int = 0
    accuracy: float = 0.0
    poem_stats: Optional[dict] = None

    def to_dict(self) -> dict:
        data = {
            "poem_id": self.poem_id,
            "header": self.header,
            "is_correct": self.is_correct,
            "expected_text": self.expected_text,
            "submitted_text": self.submitted_text,
            "total_chars": self.total_chars,
            "correct_chars": self.correct_chars,
            "wrong_chars": self.wrong_chars,
            "extra_chars": self.extra_chars,
            "accuracy": round(self.accuracy, 4),
            "line_comparisons": [lc.to_dict() for lc in self.line_comparisons],
        }
        if self.poem_stats is not None:
            data["poem_stats"] = self.poem_stats
        return data

