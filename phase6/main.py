"""
Phase 6 entry point.

Usage:
  python main.py --test       # run automated T-6.x validation tests
  streamlit run app.py        # launch the Companion UI
"""

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))


def main():
    parser = argparse.ArgumentParser(description="Phase 6 — UI & Delivery")
    parser.add_argument("--test", action="store_true", help="Run T-6.x validation tests")
    args = parser.parse_args()

    if args.test:
        from test_phase6 import run_all
        run_all()
        return

    print("To launch the Companion UI, run: streamlit run app.py")
    parser.print_help()


if __name__ == "__main__":
    main()
