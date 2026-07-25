"""
Phase 3 entry point.

Usage:
  python main.py              # text-based interactive session
  python main.py --voice      # voice session (mic + TTS)
  python main.py --test       # run T-3.x validation tests
"""

import argparse
import os
import sys

# Windows' default console codepage (cp1252) can't encode many characters
# that show up in ordinary text — arrows, "approximately equal", smart
# quotes, emoji — and agent.py's _say() prints replies directly when TTS is
# off, so one such character crashes the whole turn. See phase6/app.py for
# the same fix and the R-14 testing session that surfaced this.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))


def main():
    parser = argparse.ArgumentParser(description="Phase 3 — Conversational Voice Agent")
    parser.add_argument("--voice", action="store_true", help="Use microphone + TTS")
    parser.add_argument("--test", action="store_true", help="Run T-3.x validation tests")
    args = parser.parse_args()

    if args.test:
        from test_agent import run_all
        run_all()
        from test_narrator import run_all as run_all_narrator
        run_all_narrator()
        return

    from agent import run_session
    run_session(voice=args.voice)


if __name__ == "__main__":
    main()
