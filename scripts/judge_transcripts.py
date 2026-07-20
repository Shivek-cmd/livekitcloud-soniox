"""PR 080 — LLM-as-judge scoring of dialogue-harness transcripts (dev-only).

Applies docs/eval/naturalness_rubric.md to one or more harness output dirs
(the *.json files written by scripts/dialogue_harness.py). Mechanical checks
(repeated phrases, checkout efficiency, script/parenthetical detection) run in
code; the judgment dimensions and text-level flags go to an LLM judge. Human
review remains the authority — this ranks candidates and flags transcripts
worth reading.

Usage:
    uv run python scripts/judge_transcripts.py docs/eval/pr080/gpt-4.1-mini \
        docs/eval/pr080/gemini-3.5-flash \
        --baseline docs/eval/baseline \
        --judge-model gpt-4.1

Writes scores.json + scores.md into each input dir, and (with >1 dir) a
comparison.md next to the first dir's parent.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from dialogue_harness import completion_kwargs, create_with_retry, make_client  # noqa: E402

RUBRIC_PATH = REPO_ROOT / "docs" / "eval" / "naturalness_rubric.md"

LLM_DIMENSIONS = [
    "acknowledgement_variety",
    "sentence_length_variety",
    "code_mix_appropriateness",
    "zero_meta_speech",
    "confusion_handling_grace",
]
FLAGS = [
    "stray_language",
    "roman_indic",
    "ungrounded_dish",
    "fact_contradiction",
    "meta_speech",
    "spoken_parenthetical",
]

# ── mechanical checks ────────────────────────────────────────────────────────

ALLOWED_SCRIPT_PREFIXES = ("LATIN", "GURMUKHI", "DEVANAGARI")

# Common Roman-script renderings of Punjabi/Hindi fillers — TTS-correctness
# violations when spoken (the persona doc mandates native script).
_ROMAN_INDIC_RE = re.compile(
    r"\b(haan\s*ji|acha|accha|bilkul|dhanyavaad|dhanyavad|shukriya|"
    r"theek\s*hai|ji\s*haan|sat\s*sri\s*akal)\b",
    re.I,
)

# An Indic-script dish name immediately followed by a Latin parenthetical —
# the grounding parenthetical spoken aloud (PR 077 watch item).
_SPOKEN_PAREN_RE = re.compile(r"[ऀ-ॿ਀-੿][^()\n]*\([A-Za-z][^)]*\)")


def stray_script_chars(text: str) -> list[str]:
    """Characters whose Unicode script is outside Latin/Gurmukhi/Devanagari
    (letters only — digits/punctuation/symbols are script-neutral)."""
    bad = []
    for ch in text:
        if not ch.isalpha():
            continue
        try:
            name = unicodedata.name(ch)
        except ValueError:
            continue
        # isalpha() already restricts to letters (incl. CJK ideographs, whose
        # names lack the word LETTER) — any script outside the allowed three
        # is stray.
        if not name.startswith(ALLOWED_SCRIPT_PREFIXES):
            bad.append(ch)
    return bad


def repeated_phrase_count(agent_turns: list[str]) -> tuple[int, list[str]]:
    """Max repeat count of any normalized agent sentence or turn-opener
    (first 4 words) across the call; >2 caps acknowledgement variety at 2."""
    sentences: Counter = Counter()
    openers: Counter = Counter()
    for turn in agent_turns:
        norm_turn = re.sub(r"\s+", " ", turn.strip().lower())
        if not norm_turn:
            continue
        openers[" ".join(norm_turn.split()[:4])] += 1
        for sent in re.split(r"[.!?।]+", norm_turn):
            sent = sent.strip()
            if len(sent.split()) >= 2:
                sentences[sent] += 1
    worst = [p for p, n in (sentences + openers).items() if n > 2]
    peak = max([n for _, n in (sentences + openers).most_common(1)] or [0])
    return peak, worst


def turns_to_place(run: dict) -> int | None:
    """User turns (scripted + injected) up to and including the successful
    place_order call; None if the order was never placed."""
    count = 0
    for turn in run["turns"]:
        count += 1
        for tc in turn.get("tool_calls", []):
            if tc["name"] == "place_order" and tc["result"].startswith("Order placed"):
                return count
    return None


def mechanical_checks(run: dict, baseline_turns: int | None) -> dict:
    agent_turns = [t.get("assistant", "") for t in run["turns"]]
    speech = "\n".join(agent_turns)

    peak_repeat, repeated = repeated_phrase_count(agent_turns)
    stray = stray_script_chars(speech)
    roman = _ROMAN_INDIC_RE.findall(speech)
    parens = _SPOKEN_PAREN_RE.findall(speech)

    placed_at = turns_to_place(run)
    if placed_at is None:
        efficiency = None  # not a placement scenario (or failed — harness flags that)
    elif baseline_turns is None:
        efficiency = 5  # no baseline to compare against
    else:
        budget = baseline_turns * 1.2
        if placed_at <= budget:
            efficiency = 5
        else:
            over = (placed_at - budget) / max(baseline_turns * 0.2, 1e-9)
            efficiency = max(1, 5 - int(over) - 1)

    return {
        "peak_phrase_repeat": peak_repeat,
        "repeated_phrases": repeated[:5],
        "mech_stray_language_chars": "".join(sorted(set(stray)))[:40],
        "mech_stray_language": len(stray),
        "mech_roman_indic": len(roman),
        "mech_roman_indic_hits": sorted({m if isinstance(m, str) else m[0] for m in roman})[:5],
        "mech_spoken_parenthetical": len(parens),
        "mech_spoken_parenthetical_hits": parens[:3],
        "turns_to_place": placed_at,
        "baseline_turns_to_place": baseline_turns,
        "checkout_efficiency": efficiency,
    }


# ── LLM judge ────────────────────────────────────────────────────────────────

JUDGE_SYSTEM = """You are a strict transcript reviewer for a trilingual \
(English / Punjabi-Gurmukhi / Hindi-Devanagari) restaurant voice agent named \
Sierra. You are given the rubric, then one call transcript that includes the \
agent's tool calls and tool results. Score ONLY the agent's spoken lines \
("SIERRA:"), using tool results as ground truth for what was actually in the \
order and which dishes were surfaced by tools.

Return STRICT JSON, no markdown, with this exact shape:
{
  "scores": {
    "acknowledgement_variety": 1-5,
    "sentence_length_variety": 1-5,
    "code_mix_appropriateness": 1-5,
    "zero_meta_speech": 1-5,
    "confusion_handling_grace": 1-5
  },
  "flags": {
    "stray_language": <count>,
    "roman_indic": <count>,
    "ungrounded_dish": <count>,
    "fact_contradiction": <count>,
    "meta_speech": <count>,
    "spoken_parenthetical": <count>
  },
  "evidence": ["short quote — why it was flagged or lost points", ...]
}

Flag definitions:
- stray_language: any language other than English, Punjabi in Gurmukhi, or \
Hindi in Devanagari (e.g. Japanese, Chinese, Urdu in Perso-Arabic); also any \
phone digit spoken in a non-English script/word.
- roman_indic: Punjabi/Hindi words written in Roman letters (haan ji, bilkul).
- ungrounded_dish: a specific dish name spoken that appears in NO tool result \
and was not first named by the customer.
- fact_contradiction: spoken quantity/dish/total contradicts ADDED / ORDER NOW \
/ READBACK FACTS tool lines.
- meta_speech: narrating tools or systems, re-greeting mid-call, speaking \
tool-reply scaffolding (e.g. "ADDED:", "GUIDE:") aloud.
- spoken_parenthetical: an English parenthetical like "(Garlic Naan)" spoken \
inside a Punjabi/Hindi sentence.
Keep evidence quotes under 15 words each. Count real instances; do not pad."""


def transcript_for_judge(run: dict) -> str:
    lines = []
    for t in run["turns"]:
        lines.append(f"USER: {t['user']}")
        for tc in t.get("tool_calls", []):
            args = json.dumps(tc["args"], ensure_ascii=False)
            lines.append(f"  [tool] {tc['name']}({args}) -> {tc['result']}")
        lines.append(f"SIERRA: {t.get('assistant', '')}")
    return "\n".join(lines)


def judge_run(client, judge_model: str, rubric: str, run: dict) -> dict:
    user_prompt = (
        f"RUBRIC:\n{rubric}\n\n--- TRANSCRIPT (scenario: {run['name']}, "
        f"channel: {run['channel']}) ---\n{transcript_for_judge(run)}"
    )
    kwargs = completion_kwargs(judge_model)
    kwargs.pop("seed", None)
    response, _ = create_with_retry(
        client,
        model=judge_model,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
        **kwargs,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = {}
    scores = {d: int(parsed.get("scores", {}).get(d, 0)) for d in LLM_DIMENSIONS}
    flags = {f: int(parsed.get("flags", {}).get(f, 0)) for f in FLAGS}
    return {"scores": scores, "flags": flags, "evidence": parsed.get("evidence", [])}


# ── per-dir scoring ──────────────────────────────────────────────────────────


def load_runs(run_dir: Path) -> list[dict]:
    runs = []
    for p in sorted(run_dir.glob("*.json")):
        if p.name == "scores.json":
            continue
        runs.append(json.loads(p.read_text()))
    if not runs:
        sys.exit(f"No harness run JSON found in {run_dir}")
    return runs


def load_baseline_turns(baseline_dir: Path | None) -> dict[str, int | None]:
    if not baseline_dir or not baseline_dir.is_dir():
        return {}
    budgets = {}
    for p in sorted(baseline_dir.glob("*.json")):
        if p.name == "scores.json":
            continue
        run = json.loads(p.read_text())
        budgets[run["name"]] = turns_to_place(run)
    return budgets


def score_dir(run_dir: Path, judge_model: str, rubric: str, baselines: dict) -> dict:
    client = make_client(judge_model)
    per_scenario = []
    for run in load_runs(run_dir):
        mech = mechanical_checks(run, baselines.get(run["name"]))
        judged = judge_run(client, judge_model, rubric, run)
        # Mechanical cap: a stock phrase >2x caps acknowledgement variety at 2.
        if mech["peak_phrase_repeat"] > 2:
            judged["scores"]["acknowledgement_variety"] = min(
                judged["scores"]["acknowledgement_variety"], 2
            )
        # Merge mechanical floor counts into flags (max — the two detectors
        # overlap; the LLM sees semantics, the regexes never miss what they match).
        judged["flags"]["stray_language"] = max(
            judged["flags"]["stray_language"], mech["mech_stray_language"]
        )
        judged["flags"]["roman_indic"] = max(
            judged["flags"]["roman_indic"], mech["mech_roman_indic"]
        )
        judged["flags"]["spoken_parenthetical"] = max(
            judged["flags"]["spoken_parenthetical"], mech["mech_spoken_parenthetical"]
        )
        per_scenario.append(
            {
                "scenario": run["name"],
                "harness_passed": run["passed"],
                "scores": judged["scores"],
                "checkout_efficiency": mech["checkout_efficiency"],
                "flags": judged["flags"],
                "evidence": judged["evidence"],
                "mechanical": mech,
                "llm_latency": run.get("llm_latency", {}),
            }
        )

    dims = LLM_DIMENSIONS + ["checkout_efficiency"]
    means = {}
    for d in dims:
        vals = [
            (s["scores"].get(d) if d in s["scores"] else s.get(d))
            for s in per_scenario
        ]
        vals = [v for v in vals if v]
        means[d] = round(sum(vals) / len(vals), 2) if vals else None
    flag_totals = {f: sum(s["flags"][f] for s in per_scenario) for f in FLAGS}
    model = json.loads(next(iter(sorted(run_dir.glob("*.json")))).read_text()).get(
        "model", run_dir.name
    )
    lat = [s["llm_latency"] for s in per_scenario if s["llm_latency"]]
    mean_lat = round(sum(x["mean_s"] for x in lat) / len(lat), 3) if lat else None
    return {
        "dir": str(run_dir),
        "model": model,
        "judge_model": judge_model,
        "scenarios": per_scenario,
        "dimension_means": means,
        "flag_totals": flag_totals,
        "harness_pass_rate": f"{sum(s['harness_passed'] for s in per_scenario)}/{len(per_scenario)}",
        "mean_llm_latency_s": mean_lat,
    }


# ── output ───────────────────────────────────────────────────────────────────


def scores_markdown(result: dict) -> str:
    lines = [
        f"# Judge scores — {result['model']}",
        "",
        f"- judge: {result['judge_model']}",
        f"- harness pass rate: {result['harness_pass_rate']}",
        f"- mean LLM latency: {result['mean_llm_latency_s']}s",
        "",
        "## Dimension means (1–5)",
        "",
    ]
    for d, v in result["dimension_means"].items():
        lines.append(f"- {d}: {v}")
    lines += ["", "## Flag totals", ""]
    for f, n in result["flag_totals"].items():
        lines.append(f"- {f}: {n}")
    lines += ["", "## Per scenario", ""]
    for s in result["scenarios"]:
        flags = {k: v for k, v in s["flags"].items() if v}
        lines.append(
            f"### {s['scenario']} — harness {'PASS' if s['harness_passed'] else 'FAIL'}"
        )
        lines.append(f"- scores: {json.dumps(s['scores'])}")
        lines.append(f"- checkout_efficiency: {s['checkout_efficiency']}")
        lines.append(f"- flags: {json.dumps(flags, ensure_ascii=False) if flags else 'none'}")
        for e in s["evidence"]:
            lines.append(f"  - {e}")
        lines.append("")
    return "\n".join(lines)


def comparison_markdown(results: list[dict]) -> str:
    dims = LLM_DIMENSIONS + ["checkout_efficiency"]
    header = "| metric | " + " | ".join(r["model"] for r in results) + " |"
    sep = "|---" * (len(results) + 1) + "|"
    rows = [header, sep]
    rows.append(
        "| harness pass rate | "
        + " | ".join(r["harness_pass_rate"] for r in results)
        + " |"
    )
    rows.append(
        "| mean LLM latency (s) | "
        + " | ".join(str(r["mean_llm_latency_s"]) for r in results)
        + " |"
    )
    for d in dims:
        rows.append(
            f"| {d} | "
            + " | ".join(str(r["dimension_means"].get(d)) for r in results)
            + " |"
        )
    for f in FLAGS:
        rows.append(
            f"| flag: {f} | "
            + " | ".join(str(r["flag_totals"].get(f)) for r in results)
            + " |"
        )
    return "\n".join(
        ["# Model comparison (judge: " + results[0]["judge_model"] + ")", ""]
        + rows
        + [""]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dirs", nargs="+", type=Path, help="harness output dirs")
    parser.add_argument("--baseline", type=Path, help="baseline dir for turn budgets")
    parser.add_argument("--judge-model", default="gpt-4.1", help="judge model id")
    args = parser.parse_args()

    rubric = RUBRIC_PATH.read_text()
    baselines = load_baseline_turns(args.baseline)

    results = []
    for run_dir in args.dirs:
        print(f"── judging {run_dir} …", flush=True)
        result = score_dir(run_dir, args.judge_model, rubric, baselines)
        results.append(result)
        (run_dir / "scores.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        )
        (run_dir / "scores.md").write_text(scores_markdown(result))
        print(
            f"   means={result['dimension_means']} flags={result['flag_totals']}",
            flush=True,
        )

    if len(results) > 1:
        out = args.dirs[0].parent / "comparison.md"
        out.write_text(comparison_markdown(results))
        print(f"\ncomparison table → {out}")


if __name__ == "__main__":
    main()
