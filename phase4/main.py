"""
Phase 4 entry point.

Usage:
  python main.py --test       # run T-4.x validation tests
"""

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))


def main():
    parser = argparse.ArgumentParser(description="Phase 4 — Voice Editing & Explanations")
    parser.add_argument("--test", action="store_true", help="Run T-4.x validation tests")
    args = parser.parse_args()

    if args.test:
        from test_phase4 import run_all
        run_all()
        from test_intent_classifier_guards import run_all as run_all_guards
        run_all_guards()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
