"""
Command-line runner for the Votee Wordle solver.

  python runner.py daily [--size 5]
  python runner.py random [--size 5] [--seed 42]
  python runner.py word hello
  python runner.py daily --json             # machine-readable output

Exit code: 0 if solved, 1 if not.
"""

import argparse
import json
import sys
from dataclasses import asdict

from src.solver import Solver, SolverResult
from src.votee_client import BASE_URL, VoteeWordleClient

MARKS = {"correct": "G", "present": "Y", "absent": "."}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Solve a Votee Wordle puzzle")

    # Shared options, accepted by every mode.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--max-guesses", type=int, default=20, help="stop after this many guesses (default: 20)")
    common.add_argument("--candidates-only", action="store_true",
                        help="only guess possible answers (default: any word that splits candidates better)")
    common.add_argument("--json", action="store_true", help="print the result as JSON")
    common.add_argument("--base-url", default=BASE_URL, help=f"API base URL (default: {BASE_URL})")
    common.add_argument("--max-requests", type=int, default=45, help="API request budget (default: 45)")
    common.add_argument("--timeout", type=int, default=10, help="request timeout in seconds (default: 10)")
    common.add_argument("--delay", type=float, default=0.25, help="seconds between requests (default: 0.25)")

    modes = parser.add_subparsers(dest="mode", required=True)

    daily = modes.add_parser("daily", parents=[common], help="today's puzzle")
    daily.add_argument("--size", type=int, default=5, help="word length (default: 5)")

    random = modes.add_parser("random", parents=[common], help="random puzzle")
    random.add_argument("--size", type=int, default=5, help="word length (default: 5)")
    random.add_argument("--seed", type=int, help="same seed -> same word")

    word = modes.add_parser("word", parents=[common], help="a word you choose")
    word.add_argument("word", help="the target word")

    return parser


def print_result(result: SolverResult) -> None:
    if result.seed is not None:
        print(f"seed: {result.seed}")
    for i, step in enumerate(result.steps, 1):
        marks = "".join(MARKS[r] for r in step.results)
        print(f"{i:2}. {step.guess}  {marks}  candidates left: {step.candidates_exist}")
    if result.solved:
        print(f"solved: {result.answer} in {result.attempts} guesses")
    else:
        print(f"failed: {result.error}")


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode == "word":
        args.word = args.word.lower()
        if not args.word.isalpha():
            parser.error("word must contain letters only")
        args.size = len(args.word)
    if args.size < 1:
        parser.error("--size must be at least 1")
    if args.max_guesses < 1:
        parser.error("--max-guesses must be at least 1")

    client = VoteeWordleClient(base_url=args.base_url,
                               max_requests=args.max_requests,
                               timeout=args.timeout,
                               delay=args.delay)
    solver = Solver(client=client,
                    size=args.size,
                    max_guesses=args.max_guesses,
                    use_full_pool=not args.candidates_only)

    result = solver.solve(args.mode,
                          seed=getattr(args, "seed", None),
                          word=getattr(args, "word", None))

    if args.json:
        print(json.dumps({**asdict(result), "attempts": result.attempts}, indent=2))
    else:
        print_result(result)

    return 0 if result.solved else 1


if __name__ == "__main__":
    sys.exit(main())
