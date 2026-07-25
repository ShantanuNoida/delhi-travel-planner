"""
Team Waypoint -- Itinerary edit commands QA (Phase 1)
Agent 5 (Documentation Agent) support script: renders Part 1 (itinerary
summaries) and Part 2 (per-itinerary edit command tables) directly from the
real run's JSON logs, so the deliverable's data sections are generated from
the actual recorded application output rather than transcribed by hand.
"""
import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load(i):
    with open(os.path.join(RESULTS_DIR, f"itinerary_{i:02d}.json"), encoding="utf-8") as f:
        return json.load(f)


def fmt_day_summary(day_key, day):
    lines = [f"**{day_key.replace('_', ' ').title()}** ({day['total_hours']}h)"]
    for stop in day["stops"]:
        lines.append(f"  - {stop['slot'].title()}: {stop['name']} _{stop['category']}_ (arr. {stop['arrival_time']})")
    if not day["stops"]:
        lines.append("  - (no stops)")
    return "\n".join(lines)


def part1():
    out = ["## Part 1 — The 20 Itineraries (Agent 2: Itinerary Generator)\n"]
    out.append("| # | Label | Days | Pace | Interests |")
    out.append("|---|---|---|---|---|")
    for i in range(1, 21):
        d = load(i)
        s = d["spec"]
        out.append(f"| {i} | {s['label']} | {s['days']} | {s['pace']} | {', '.join(s['interests'])} |")
    out.append("")
    for i in range(1, 21):
        d = load(i)
        s = d["spec"]
        out.append(f"### Itinerary {i}: {s['label']}")
        out.append(f"*{s['days']}-day, {s['pace']} pace, interests: {', '.join(s['interests'])}*\n")
        for day_key in sorted(d["initial_itinerary_summary"], key=lambda k: int(k.split('_')[1])):
            out.append(fmt_day_summary(day_key, d["initial_itinerary_summary"][day_key]))
        out.append("")
    return "\n".join(out)


def part2():
    out = ["## Part 2 — Edit Commands & Application Responses (Agent 3: Edit Command Agent)\n"]
    out.append(
        "Each itinerary below received the same **15-command editing session, applied cumulatively** "
        "(each command acts on the itinerary state left by the previous one, exactly like a real back-and-forth "
        "editing conversation) -- run for real through the app's actual Gemini-backed intent classifier and edit engine, "
        "not simulated.\n"
    )
    for i in range(1, 21):
        d = load(i)
        s = d["spec"]
        out.append(f"### Itinerary {i}: {s['label']} — edit session\n")
        out.append("| # | Command | Classified (edit_type / day / slot) | Result | App Response |")
        out.append("|---|---|---|---|---|")
        for step in d["steps"]:
            cls = step["classification"]
            ei = cls.get("edit_intent") or {}
            classified = f"{cls.get('intent')}" + (f" / {ei.get('edit_type')} / day {ei.get('target_day')} / {ei.get('target_slot')}" if ei else "")
            result = "OK" if step["edit_result_ok"] else ("N/A" if step["edit_result_ok"] is None else "REJECTED")
            msg = step["edit_result_message"].replace("|", "\\|").replace("\n", " ")
            cmd = step["command"].replace("|", "\\|")
            out.append(f"| {step['n']} | {cmd} | {classified} | {result} | {msg} |")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    with open(os.path.join(RESULTS_DIR, "_part1.md"), "w", encoding="utf-8") as f:
        f.write(part1())
    with open(os.path.join(RESULTS_DIR, "_part2.md"), "w", encoding="utf-8") as f:
        f.write(part2())
    print("wrote _part1.md and _part2.md")
