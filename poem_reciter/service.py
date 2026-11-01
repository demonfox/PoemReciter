from itertools import zip_longest
import random
from typing import Callable, List, Optional

from poem_reciter.models import EvaluationResult, LineComparison, Poem
from poem_reciter.repository import PoemRepository, normalize_poem_text

AttemptListener = Callable[[EvaluationResult], None]


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
            comparisons.append(
                LineComparison(
                    line_number=idx,
                    expected=exp_line,
                    actual=act_line,
                    is_correct=(exp_line == act_line),
                )
            )

        result = EvaluationResult(
            poem_id=poem.id,
            header=poem.header,
            is_correct=is_correct,
            expected_text=expected_text,
            submitted_text=submitted_text,
            line_comparisons=comparisons,
        )

        for listener in self._listeners:
            listener(result)

        return result

