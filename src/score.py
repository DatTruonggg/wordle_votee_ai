"""
My Idea
Hello -> lllll

remove the candidate. after each finding, with the `l` in list solver will ask if "l" is in answer or not, if correct, it will return the correct feedback

How it works with the Votee API (each slot is scored on its own, no letter counting):
  - correct : same letter at the same slot
  - present : letter appears anywhere in the answer
  - absent  : letter not in the answer at all

  So guessing one letter repeated ("lllll") answers two questions at once:
    answer "hello", guess "lllll" -> present present correct correct present
      -> "l" IS in the answer, and it sits exactly at slots 2 and 3
    answer "crane", guess "lllll" -> absent absent absent absent absent
      -> "l" is NOT in the answer

  score() reproduces that feedback locally, so we can remove every candidate
  whose score(guess, candidate) differs from what the API returned.

Feedback encoding:
  Each slot has only 3 possible values, so a whole feedback is a base-3 number
  (like a bitmask, but 3 states instead of 2). Slot i is the digit at 3**i:

    code = sum(DIGIT[result_i] * 3**i)

  absent=0, correct=1, present=2 (index in RESULTS)
    "lllll" vs "hello" -> present present correct correct present
                       -> 2*1 + 2*3 + 1*9 + 1*27 + 2*81 = 206

  One int is cheap to compare and can be used as a dict key
  (e.g. group candidates by the feedback they would give).
"""

RESULTS = ("absent", "correct", "present") #3 possible values
ABSENT, CORRECT, PRESENT = range(3)        # digit of each result
DIGIT = {result: d for d, result in enumerate(RESULTS)}


def score(guess: str, answer: str) -> int:
    """Return the feedback of `guess` against `answer` (same rules as the API) as a base-3 int."""
    if len(guess) != len(answer):
        raise ValueError("guess and answer must have the same length")

    letters = set(answer)
    code = 0
    weight = 1
    for g, a in zip(guess, answer):
        if g == a:
            code += CORRECT * weight
        elif g in letters:
            code += PRESENT * weight
        weight *= 3
    return code


def encode(results: list[str]) -> int:
    """["present", "correct", ...] (in slot order) -> base-3 int."""
    code = 0
    weight = 1
    for r in results:
        code += DIGIT[r] * weight
        weight *= 3
    return code


def decode(code: int, size: int) -> tuple[str, ...]:
    """base-3 int -> ("present", "correct", ...). Handy for printing/debugging."""
    results = []
    for _ in range(size):
        code, d = divmod(code, 3)
        results.append(RESULTS[d])
    return tuple(results)


def solved_code(size: int) -> int:
    """Code of an all-correct feedback (the puzzle is solved)."""
    return encode(["correct"] * size)


def pattern_from_response(response: list[dict]) -> int:
    """Convert the API response [{"slot", "guess", "result"}, ...] into a base-3 int."""
    return encode([item["result"] for item in sorted(response, key=lambda x: x["slot"])])


def filter_candidates(candidates, guess: str, feedback: int) -> list[str]:
    """Remove every candidate that would not have produced `feedback` for `guess`."""
    return [word for word in candidates if score(guess, word) == feedback]
