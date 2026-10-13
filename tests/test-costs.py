#!/usr/bin/env python3
"""Tests for claude-costs.

Runs against synthetic logs and a synthetic ~/.claude.json, so no API key,
no spend, and no dependence on this machine's real usage history.

    tests/test-costs.py
"""
from __future__ import annotations

import importlib.util
import importlib.machinery
import json
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
TOOL = REPO / "bin" / "claude-costs"

spec = importlib.util.spec_from_loader(
    "claude_costs", importlib.machinery.SourceFileLoader("claude_costs", str(TOOL)))
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

passed = failed = 0


def check(cond: bool, desc: str, detail: str = "") -> None:
    global passed, failed
    if cond:
        print(f"  PASS  {desc}")
        passed += 1
    else:
        print(f"  FAIL  {desc}\n     {detail}")
        failed += 1


def row(**kw) -> str:
    base = {"ts": "2026-08-13T00:00:00Z", "profile": "review", "cost_usd": 0.0,
            "is_error": False, "quality": "ok"}
    base.update(kw)
    return json.dumps(base)


def main() -> int:
    print("== local lane (agentroute ledger) ==")
    with tempfile.TemporaryDirectory() as d:
        led = pathlib.Path(d) / "requests.jsonl"
        led.write_text("\n".join([
            json.dumps({"route": "local", "iso": "2026-09-04T13:00:00", "status": 200, "wall_s": 40.0,
                        "model_out": "qwen3.8:27b-mtp-q8_0", "agent_id": "a1", "session_id": "s1",
                        "stripped_reminders": 1, "pinged": 0,
                        "usage": {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read_input_tokens": 5}}),
            json.dumps({"route": "local", "iso": "2026-09-04T13:01:00", "status": 500, "wall_s": 2.0,
                        "model_out": "qwen3.8:27b-mtp-q8_0", "agent_id": "a2", "session_id": "s1", "usage": {}}),
            json.dumps({"route": "upstream", "iso": "2026-09-04T13:02:00", "status": 200, "wall_s": 3.0,
                        "model_out": "claude-haiku-4-5", "usage": {"input_tokens": 9, "output_tokens": 9}}),
            json.dumps({"route": "local-count-estimate", "iso": "2026-09-04T13:03:00", "status": 200}),
            "not json",
        ]) + "\n")
        loc = cc.read_local_lane(led, None)
        check(loc["requests"] == 2, "only route=local rows count", str(loc["requests"]))
        check(loc["tokens"]["in"] == 1_000_000 and loc["tokens"]["out"] == 100_000, "tokens summed", str(loc["tokens"]))
        check(loc["agents"] == 2 and loc["sessions"] == 1 and loc["errors"] == 1, "agents/sessions/errors counted",
              f"{loc['agents']} {loc['sessions']} {loc['errors']}")
        check(abs(loc["wall_s"] - 42.0) < 1e-9 and loc["stripped_reminders"] == 1, "wall and stripped reminders summed")
        # 1M in @ $3 + 100k out @ $15 on Sonnet 5 = $3.00 + $1.50
        check(loc["by_backend"]["(unrecorded)"]["requests"] == 2 and loc["by_backend"]["(unrecorded)"]["errors"] == 1,
              "rows with no backend field are their own bucket, not merged into the real 'default' backend",
              str(loc["by_backend"]))
        # 1M in @ $3 + 100k out @ $15 + 5 cache reads @ $3*0.10 = 3.00 + 1.50 + ~0
        check(loc["equiv_model"] == "claude-sonnet-5" and abs(loc["equiv_usd"] - 4.5000015) < 1e-6,
              "equivalent figure prices input, output AND cache reads (it used to omit cache reads "
              "on the very line that printed them)", str(loc["equiv_usd"]))

    print("== local lane: a hostile ledger must not kill the report ==")
    with tempfile.TemporaryDirectory() as d:
        led = pathlib.Path(d) / "requests.jsonl"
        led.write_text("\n".join([
            "123", '"a string"', "[]", "not json at all", "",
            json.dumps({"route": "local", "iso": "2026-09-04T13:00:00", "status": "200", "wall_s": "x",
                        "model_out": 42, "backend": None, "agent_id": "a1",
                        "usage": {"input_tokens": "many", "output_tokens": None}}),
            json.dumps({"route": "local", "status": 200, "usage": "not-a-dict", "wall_s": 1.0}),
        ]) + "\n")
        loc = cc.read_local_lane(led, None)
        check(loc["requests"] == 2, "non-object JSON lines are skipped, not fatal", str(loc["requests"]))
        check(loc["tokens"]["in"] == 0 and loc["tokens"]["out"] == 0,
              "string/None token counts coerce to 0 instead of raising", str(loc["tokens"]))
        check(loc["errors"] == 0, 'a string "200" status counts as success, not an error', str(loc["errors"]))
        check("(unrecorded)" in loc["by_backend"], "a null backend buckets as (unrecorded)", str(list(loc["by_backend"])))
        undated = cc.read_local_lane(led, cc.dt.date(2026, 9, 5))
        check(undated["requests"] == 1 and undated["undated"] == 1,
              "--since keeps the undated row and counts it, and still filters the dated one",
              f"{undated['requests']} rows, {undated['undated']} undated")
        dated_only = pathlib.Path(d) / "dated.jsonl"
        dated_only.write_text(json.dumps({"route": "local", "iso": "2026-09-04T13:00:00", "status": 200}) + "\n")
        check(cc.read_local_lane(dated_only, cc.dt.date(2026, 9, 5))["requests"] == 0,
              "--since filters on the row's iso date")
        missing = cc.read_local_lane(pathlib.Path(d) / "absent.jsonl", None)
        check(missing["requests"] == 0 and missing["equiv_usd"] == 0.0, "absent ledger is an empty lane, not an error")

    print("== model-name canonicalization ==")
    for raw, want in (("claude-opus-5[1m]", "claude-opus-5"),
                      ("claude-haiku-4-5-20251001", "claude-haiku-4-5"),
                      ("claude-sonnet-5", "claude-sonnet-5")):
        got = cc.canonical(raw)
        check(got == want, f"{raw} -> {want}", f"got {got}")

    print("== pricing arithmetic ==")
    # 1M cache reads on Sonnet 5 ($3 in): cached 1M*3*0.10 = $0.30,
    # uncached the same tokens bill as fresh input = $3.00.
    tok = {"in": 0, "out": 0, "cr": 1_000_000, "cw": 0, "usd": 0.30}
    check(abs(cc.uncached_cost("claude-sonnet-5", tok) - 3.00) < 1e-9,
          "uncached_cost bills cache reads as fresh input",
          str(cc.uncached_cost("claude-sonnet-5", tok)))
    check(abs(cc.predicted_cost("claude-sonnet-5", tok) - 0.30) < 1e-9,
          "predicted_cost applies the cache-read multiplier",
          str(cc.predicted_cost("claude-sonnet-5", tok)))
    check(cc.uncached_cost("some-unknown-model", tok) is None,
          "unknown model is unpriced rather than assumed")

    print("== price-table self-check ==")
    # The real finding this exists for: a table entry that disagrees with what
    # was actually billed must be caught, not silently used.
    drift = cc.price_table_drift({"claude-sonnet-5": tok})
    check(drift and abs(drift[0][3]) < 0.01,
          "matching table reports ~0% error", str(drift))
    wrong = {"in": 0, "out": 0, "cr": 1_000_000, "cw": 0, "usd": 0.20}
    drift = cc.price_table_drift({"claude-sonnet-5": wrong})
    check(drift and abs(drift[0][3]) > 2.0,
          "mismatched billing is detected as drift", str(drift))

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)

        cfg = tmp / "claude.json"
        cfg.write_text(json.dumps({
            "oauthAccount": {"userRateLimitTier": "test_tier",
                             "organizationRateLimitTier": "test_org"},
            "projects": {
                "/a": {"lastModelUsage": {"claude-opus-5[1m]": {
                    "inputTokens": 100, "outputTokens": 200,
                    "cacheReadInputTokens": 300, "cacheCreationInputTokens": 400,
                    "costUSD": 12.5}}},
                "/b": {"lastModelUsage": {"claude-opus-5": {
                    "inputTokens": 1, "outputTokens": 2,
                    "cacheReadInputTokens": 3, "cacheCreationInputTokens": 4,
                    "costUSD": 7.5}}},
                "/c": {},
            },
        }))

        log = tmp / "usage.jsonl"
        log.write_text("\n".join([
            row(cost_usd=1.00, by_model={"claude-sonnet-5": {
                "in": 0, "out": 0, "cr": 1_000_000, "cw": 0, "usd": 0.30}}),
            row(cost_usd=0.50, quality="thin", by_model={"claude-sonnet-5": {
                "in": 0, "out": 0, "cr": 500_000, "cw": 0, "usd": 0.15}}),
            row(cost_usd=0.25, is_error=True, profile="explore"),  # legacy row
            row(cost_usd=2.00, ts="2020-01-01T00:00:00Z"),         # before --since
        ]) + "\n")

        def run(*extra):
            return subprocess.run(
                [sys.executable, str(TOOL), *extra],
                capture_output=True, text=True,
                env={"PATH": "/usr/bin:/bin",
                     "CLAUDE_API_AGENT_LOG": str(log),
                     "CLAUDE_CONFIG_FILE": str(cfg),
                     "HOME": str(tmp)})

        print("== lanes are read and kept separate ==")
        agg = json.loads(run("--json").stdout)
        api, sub = agg["api_lane"], agg["subscription_lane"]
        check(abs(api["actual_usd"] - 3.75) < 1e-9,
              "API total sums every row", str(api["actual_usd"]))
        check(abs(sub["equivalent_usd"] - 20.0) < 1e-9,
              "subscription total sums across projects", str(sub["equivalent_usd"]))
        check("claude-opus-5" in sub["by_model"] and len(sub["by_model"]) == 1,
              "[1m] variant folds into its base model", str(list(sub["by_model"])))
        check(sub["tier"] == "test_tier", "subscription tier is reported", str(sub["tier"]))

        print("== spend that bought nothing ==")
        check(abs(api["wasted_usd"] - 0.75) < 1e-9,
              "errored + thin runs are counted as wasted", str(api["wasted_usd"]))

        print("== unattributable rows are disclosed, not dropped ==")
        check(api["unattributed_runs"] == 2,
              "rows without by_model are counted and flagged",
              str(api["unattributed_runs"]))
        # 3.75 total includes $2.25 of rows that carry no per-model data; the
        # cache figure must be computed only from what is attributable.
        check(abs(api["uncached_equivalent_usd"] - 4.5) < 1e-9,
              "uncached equivalent uses only attributable tokens",
              str(api["uncached_equivalent_usd"]))
        # C1: the saving compares list_cost against the ACTUAL of the same
        # priced rows ($0.45 = 0.30 + 0.15 from the two GOOD-cost:* rows), not
        # against api_total which folds in $2.25 of unattributable spend.
        # 4.5 - 0.45 = 4.05, not 4.5 - 3.75 = 0.75.
        check(abs(api["cache_saving_usd"] - 4.05) < 1e-9,
              "C1: cache saving compares like with like",
              str(api["cache_saving_usd"]))
        check(abs(api["cache_saving_basis_usd"] - 0.45) < 1e-9,
              "C1: saving basis is the attributable actual",
              str(api.get("cache_saving_basis_usd")))

        print("== --since filters ==")
        agg2 = json.loads(run("--json", "--since", "2026-01-01").stdout)
        check(abs(agg2["api_lane"]["actual_usd"] - 1.75) < 1e-9,
              "--since excludes older runs", str(agg2["api_lane"]["actual_usd"]))

        print("== human output ==")
        text = run().stdout
        check("API LANE" in text and "SUBSCRIPTION LANE" in text,
              "both lanes are labelled")
        check("not exposed in any" in text,
              "session-window limitation is stated, not guessed")
        check("$3.7500" in text, "actual spend is shown", text[:200])

        print("== drift withholds the cache figure ==")
        bad = tmp / "bad.jsonl"
        bad.write_text(row(cost_usd=0.20, by_model={"claude-sonnet-5": {
            "in": 0, "out": 0, "cr": 1_000_000, "cw": 0, "usd": 0.20}}) + "\n")
        out = subprocess.run(
            [sys.executable, str(TOOL)], capture_output=True, text=True,
            env={"PATH": "/usr/bin:/bin", "CLAUDE_API_AGENT_LOG": str(bad),
                 "CLAUDE_CONFIG_FILE": str(cfg), "HOME": str(tmp)}).stdout
        check("PRICE TABLE DISAGREES" in out and "prompt cache saved" not in out,
              "a wrong price table withholds the cache figure", out[-400:])
        check("$0.2000" in out,
              "actual spend still reported when the table is wrong", out[:300])

    print("== attribution and efficiency ==")
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        cfg = tmp / "c.json"; cfg.write_text("{}")

        def tagged(exp, phase, usd, **kw):
            d = {"ts": "2026-08-13T00:00:00Z", "profile": kw.get("profile", "review"),
                 "cost_usd": usd, "is_error": kw.get("is_error", False),
                 "quality": kw.get("quality", "ok"), "turns": 4,
                 "denial_count": kw.get("denials", 0), "findings_count": 2,
                 "tags": {"id": exp, "phase": phase},
                 "by_model": {"claude-sonnet-5": {
                     "in": 100, "out": kw.get("out", 1000),
                     "cr": kw.get("cr", 20000), "cw": kw.get("cw", 5000), "usd": usd}}}
            return json.dumps(d)

        log = tmp / "exp.jsonl"
        log.write_text("\n".join([
            tagged("e1", "triage", 2.00),
            tagged("e1", "fix", 0.50),
            tagged("e1", "fix", 0.50),
            tagged("e2", "fix", 1.00, quality="thin"),
        ]) + "\n")

        def run(*extra):
            return subprocess.run(
                [sys.executable, str(TOOL), *extra], capture_output=True, text=True,
                env={"PATH": "/usr/bin:/bin", "CLAUDE_API_AGENT_LOG": str(log),
                     "CLAUDE_CONFIG_FILE": str(cfg), "HOME": str(tmp)})

        agg = json.loads(run("--json").stdout)
        eff, phases = agg["efficiency"], agg["by_phase"]
        heads = " | ".join(a["headline"] for a in agg["advice"])

        check(abs(phases["fix"]["usd"] - 2.0) < 1e-9 and phases["fix"]["runs"] == 3,
              "phase tags roll spend up per phase", str(phases))
        check(abs(phases["triage"]["usd"] - 2.0) < 1e-9,
              "deciding spend is separated from doing spend", str(phases))
        check(eff["usable_runs"] == 3 and abs(eff["waste_rate"] - 0.25) < 1e-9,
              "thin run counts against the waste rate", str(eff["waste_rate"]))
        check(abs(eff["usd_per_usable_run"] - 4.0 / 3) < 1e-6,
              "cost per usable run divides by usable runs only",
              str(eff["usd_per_usable_run"]))
        check(abs(eff["cache_hit_rate"] - 20000 / 25100) < 1e-6,
              "cache hit rate is reads over all input tokens",
              str(eff["cache_hit_rate"]))

        # C3: output share must price cache tokens at their multipliers. The
        # fixture is all Sonnet-5 ($3/$15). Pricing cache at the full input
        # rate would balloon the input side and collapse this share toward the
        # value that suppressed the "output dominates" advisory.
        by = agg["api_lane"]["by_model"]["claude-sonnet-5"]
        in_cost = (by["in"] * 3 + by["cr"] * 3 * 0.10 + by["cw"] * 3 * 1.25) / 1e6
        out_cost = by["out"] * 15 / 1e6
        expected_share = out_cost / (out_cost + in_cost)
        check(abs(eff["output_cost_share"] - expected_share) < 1e-9,
              "C3: output share prices cache tokens at their multipliers",
              f"{eff['output_cost_share']} vs {expected_share}")

        check("deciding costs 50%" in heads,
              "overhead rule fires when triage dominates", heads)
        check("bought nothing" in heads, "waste rule fires", heads)

        # The overhead rule must not impose one vocabulary: a caller whose
        # phases are named differently can redefine or disable it.
        heads_off = " | ".join(
            a["headline"] for a in
            json.loads(run("--json", "--overhead-phases", "").stdout)["advice"])
        check("deciding costs" not in heads_off,
              "empty --overhead-phases disables the overhead rule", heads_off)
        heads_alt = " | ".join(
            a["headline"] for a in
            json.loads(run("--json", "--overhead-phases", "fix").stdout)["advice"])
        check("deciding costs 50%" in heads_alt,
              "--overhead-phases redefines which phases count as overhead",
              heads_alt)

        # An id present in the rows is rolled up without needing --by; the
        # whole point of stamping it is that the answer is not behind a flag.
        auto = run().stdout
        check("by id:" in auto, "id rolls up automatically", auto[-500:])

        text = run("--by", "id").stdout
        check("by id:" in text and "e1" in text and "e2" in text,
              "--by groups spend along a tag key", text[-400:])

        # Below every threshold, the advisory must say so rather than invent work.
        quiet = tmp / "quiet.jsonl"
        quiet.write_text("\n".join(
            tagged("e", "fix", 0.50, out=100, cr=90000, cw=1000) for _ in range(3)) + "\n")
        out = subprocess.run(
            [sys.executable, str(TOOL)], capture_output=True, text=True,
            env={"PATH": "/usr/bin:/bin", "CLAUDE_API_AGENT_LOG": str(quiet),
                 "CLAUDE_CONFIG_FILE": str(cfg), "HOME": str(tmp)}).stdout
        check("nothing to flag" in out,
              "clean data produces no manufactured advice", out[-300:])

    print("== the 5.x price rows (packet a-s3, ruling 9) ==")
    for m, want in (("claude-opus-5-5", (4.00, 20.00)), ("claude-fable-5-1", (10.00, 50.00)),
                    ("claude-sonnet-5-5", (2.00, 10.00)), ("claude-haiku-5-5", (0.10, 0.50))):
        check(cc.rates(m) == want, f"{m} is priced at {want[0]:g}/{want[1]:g}", str(cc.rates(m)))
        check(cc.rates(m + "[1m]") == want, f"{m}[1m] folds into {m}", str(cc.rates(m + "[1m]")))
    one_m_read = {"in": 0, "out": 0, "cr": 1_000_000, "cw": 0}
    for m, want in (("claude-opus-5-5", 0.20), ("claude-sonnet-5-5", 0.20), ("claude-fable-5-1", 0.25),
                    ("claude-haiku-5-5", 0.10 * cc.CACHE_READ_MULT),
                    ("claude-sonnet-5", 3.00 * cc.CACHE_READ_MULT)):
        got = cc.predicted_cost(m, one_m_read)
        check(got is not None and abs(got - want) < 1e-12,
              f"{m}: 1M cache reads cost ${want:g} (a per-model rate overrides the multiplier "
              f"where the list names one)", str(got))
    got = cc.predicted_cost("claude-opus-5-5", {"in": 1000, "out": 2000, "cr": 100_000, "cw": 10_000})
    check(got is not None and abs(got - 0.114) < 1e-12,
          "opus 5.5: input, output, cache read and cache write together", str(got))
    check(cc.rates("claude-sonnet-5") == (3.00, 15.00), "claude-sonnet-5 stays at the billed 3/15",
          str(cc.rates("claude-sonnet-5")))

    print("== --check-prices ==")
    out = subprocess.run([sys.executable, str(TOOL), "--check-prices"],
                         capture_output=True, text=True).stdout
    check("claude-opus-5" in out and "cache read" in out,
          "price table is printable for review")
    check(all(m in out for m in ("claude-opus-5-5", "claude-fable-5-1", "claude-sonnet-5-5",
                                 "claude-haiku-5-5")),
          "the 5.x rows are in the printed table", out[:600])

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
