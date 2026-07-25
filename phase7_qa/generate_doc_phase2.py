"""
Team Waypoint -- Itinerary edit commands QA (Phase 2)
Agent 5 (Documentation Agent) support script: renders the per-itinerary
question-command tables directly from the real run's JSON logs, so this
section is generated from actual recorded application output rather than
transcribed by hand.
"""
import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load(i):
    with open(os.path.join(RESULTS_DIR, f"phase2_itinerary_{i:02d}.json"), encoding="utf-8") as f:
        return json.load(f)


def esc(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def part5():
    out = ["## Part 5 — Question Commands & Application Responses (Agent 3: Question Command Agent)\n"]
    out.append(
        "Each itinerary below received the same **15-question session** -- one real question per "
        "category-diverse probe (justification, contingency, alternatives, expansion, practicalities, "
        "suitability, plus one edge-case honesty probe), run against the **unmodified itinerary Agent 2 "
        "built in Phase 1** (no edits applied), through the app's actual Gemini-backed intent classifier "
        "(`phase4/intent_classifier.py`) and explanation engine (`phase4/explain_engine.py`, which itself "
        "performs real RAG lookups against Phase 1's ChromaDB) -- not simulated. Every question names a "
        "venue that is actually on that itinerary.\n"
    )
    for i in range(1, 21):
        d = load(i)
        s = d["spec"]
        out.append(f"### Itinerary {i}: {s['label']} — question session\n")
        out.append("| # | Category | Question | Intent | Grounded | App Answer |")
        out.append("|---|---|---|---|---|---|")
        for step in d["steps"]:
            cls = step["classification"]
            answer = step.get("answer")
            intent = cls.get("intent")
            if answer is not None:
                grounded = str(answer.get("grounded"))
                ans_text = esc(answer.get("answer"))
            else:
                grounded = "N/A"
                ans_text = esc(step.get("_note"))
            cmd = esc(step["command"])
            out.append(f"| {step['n']} | {step['category']} | {cmd} | {intent} | {grounded} | {ans_text} |")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    with open(os.path.join(RESULTS_DIR, "_part5.md"), "w", encoding="utf-8") as f:
        f.write(part5())
    print("wrote _part5.md")
