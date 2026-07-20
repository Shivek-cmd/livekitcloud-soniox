"""PR 074 — dialogue eval harness (dev-only, real LLM calls, no audio).

PR 080: multi-provider — pass --model gemini-2.5-flash (any gemini-* id) to
drive the same tool-loop through Gemini's OpenAI-compatible endpoint using
GEMINI_API_KEY; the transcript/tool-loop/assertion machinery is identical, so
model comparisons are apples-to-apples. Gemini rejects OpenAI's `seed` param,
so it is omitted there (runs are near-deterministic at temperature 0 anyway).

Drives the real RestaurantAgent tools through a scripted customer
conversation so conversation-layer changes (PRs 074–080) have a measurable
before/after. No LiveKit session exists — the agent is null-safe headless
(_sync_web/_record_tool no-op; place_order has a no-session branch), so the
real menu resolution, gates, and cart run exactly as in production while the
LLM is driven through a manual tool-loop at temperature 0.

What this deliberately does NOT simulate: the audio path (STT/TTS, echo/
background/noise filters in on_user_turn_completed) — those are channel
hygiene, not conversation logic. Language tracking and real_user_turns ARE
mirrored, matching the tail of the runtime turn hook.

Usage:
    uv run python scripts/dialogue_harness.py                      # all scenarios
    uv run python scripts/dialogue_harness.py --scenario english_pickup
    uv run python scripts/dialogue_harness.py --out docs/eval/baseline

Scenario files live in tests/scenarios/*.json:
    {
      "name": "english_pickup",
      "channel": "phone",                 # "phone" | "web"
      "turns": ["Hi, ...", "..."],        # customer lines, in order
      "reactive": [                        # optional: answered BEFORE the queue
        {"when": "(?i)address", "say": "12 Main St", "max_uses": 2}
      ],
      "readback_verify": "strict",        # optional: pin READBACK_VERIFY for this run
      "censor_speech": [                   # optional: strip text from the SPOKEN
        {"text": "Garlic Naan", "max_uses": 1}   # readback fed to the verifier
      ],
      "expect": {
        "placed": true,
        "items": [{"name": "Butter Chicken", "qty": 2, "note_contains": "medium"}],
        "order_type": "pickup",
        "customer_name": "Harpreet",
        "customer_phone": "6475551212",
        "additional_requests_recorded": true,
        "min_readbacks": 1,
        "transcript_any": ["..."],        # ≥1 substring must appear in agent speech
        "transcript_none": ["..."],       # none of these may appear
        "tool_result_contains": [          # ≥min tool results must contain substring
          {"tool": "confirm_readback", "contains": "READBACK INCOMPLETE", "min": 1}
        ]
      }
    }
All expect keys are optional. One invariant runs on every scenario regardless:
a placed order implies the readback was confirmed at the final cart revision.

Turn selection: before consuming the next scripted line, the harness checks the
agent's last reply against (a) the scenario's "reactive" rules (specific
answers win — a combined "is that number right? pickup or delivery?" must get
"Delivery please.", not a bare "Yes."), then (b) a built-in phone-digit
confirm ("...six, four, seven... — is that correct?" → injected "Yes."). Injected replies do NOT consume the scripted queue. This
absorbs the agent's optional clarifying questions (whether it double-checks the
phone number varies run to run even at temperature 0), which would otherwise
shift every following scripted line one question off.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # runnable as `python scripts/dialogue_harness.py`

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from livekit.agents.llm import utils as llm_utils  # noqa: E402
from openai import OpenAI  # noqa: E402

from restaurant.agent.core import RestaurantAgent  # noqa: E402
from restaurant.agent.language import OPENING_GREETING, update_preferred_language  # noqa: E402
from restaurant.voice_stack import is_gemini_model, llm_model_name  # noqa: E402

GEMINI_OPENAI_COMPAT_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def make_client(model: str) -> OpenAI:
    """OpenAI SDK client for the given model id, any provider.

    gemini-* ids go through Gemini's OpenAI-compatible endpoint so the whole
    tool-loop below runs unchanged for both providers.
    """
    if is_gemini_model(model):
        api_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv(
            "GOOGLE_API_KEY", ""
        ).strip()
        if not api_key:
            sys.exit("GEMINI_API_KEY (or GOOGLE_API_KEY) required for gemini models")
        return OpenAI(api_key=api_key, base_url=GEMINI_OPENAI_COMPAT_URL)
    return OpenAI()


def create_with_retry(client: OpenAI, **kwargs):
    """chat.completions.create with the two retries batch eval actually needs:
    - OpenAI 429 TPM limits (gpt-4.1 at 30k TPM can't do 10 scenarios
      back-to-back) → exponential-ish sleep and retry;
    - Gemini's compat endpoint occasionally returning a completion whose
      message is None → retry, then surface an error string for the turn.
    """
    from openai import APIStatusError, RateLimitError

    last_error = "no response"
    for attempt in range(6):
        attempt_started = time.monotonic()
        try:
            response = client.chat.completions.create(**kwargs)
        except RateLimitError as e:
            last_error = f"rate limited: {e}"
            time.sleep(min(15 * (attempt + 1), 60))
            continue
        except APIStatusError as e:
            if e.status_code >= 500:  # transient provider hiccup
                last_error = f"HTTP {e.status_code}: {e}"
                time.sleep(5 * (attempt + 1))
                continue
            raise
        choices = response.choices or []
        if choices and choices[0].message is not None:
            # Elapsed time of the SUCCESSFUL attempt only — retry backoff
            # must not pollute the per-call latency stats.
            return response, time.monotonic() - attempt_started
        finish = choices[0].finish_reason if choices else "no choices"
        last_error = f"completion had no message (finish_reason={finish})"
        time.sleep(2)
    raise RuntimeError(f"LLM call failed after retries: {last_error}")


def completion_kwargs(model: str) -> dict:
    """Per-provider extras. Mirrors the runtime config choices:
    - OpenAI: seed for (near-)reproducibility.
    - Gemini: no seed (compat endpoint rejects it); thinking disabled like
      build_llm's thinking_budget=0 ("none" is invalid for pro → "low").
    """
    if is_gemini_model(model):
        # NOTE: the compat endpoint accepts no safety_settings (probed —
        # extra_body.google only knows cached_content/thinking_config), and
        # the block observed on delivery_split_phone is finish_reason
        # PROHIBITED_CONTENT, Google's NON-configurable filter — it cannot be
        # disabled via the native API either. Recorded as a turn error; it is
        # model-decision evidence, not a harness bug.
        return {"reasoning_effort": "low" if "pro" in model else "none"}
    return {"seed": 7}

SCENARIO_DIR = REPO_ROOT / "tests" / "scenarios"
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "eval" / "baseline"

# A single customer turn should never need more LLM round-trips than this;
# more means the model is looping (counts as a scenario failure, not a hang).
MAX_TOOL_ROUNDS_PER_TURN = 6

# Injected (non-scripted) replies allowed per scenario — bounds reactive rules
# so a repeated agent question can't loop the harness forever.
MAX_INJECTED_TURNS = 6

# Built-in reactive rule: the agent often (not always) reads the saved phone
# number back as English word digits and asks if it's correct. Answer yes
# without consuming a scripted line. Matches ≥6 spoken digit words + a "?" —
# the English-word-digits rule is a hard TTS invariant, so this stays valid
# across prompt rewrites; the order readback never contains 6+ digit words.
_DIGIT_WORD_RE = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine)\b", re.I
)


def _is_phone_confirm_question(text: str) -> bool:
    return "?" in text and len(_DIGIT_WORD_RE.findall(text)) >= 6


@dataclass
class ToolCallRecord:
    name: str
    args: dict
    result: str


@dataclass
class TurnRecord:
    user: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    assistant: str = ""
    injected: bool = False  # reactive/built-in reply, not from the script
    error: str | None = None


@dataclass
class ScenarioRun:
    name: str
    channel: str
    model: str
    turns: list[TurnRecord] = field(default_factory=list)
    final_cart: dict = field(default_factory=dict)
    assertions: list[dict] = field(default_factory=list)
    llm_latencies: list[float] = field(default_factory=list)  # seconds per LLM call

    @property
    def passed(self) -> bool:
        return all(a["ok"] for a in self.assertions) and not any(
            t.error for t in self.turns
        )


def _build_tools(agent: RestaurantAgent) -> tuple[list[dict], dict]:
    """OpenAI tool schemas + name→callable map from the agent's real tools."""
    schemas: list[dict] = []
    by_name: dict = {}
    for tool in agent.tools:
        schema = llm_utils.build_legacy_openai_schema(tool, internally_tagged=True)
        # internally_tagged leaves "type": "function" INSIDE the function
        # object; OpenAI ignores the extra key, Gemini's compat endpoint 400s.
        schema = {k: v for k, v in schema.items() if k != "type"}
        schemas.append({"type": "function", "function": schema})
        by_name[schema["name"]] = tool
    return schemas, by_name


async def _exec_tool(tool, args: dict) -> str:
    result = await tool(**args)
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)


async def run_scenario(scenario: dict, model: str) -> ScenarioRun:
    # PR 078 — adversarial readback testing: "readback_verify" pins the env
    # mode for this run; "censor_speech" entries strip a substring from what
    # is fed to note_agent_speech while a readback is pending, simulating a
    # sloppy/truncated SPOKEN readback without touching the LLM context.
    env_mode = scenario.get("readback_verify")
    prev_mode = os.environ.get("READBACK_VERIFY")
    if env_mode:
        os.environ["READBACK_VERIFY"] = env_mode
    try:
        return await _run_scenario_inner(scenario, model)
    finally:
        if env_mode:
            if prev_mode is None:
                os.environ.pop("READBACK_VERIFY", None)
            else:
                os.environ["READBACK_VERIFY"] = prev_mode


async def _run_scenario_inner(scenario: dict, model: str) -> ScenarioRun:
    channel = scenario.get("channel", "phone")
    agent = RestaurantAgent(is_phone=channel == "phone")
    tools, tools_by_name = _build_tools(agent)
    client = make_client(model)
    extra_kwargs = completion_kwargs(model)

    run = ScenarioRun(name=scenario["name"], channel=channel, model=model)
    # The opening greeting is spoken by code (session.say) before the LLM's
    # first turn — seed it so the LLM sees the same context as in production.
    messages: list[dict] = [
        {"role": "system", "content": agent.instructions},
        {"role": "assistant", "content": OPENING_GREETING},
    ]
    agent.note_agent_speech(OPENING_GREETING)

    reactive = [
        {
            "when": re.compile(r["when"]),
            "say": r["say"],
            "uses_left": int(r.get("max_uses", 1)),
        }
        for r in scenario.get("reactive", [])
    ]
    censor = [
        {"text": c["text"], "uses_left": int(c.get("max_uses", 1))}
        for c in scenario.get("censor_speech", [])
    ]
    pending = deque(scenario["turns"])
    injected_count = 0
    last_assistant = ""

    while pending:
        user_text: str | None = None
        injected = False
        if injected_count < MAX_INJECTED_TURNS:
            # Scenario reactive rules first — they are specific ("Delivery
            # please." to a pickup-or-delivery question) while the built-in
            # phone confirm is generic. A combined question ("…is that number
            # right? Pickup or delivery?") answered with a bare "Yes." makes
            # the model guess the order type.
            for rule in reactive:
                if rule["uses_left"] > 0 and rule["when"].search(last_assistant):
                    rule["uses_left"] -= 1
                    user_text, injected = rule["say"], True
                    break
            if user_text is None and _is_phone_confirm_question(last_assistant):
                user_text, injected = "Yes.", True
        if user_text is None:
            user_text = pending.popleft()
        else:
            injected_count += 1

        turn = TurnRecord(user=user_text, injected=injected)
        run.turns.append(turn)

        # Mirror the non-filter tail of on_user_turn_completed.
        agent.state.preferred_language = update_preferred_language(
            agent.state.preferred_language, user_text
        )
        agent.state.real_user_turns += 1

        messages.append({"role": "user", "content": user_text})

        for round_no in range(MAX_TOOL_ROUNDS_PER_TURN + 1):
            if round_no == MAX_TOOL_ROUNDS_PER_TURN:
                turn.error = f"tool loop exceeded {MAX_TOOL_ROUNDS_PER_TURN} rounds"
                break
            try:
                response, elapsed = create_with_retry(
                    client,
                    model=model,
                    messages=messages,
                    tools=tools,
                    temperature=0,
                    **extra_kwargs,
                )
            except RuntimeError as e:
                turn.error = str(e)
                break
            run.llm_latencies.append(elapsed)
            msg = response.choices[0].message
            if not msg.tool_calls:
                turn.assistant = (msg.content or "").strip()
                messages.append({"role": "assistant", "content": turn.assistant})
                noted = turn.assistant
                if agent.state.readback_pending:
                    for c in censor:
                        if c["uses_left"] > 0 and c["text"] in noted:
                            noted = noted.replace(c["text"], "")
                            c["uses_left"] -= 1
                agent.note_agent_speech(noted)
                break

            # Round-trip the raw assistant message rather than reconstructing
            # it: Gemini 3 returns thought signatures as extra fields on the
            # tool calls and 400s if they aren't echoed back verbatim.
            messages.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except ValueError:
                    args = {}
                tool = tools_by_name.get(name)
                if tool is None:
                    result = f"ERROR: unknown tool '{name}'"
                else:
                    try:
                        result = await _exec_tool(tool, args)
                    except Exception as e:  # record, don't crash the run
                        result = f"ERROR: {type(e).__name__}: {e}"
                turn.tool_calls.append(ToolCallRecord(name=name, args=args, result=result))
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )

        last_assistant = turn.assistant

    run.final_cart = agent.cart.to_state_dict()
    run.assertions = _run_assertions(scenario.get("expect", {}), agent, run)
    return run


# ── machine assertions ───────────────────────────────────────────────────────


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail}


def _run_assertions(expect: dict, agent: RestaurantAgent, run: ScenarioRun) -> list[dict]:
    checks: list[dict] = []
    cart = agent.cart
    state = agent.state
    all_tool_calls = [tc for t in run.turns for tc in t.tool_calls]
    agent_speech = "\n".join(t.assistant for t in run.turns)

    # Invariant (every scenario): placed ⇒ readback confirmed at final revision.
    if cart.placed:
        confirmed_ok = state.readback_confirmed and state.readback_revision == cart.revision
        checks.append(
            _check(
                "gates: placed order had a confirmed, current readback",
                confirmed_ok,
                f"readback_confirmed={state.readback_confirmed} "
                f"readback_revision={state.readback_revision} cart.revision={cart.revision}",
            )
        )

    if "placed" in expect:
        checks.append(
            _check("placed", cart.placed == expect["placed"], f"cart.placed={cart.placed}")
        )

    if "items" in expect:
        got = {i.name: i for i in cart.items}
        want = expect["items"]
        names_ok = sorted(got) == sorted(w["name"] for w in want)
        checks.append(
            _check("items: exact set of dishes", names_ok, f"cart={sorted(got)}")
        )
        for w in want:
            line = got.get(w["name"])
            if line is None:
                continue  # covered by the set check above
            if "qty" in w:
                checks.append(
                    _check(
                        f"items: {w['name']} qty == {w['qty']}",
                        line.quantity == w["qty"],
                        f"got qty={line.quantity}",
                    )
                )
            if "note_contains" in w:
                checks.append(
                    _check(
                        f"items: {w['name']} note contains '{w['note_contains']}'",
                        w["note_contains"].lower() in (line.note or "").lower(),
                        f"got note='{line.note}'",
                    )
                )

    for key, actual in (
        ("order_type", cart.order_type),
        ("customer_name", cart.customer_name),
        ("customer_phone", cart.customer_phone),
    ):
        if key in expect:
            checks.append(_check(key, actual == expect[key], f"got {actual!r}"))

    if "additional_requests_recorded" in expect:
        checks.append(
            _check(
                "additional_requests_recorded",
                state.additional_requests_recorded == expect["additional_requests_recorded"],
                f"got {state.additional_requests_recorded}",
            )
        )

    if "min_readbacks" in expect:
        n = sum(
            1
            for tc in all_tool_calls
            if tc.name == "get_order_readback" and not tc.result.startswith("Cannot")
        )
        checks.append(
            _check(
                f"readbacks: at least {expect['min_readbacks']} successful",
                n >= expect["min_readbacks"],
                f"got {n}",
            )
        )

    for spec in expect.get("tool_result_contains", []):
        wanted = int(spec.get("min", 1))
        n = sum(
            1
            for tc in all_tool_calls
            if tc.name == spec["tool"] and spec["contains"] in tc.result
        )
        checks.append(
            _check(
                f"tool {spec['tool']} result contains '{spec['contains']}' "
                f"at least {wanted}x",
                n >= wanted,
                f"got {n}",
            )
        )

    if "transcript_any" in expect:
        hit = any(s.lower() in agent_speech.lower() for s in expect["transcript_any"])
        checks.append(
            _check(f"transcript contains one of {expect['transcript_any']}", hit)
        )

    if "transcript_none" in expect:
        for s in expect["transcript_none"]:
            checks.append(
                _check(
                    f"transcript never contains '{s}'",
                    s.lower() not in agent_speech.lower(),
                )
            )

    return checks


# ── output ───────────────────────────────────────────────────────────────────


def _run_to_dict(run: ScenarioRun) -> dict:
    return {
        "name": run.name,
        "channel": run.channel,
        "model": run.model,
        "passed": run.passed,
        "turns": [
            {
                "user": t.user,
                "tool_calls": [
                    {"name": tc.name, "args": tc.args, "result": tc.result}
                    for tc in t.tool_calls
                ],
                "assistant": t.assistant,
                **({"injected": True} if t.injected else {}),
                **({"error": t.error} if t.error else {}),
            }
            for t in run.turns
        ],
        "final_cart": run.final_cart,
        "assertions": run.assertions,
        "llm_latency": _latency_stats(run.llm_latencies),
    }


def _latency_stats(latencies: list[float]) -> dict:
    if not latencies:
        return {}
    ordered = sorted(latencies)
    return {
        "calls": len(ordered),
        "mean_s": round(sum(ordered) / len(ordered), 3),
        "p95_s": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 3),
        "max_s": round(ordered[-1], 3),
    }


def _run_to_markdown(run: ScenarioRun) -> str:
    lines = [
        f"# Scenario: {run.name}",
        "",
        f"- channel: {run.channel}",
        f"- model: {run.model}",
        f"- result: {'PASS' if run.passed else 'FAIL'}",
        "",
        "## Transcript",
        "",
        f"**SIERRA (greeting):** {OPENING_GREETING}",
        "",
    ]
    for t in run.turns:
        label = "USER (reactive)" if t.injected else "USER"
        lines.append(f"**{label}:** {t.user}")
        for tc in t.tool_calls:
            args = json.dumps(tc.args, ensure_ascii=False)
            result = tc.result.replace("\n", " ⏎ ")
            lines.append(f"> `{tc.name}({args})` → {result}")
        lines.append(f"**SIERRA:** {t.assistant}")
        if t.error:
            lines.append(f"**ERROR:** {t.error}")
        lines.append("")
    lines += ["## Final cart", "", "```json", json.dumps(run.final_cart, indent=2, ensure_ascii=False), "```", "", "## Assertions", ""]
    for a in run.assertions:
        mark = "✅" if a["ok"] else "❌"
        detail = f" — {a['detail']}" if a["detail"] else ""
        lines.append(f"- {mark} {a['check']}{detail}")
    lines.append("")
    return "\n".join(lines)


def _load_scenarios(only: str | None) -> list[dict]:
    paths = sorted(SCENARIO_DIR.glob("*.json"))
    scenarios = []
    for p in paths:
        s = json.loads(p.read_text())
        s.setdefault("name", p.stem)
        if only and s["name"] != only:
            continue
        scenarios.append(s)
    if not scenarios:
        sys.exit(f"No scenarios matched (looked in {SCENARIO_DIR})")
    return scenarios


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenario", help="run only this scenario name")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="output dir")
    parser.add_argument(
        "--model",
        default=llm_model_name(),
        help="model id (OpenAI, or gemini-* via the OpenAI-compat endpoint)",
    )
    args = parser.parse_args()

    scenarios = _load_scenarios(args.scenario)
    args.out.mkdir(parents=True, exist_ok=True)

    results: list[ScenarioRun] = []
    for scenario in scenarios:
        print(f"── {scenario['name']} ({scenario.get('channel', 'phone')}) …", flush=True)
        run = asyncio.run(run_scenario(scenario, args.model))
        results.append(run)
        (args.out / f"{run.name}.json").write_text(
            json.dumps(_run_to_dict(run), indent=2, ensure_ascii=False) + "\n"
        )
        (args.out / f"{run.name}.md").write_text(_run_to_markdown(run))
        print(f"   {'PASS' if run.passed else 'FAIL'}")

    summary = [
        "# Dialogue harness summary",
        "",
        f"- model: {args.model}",
        f"- scenarios: {len(results)}, passed: {sum(r.passed for r in results)}",
        "",
    ]
    for r in results:
        failed = [a["check"] for a in r.assertions if not a["ok"]]
        errors = [t.error for t in r.turns if t.error]
        note = f" — failed: {failed}{errors}" if (failed or errors) else ""
        summary.append(f"- {'✅' if r.passed else '❌'} {r.name}{note}")
    all_latencies = [s for r in results for s in r.llm_latencies]
    if all_latencies:
        stats = _latency_stats(all_latencies)
        summary.append("")
        summary.append(
            f"- llm latency (per call): mean {stats['mean_s']}s, "
            f"p95 {stats['p95_s']}s, max {stats['max_s']}s over {stats['calls']} calls"
        )
    summary.append("")
    (args.out / "summary.md").write_text("\n".join(summary))

    print(f"\n{sum(r.passed for r in results)}/{len(results)} scenarios passed → {args.out}")
    if not all(r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
