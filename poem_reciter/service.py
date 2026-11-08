from difflib import SequenceMatcher
from itertools import zip_longest
import random
from typing import Callable, List, Optional

from poem_reciter.models import EvaluationResult, LineComparison, Poem
from poem_reciter.repository import PoemRepository, extract_poem_chars, normalize_poem_text

AttemptListener = Callable[[EvaluationResult], None]


def compare_line_chars( line_number: int, exp_line: str, act_line: str ) -> LineComparison:
    """Compare a single expected line and actual line using character-level LCS alignment."""
    exp_chars = extract_poem_chars(exp_line)
    act_chars = extract_poem_chars(act_line)
    n_exp = len(exp_chars)
    n_act = len(act_chars)

    matcher = SequenceMatcher(None, exp_chars, act_chars, autojunk=False)
    matched_chars = sum(block.size for block in matcher.get_matching_blocks())

    char_diffs: List[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        char_diffs.append(
            {
                "type": tag,
                "expected": exp_chars[i1:i2],
                "actual": act_chars[j1:j2],
            }
        )

    extra_chars = max(0, n_act - n_exp)
    if n_exp > 0:
        correct_chars = max(0, matched_chars - extra_chars)
        wrong_chars = n_exp - correct_chars
        is_line_correct = (exp_chars == act_chars)
    else:
        correct_chars = 0
        wrong_chars = 0
        is_line_correct = (n_act == 0)

    return LineComparison(
        line_number=line_number,
        expected=exp_line,
        actual=act_line,
        is_correct=is_line_correct,
        total_chars=n_exp,
        matched_chars=matched_chars,
        correct_chars=correct_chars,
        wrong_chars=wrong_chars,
        extra_chars=extra_chars,
        char_diffs=char_diffs,
    )


class ReciterService:
    """Core domain service for selecting poems and evaluating recitations."""

    def __init__(self, repository: PoemRepository) -> None:
        self.repository = repository
        self._listeners: List[AttemptListener] = []

    def register_attempt_listener(self, listener: AttemptListener) -> None:
        """Hook for future features such as recording statistics or spaced repetition."""
        self._listeners.append(listener)

    def get_all_poems(self) -> List[Poem]:
        return self.repository.list_all()

    def get_poem(self, poem_id: int) -> Optional[Poem]:
        return self.repository.get_by_id(poem_id)

    def pick_random_poem(self, exclude_id: Optional[int] = None) -> Poem:
        poems = self.repository.list_all()
        if not poems:
            raise ValueError("No poems available in repository.")
        if exclude_id is not None and len(poems) > 1:
            candidates = [p for p in poems if p.id != exclude_id]
            if candidates:
                poems = candidates
        return random.choice(poems)

    def evaluate(self, poem_id: int, raw_answer: str) -> EvaluationResult:
        poem = self.repository.get_by_id(poem_id)
        if poem is None:
            raise KeyError(f"Poem with id {poem_id} not found.")

        submitted_text = normalize_poem_text(raw_answer)
        expected_text = poem.text
        is_correct = submitted_text == expected_text

        expected_lines = expected_text.split("\n") if expected_text else []
        submitted_lines = submitted_text.split("\n") if submitted_text else []

        comparisons: List[LineComparison] = []
        for idx, (exp_line, act_line) in enumerate(
            zip_longest(expected_lines, submitted_lines, fillvalue=""), start=1
        ):
            comparisons.append(compare_line_chars(idx, exp_line, act_line))

        total_chars = sum(lc.total_chars for lc in comparisons)
        extra_line_chars = sum(lc.extra_chars for lc in comparisons if lc.total_chars == 0)
        raw_correct_chars = sum(lc.correct_chars for lc in comparisons if lc.total_chars > 0)
        correct_chars = max(0, raw_correct_chars - extra_line_chars)
        wrong_chars = total_chars - correct_chars
        extra_chars = sum(lc.extra_chars for lc in comparisons)
        accuracy = (correct_chars / total_chars) if total_chars > 0 else 1.0
        is_correct = all(lc.is_correct for lc in comparisons) and len(expected_lines) == len(submitted_lines)

        result = EvaluationResult(
            poem_id=poem.id,
            header=poem.header,
            is_correct=is_correct,
            expected_text=expected_text,
            submitted_text=submitted_text,
            line_comparisons=comparisons,
            total_chars=total_chars,
            correct_chars=correct_chars,
            wrong_chars=wrong_chars,
            extra_chars=extra_chars,
            accuracy=accuracy,
        )

        for listener in self._listeners:
            listener(result)

        return result

