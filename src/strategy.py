"""
Pick the next guess.

  - 2 or fewer candidates left -> just guess candidates[0]
    (it's either the answer, or the feedback tells us the other one).

  - Otherwise score every word in guess_pool (or candidates if no pool) by a tuple,
    and return the max:

      1. split  : sum of min(count, total - count) over the word's DISTINCT letters,
                  count = how many candidates contain that letter.
                  A letter in half the candidates splits them best; a letter in all
                  or none of them tells us nothing.
      2. is_cand: True if the word is itself a candidate (it could be the answer).
      3. slots  : sum of how many candidates share each of the word's letters at the
                  same slot (more likely to get "correct" feedback).

    Tuples compare left to right, so (2) and (3) only break ties of (1).
"""

from collections import Counter


def choose_guess(candidates, guess_pool=None) -> str:
    candidates = sorted(candidates)  # works for sets too, and keeps results deterministic
    if not candidates:
        raise ValueError("no candidates left")
    if len(candidates) <= 2:
        return candidates[0]

    total = len(candidates)
    candidate_set = set(candidates)

    # How many candidates contain each letter (counted once per word).
    letter_count = Counter(ch for word in candidates for ch in set(word))
    # How many candidates have each letter at each slot.
    slot_count = Counter((i, ch) for word in candidates for i, ch in enumerate(word))

    def word_score(word: str) -> tuple[int, bool, int]:
        split = sum(min(letter_count[ch], total - letter_count[ch]) for ch in set(word))
        is_cand = word in candidate_set
        slots = sum(slot_count[(i, ch)] for i, ch in enumerate(word))
        return (split, is_cand, slots)

    pool = sorted(guess_pool) if guess_pool else candidates
    return max(pool, key=word_score)
