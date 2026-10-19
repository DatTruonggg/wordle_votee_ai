# Votee Wordle Solver

A solver for the Votee Wordle API (`https://wordle.votee.dev:8000`). It plays one game against the API and prints every guess with its feedback.

It supports the three puzzle types of the API:

| Mode | Endpoint | Puzzle |
|---|---|---|
| `daily` | `GET /daily?guess=&size=` | today's puzzle |
| `random` | `GET /random?guess=&size=&seed=` | a random word, fixed by a seed |
| `word` | `GET /word/{word}?guess=` | a word you choose |

## Running

Requires Python 3.10 or newer. Run all commands from the project root.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python -m src.runner daily                    # today's puzzle, 5 letters
python -m src.runner daily --size 6           # today's puzzle, 6 letters
python -m src.runner random                   # random puzzle, seed picked for you
python -m src.runner random --seed 42 --size 6
python -m src.runner word hello               # solve a word you choose
```

Example output (`G` = correct, `Y` = present, `.` = absent):

```
seed: 82950862
 1. aries  Y..G.  candidates left: 216
 2. doylt  Y..Y.  candidates left: 13
 3. nowch  Y....  candidates left: 1
 4. laden  GGGGG  candidates left: 1
solved: laden in 4 guesses
```

### Options

| Option | Modes | Default | Description |
|---|---|---|---|
| `--size N` | daily, random | 5 | word length (`word` mode uses the word's length) |
| `--seed N` | random | random | same seed gives the same word; the seed used is printed |
| `--max-guesses N` | all | 20 | stop after N guesses |
| `--candidates-only` | all | off | only guess words that can still be the answer |
| `--json` | all | off | print the full result as JSON |
| `--max-requests N` | all | 45 | maximum number of API requests |
| `--delay S` | all | 0.25 | seconds to wait between requests |
| `--timeout S` | all | 10 | request timeout in seconds |
| `--base-url URL` | all | API URL | use another server |

Exit code: `0` if solved, `1` if not solved, `2` for invalid arguments.

## How the solution works

### 1. How the API scores a guess

Before writing the solver, I tested how the API handles repeated letters. It does **not** follow standard Wordle rules. It scores each slot on its own:

- `correct`: same letter at the same slot
- `present`: the letter appears anywhere in the answer
- `absent`: the letter is not in the answer

The API never counts letters. For the answer `hello` and the guess `lllll`:

```
API:              present present correct correct present
standard Wordle:  absent  absent  correct correct absent
```

This gives a useful property: a guess of one repeated letter, such as `lllll`, answers two questions at once: is `l` in the word, and in exactly which slots.

### 2. Feedback as a base-3 number (`score.py`)

Each slot has only 3 possible results, so the feedback of a whole guess is a base-3 number, like a bitmask with 3 states instead of 2. Slot `i` is the digit worth `3**i`:

```
absent = 0, correct = 1, present = 2

"lllll" vs "hello" -> present present correct correct present
                   -> 2*1 + 2*3 + 1*9 + 1*27 + 2*81 = 206
```

One integer is cheap to compare and can be used as a dictionary key.

`score(guess, answer)` computes this number locally, using the same rules as the API. Filtering is then one comparison per word: a word stays a candidate only if `score(guess, word)` equals the feedback the API returned. Every rule (correct, present, absent, repeated letters) is handled by this one function.

### 3. Choosing the next guess (`strategy.py`)

If 2 or fewer candidates are left, guess the first one. Otherwise, give every word in the guess pool a score tuple and pick the highest:

1. **Split**: for each distinct letter of the word, `min(count, total - count)`, summed. `count` is how many candidates contain the letter. A letter in about half of the candidates splits them best. A letter in all or none of them tells us nothing.
2. **Is a candidate**: prefer words that could be the answer.
3. **Slot matches**: for each slot, how many candidates have the same letter there, summed.

Python compares tuples left to right, so (2) and (3) only break ties.

By default the guess pool is the whole word list, not only the remaining candidates. A word that cannot be the answer often splits the candidates better (use `--candidates-only` to turn this off).

### 4. The game loop (`solver.py`)

```
candidates = all words of the right length
repeat:
    guess    = choose_guess(candidates, pool)
    feedback = ask the API, encode as base-3 number
    stop if feedback is all correct
    candidates = filter_candidates(candidates, guess, feedback)
```

Every step is saved as a `SolverStep(guess, results, candidates_exist)`, and the game returns a `SolverResult` (solved, answer, steps, error, seed).

### 5. Fallback: answer not in the word list

The word lists in `data/` may not contain every answer the API uses. With only `words_alpha.txt`, the daily answer `lykes` was missing and the candidates dropped to 0 (the larger `English_words.txt` now covers it).

The API accepts any string as a guess, so the solver does not need a dictionary to keep going. While playing, it also keeps a set of possible letters for each slot:

- `correct` at slot i: slot i is that letter
- `present` at slot i: slot i is not that letter, but the letter is in the answer
- `absent`: the letter is in no slot

When no candidates are left, it builds guesses from these sets. It puts a different untried letter in every unknown slot, in this order: letters known to be present but not placed yet, then the most common letters, then letters already placed in another slot (only useful if the answer repeats a letter). This solves any word, even made-up ones such as `qzxjv` (9 guesses).

### 6. Random mode needs a fixed seed

Without a `seed`, `/random` picks a new word on every request, so feedback from different guesses would belong to different words. If no `--seed` is given, the solver picks one seed at the start, uses it for the whole game and prints it, so the game can be replayed.

## Project structure

```
data/words_alpha.txt   English word list  } merged into one set
data/English_words.txt larger word list   } to build candidates
src/votee_client.py    API client: VoteeWordleClient, APIError
src/corpus.py          loads all words of a given length
src/score.py           local scoring, base-3 feedback encoding, filtering
src/strategy.py        choose_guess: picks the next guess
src/solver.py          game loop, fallback probing, SolverStep / SolverResult
src/runner.py          command-line interface (argparse)
```

### API client

`VoteeWordleClient` uses only the Python standard library (`urllib`). For every request it:

- checks the request budget (`max_requests`) and raises `APIError` when it is used up
- waits `delay` seconds between requests
- raises `APIError(status, message)` with the server's message on HTTP errors, e.g. `APIError 400 Guess must be the same length as the word`

## Results

Some games played against the live API:

| Puzzle | Answer | Guesses |
|---|---|---|
| `word hello` | hello | 6 |
| `random --seed 1` | fiery | 4 |
| `random --seed 3` | murky | 5 |
| `random --seed 11 --size 6 --candidates-only` | kimono | 4 |
| `daily` (2026-10-19) | lykes | 3 |
| `daily` (2026-10-19), `words_alpha.txt` only | lykes (found by fallback) | 9 |
| `word qzxjv` (not a real word) | qzxjv | 9 |
