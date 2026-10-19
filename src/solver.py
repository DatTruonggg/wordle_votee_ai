"""
Solve a Votee Wordle puzzle.

Loop:
  1. choose_guess(candidates, guess_pool)       -> strategy.py
  2. ask the API for feedback on that guess     -> votee_client.py
  3. encode feedback as a base-3 int            -> score.py
  4. stop if all correct, else filter_candidates and repeat

Fallback when no candidates are left (answer is not in our word list):
  The API accepts any string and scores each slot on its own, so we can probe
  letters directly. Every feedback is kept as per-slot constraints:
    correct at i -> slot i is that letter
    present at i -> slot i is NOT that letter, but the letter is in the answer
    absent       -> the letter is in no slot
  Each probe puts a different untried letter into every unknown slot:
  present-but-unplaced letters first, then by corpus frequency, already placed letters last.
"""

import random
from collections import Counter
from dataclasses import dataclass, field
from string import ascii_lowercase

from src.corpus import load_words
from src.score import decode, filter_candidates, pattern_from_response, solved_code
from src.strategy import choose_guess
from src.votee_client import APIError, VoteeWordleClient


@dataclass
class SolverStep:
    guess: str
    results: tuple[str, ...]   # per-slot feedback, e.g. ("absent", "present", ...)
    candidates_exist: int      # candidates left after filtering with this feedback


@dataclass
class SolverResult:
    solved: bool
    answer: str | None
    steps: list[SolverStep] = field(default_factory=list)
    error: str | None = None
    seed: int | None = None    # seed used in "random" mode, to replay the same puzzle

    @property
    def attempts(self) -> int:
        return len(self.steps)


class Solver:
    def __init__(self,
                client: VoteeWordleClient | None = None,
                size: int = 5,
                max_guesses: int = 20,
                use_full_pool: bool = True):
        self.client = client or VoteeWordleClient()
        self.size = size
        self.max_guesses = max_guesses
        self.words = sorted(load_words(size))
        # Full pool: may guess non-candidate words that split candidates better.
        self.guess_pool = self.words if use_full_pool else None
        # Letter priority for the fallback probe: most common letters first.
        freq = Counter(ch for w in self.words for ch in w)
        self.letter_order = sorted(ascii_lowercase, key=lambda ch: -freq[ch])

    def _probe_guess(self, allowed: list[set[str]], present: set[str]) -> str:
        """Fallback guess built from per-slot constraints (no dictionary needed)."""
        # Present-but-unplaced letters first, then by frequency, letters already placed last
        # (they only help if the answer repeats a letter).
        placed = {next(iter(slot)) for slot in allowed if len(slot) == 1}
        order = sorted(self.letter_order,
                       key=lambda ch: 2 if ch in placed else 0 if ch in present else 1)
        guess, used = [], set()
        for slot in allowed:
            if len(slot) == 1:
                guess.append(next(iter(slot)))
                continue
            options = [ch for ch in order if ch in slot]
            # Prefer a letter not used elsewhere in this guess, to test more letters at once.
            pick = next((ch for ch in options if ch not in used), options[0])
            guess.append(pick)
            used.add(pick)
        return "".join(guess)

    @staticmethod
    def _update_constraints(allowed: list[set[str]], present: set[str], guess: str, results) -> None:
        for i, (ch, r) in enumerate(zip(guess, results)):
            if r == "correct":
                allowed[i] = {ch}
            elif r == "present":
                allowed[i].discard(ch)
                present.add(ch)
            else:
                for slot in allowed:
                    if len(slot) > 1:
                        slot.discard(ch)

    def _ask(self, guess: str, mode: str, seed: int | None, word: str | None) -> list[dict]:
        if mode == "daily":
            return self.client.daily(guess, self.size)
        if mode == "random":
            return self.client.random(guess, self.size, seed)
        if mode == "word":
            return self.client.word(word, guess)
        raise ValueError(f"unknown mode: {mode!r}")

    def solve(self, mode: str = "daily", seed: int | None = None, word: str | None = None) -> SolverResult:
        """mode: "daily" | "random" (optional seed) | "word" (requires word)."""
        if mode == "word":
            if not word:
                raise ValueError('mode "word" needs a word')
            if len(word) != self.size:
                raise ValueError(f"word must have {self.size} letters")
        if mode == "random" and seed is None:
            # Without a seed the API picks a new word on EVERY request,
            # so fix one seed for the whole game.
            seed = random.randrange(2**31)

        candidates = list(self.words)
        allowed = [set(ascii_lowercase) for _ in range(self.size)]
        present: set[str] = set()
        result = SolverResult(solved=False, answer=None, seed=seed if mode == "random" else None)
        target = solved_code(self.size)

        while result.attempts < self.max_guesses:
            if candidates:
                guess = choose_guess(candidates, self.guess_pool)
            elif all(allowed):
                guess = self._probe_guess(allowed, present)
            else:
                result.error = "feedback is contradictory (no letter fits some slot)"
                return result

            try:
                feedback = pattern_from_response(self._ask(guess, mode, seed, word))
            except APIError as e:
                result.error = str(e)
                return result

            if feedback == target:
                result.steps.append(SolverStep(guess, decode(feedback, self.size), 1))
                result.solved = True
                result.answer = guess
                return result

            results = decode(feedback, self.size)
            self._update_constraints(allowed, present, guess, results)
            candidates = filter_candidates(candidates, guess, feedback)
            result.steps.append(SolverStep(guess, results, len(candidates)))

        result.error = f"gave up after {self.max_guesses} guesses"
        return result

