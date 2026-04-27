"""Sentinel Core - CLI entry point and pipeline demo."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sentinel_core import CPGBuilder, CodeParser, configure_logging, get_logger, settings
from sentinel_core.agents import run_pipeline
from sentinel_core.llm.config import DEFAULT_MODEL, get_llm

configure_logging(level=settings.log_level.value, json_output=settings.json_logs)
log = get_logger(__name__)

_DEMO_SOURCE = """\
import os
import pickle
import yaml

def handle_request(user_input: str):
    # CWE-95: arbitrary code execution via eval
    result = eval(user_input)

    # CWE-78: OS command injection
    os.system("echo " + user_input)

    # CWE-502: unsafe pickle deserialisation
    obj = pickle.loads(user_input.encode())

    # CWE-502: unsafe YAML load
    cfg = yaml.load(user_input)

    return result
"""

_SEP = "=" * 72
_LINE = "-" * 72


def _display(result: dict) -> None:
    vulns = result.get("vulnerabilities", [])
    reasoning = result.get("reasoning", [])
    patches = result.get("proposed_patches", [])
    patch_report = result.get("patch_report", {})
    verifications = result.get("verification_results", [])
    sandbox = result.get("sandbox_verification", {})
    score = result.get("confidence_score", 0.0)
    breakdown = result.get("confidence_breakdown", {})
    source_code = result.get("source_code", "")
    llm_model = result.get("llm_model", "rule-based")

    G = "\033[32m"  # green
    R = "\033[31m"  # red
    Y = "\033[33m"  # yellow
    C = "\033[36m"  # cyan
    B = "\033[1m"   # bold
    RST = "\033[0m"  # reset

    print(f"\n{_SEP}")
    print(f"  {B}SENTINEL CORE - Security Analysis Report{RST}")
    llm_active = llm_model not in ("rule-based", "none", "")
    model_tag = f"{G}{llm_model}{RST}" if llm_active else f"{Y}rule-based (no API key){RST}"
    print(f"  Analysis engine : {model_tag}")
    print(_SEP)

    # ── [1] Original code with line numbers ───────────────────────────
    print(f"\n  {B}[1] ORIGINAL CODE{RST}")
    print(f"  {_LINE}")
    if source_code:
        for i, line in enumerate(source_code.splitlines()):
            marker = ""
            for v in vulns:
                loc = v.get("location", "")
                if f"line {i}" == loc:
                    marker = f"  {R}<-- {v.get('kind', '?')}{RST}"
                    break
            print(f"  {C}{i:>3}{RST} | {line}{marker}")

    # ── [2] Vulnerabilities ───────────────────────────────────────────
    print(f"\n  {B}[2] VULNERABILITIES DETECTED ({len(vulns)}){RST}")
    print(f"  {_LINE}")
    if not vulns:
        print(f"  {G}No vulnerabilities detected.{RST}")
    else:
        for i, v in enumerate(vulns, 1):
            sev = v.get("severity", "?")
            sev_color = R if sev == "HIGH" else Y
            print(f"  {i}. {sev_color}[{sev}]{RST} {v.get('kind')} @ {v.get('location')}")
            print(f"     {v.get('description')}")

    # ── [3] Root-cause analysis ───────────────────────────────────────
    ctx_info = patch_report.get("context_info", [])
    print(f"\n  {B}[3] ROOT-CAUSE ANALYSIS{RST}")
    print(f"  {_LINE}")
    if ctx_info:
        for info in ctx_info:
            fn = info.get("function", "<module>")
            print(f"  {R}[{info.get('cwe', '?')}]{RST} {info.get('kind')} "
                  f"@ {info.get('location')} {C}(in {fn}){RST}")
            print(f"    Fix: {info.get('fix', '')}")
            if info.get("llm_strategy"):
                print(f"    {C}LLM strategy : {info['llm_strategy']}{RST}")
            if info.get("llm_rationale"):
                print(f"    {C}LLM rationale: {info['llm_rationale']}{RST}")
            if info.get("llm_test_hint"):
                print(f"    {C}LLM test hint: {info['llm_test_hint']}{RST}")
    elif reasoning:
        for block in reasoning:
            for line in block.splitlines():
                print(f"    {line}")
            print()
    else:
        print("  (skipped)")

    # ── [4] Proposed fixes ────────────────────────────────────────────
    print(f"\n  {B}[4] PROPOSED FIXES{RST}")
    print(f"  {_LINE}")
    if not patches:
        print("  (no patches)")
    else:
        for p in patches:
            print(f"  {R}- {p.get('original')}{RST}  ->  {G}+ {p.get('patched')}{RST}")
            print(f"    Location: {p.get('target_location', '?')}")

    # ── [5] Unified diff ──────────────────────────────────────────────
    diff = patch_report.get("diff", "")
    changes = patch_report.get("changes", [])
    print(f"\n  {B}[5] UNIFIED DIFF{RST}")
    print(f"  {_LINE}")
    if diff:
        print(f"  Changes applied ({len(changes)}):")
        for c in changes:
            print(f"    * {c}")
        print()
        for line in diff.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                print(f"  {B}{line}{RST}")
            elif line.startswith("+"):
                print(f"  {G}{line}{RST}")
            elif line.startswith("-"):
                print(f"  {R}{line}{RST}")
            elif line.startswith("@@"):
                print(f"  {C}{line}{RST}")
            else:
                print(f"  {line}")
    else:
        print("  (no diff generated)")

    # ── [6] Static verification ───────────────────────────────────────
    print(f"\n  {B}[6] STATIC VERIFICATION{RST}")
    print(f"  {_LINE}")
    if not verifications:
        print("  (no checks)")
    else:
        for v in verifications:
            ok = v.get("passed", False)
            icon = f"{G}PASS{RST}" if ok else f"{R}FAIL{RST}"
            print(f"  [{icon}] {v.get('details', '')}")

    # ── [7] Dynamic verification (Sandbox before/after) ───────────────
    print(f"\n  {B}[7] DYNAMIC VERIFICATION (Sandbox){RST}")
    print(f"  {_LINE}")
    if sandbox:
        orig_ok = sandbox.get("original_runs", False)
        patch_ok = sandbox.get("patched_runs", False)
        bm_ok = sandbox.get("behaviour_match", False)
        test_ok = sandbox.get("test_passed", False)
        tc = sandbox.get("test_count", 0)
        tp = sandbox.get("test_pass_count", 0)

        _status = lambda ok: f"{G}PASS{RST}" if ok else f"{R}FAIL{RST}"
        print(f"  Original compiles     : [{_status(orig_ok)}]")
        print(f"  Patched compiles+runs : [{_status(patch_ok)}]")
        print(f"  Behaviour preserved   : [{_status(bm_ok)}]")
        print(f"  Safety tests          : [{_status(test_ok)}] ({tp}/{tc} passed)")

        test_out = sandbox.get("test_output", "")
        if test_out:
            print(f"\n  {B}Test output:{RST}")
            for line in test_out.strip().splitlines():
                color = G if "PASS" in line else (R if "FAIL" in line else "")
                end = RST if color else ""
                print(f"    {color}{line}{end}")
    else:
        print("  (sandbox not run)")

    # ── [8] Confidence score breakdown ────────────────────────────────
    print(f"\n  {B}[8] CONFIDENCE SCORE{RST}")
    print(f"  {_LINE}")
    if breakdown:
        _bar = lambda v: ("*" * int(v * 20)).ljust(20, ".")
        print(f"  Static safety     : [{_bar(breakdown.get('static_safety', 0))}] "
              f"{breakdown.get('static_safety', 0):.0%}  (weight: 30%)")
        print(f"  Behavioural match : [{_bar(breakdown.get('behavioural_match', 0))}] "
              f"{breakdown.get('behavioural_match', 0):.0%}  (weight: 30%)")
        print(f"  Patch complexity  : [{_bar(breakdown.get('patch_complexity', 0))}] "
              f"{breakdown.get('patch_complexity', 0):.0%}  (weight: 20%)")
        print(f"  CPG coverage      : [{_bar(breakdown.get('cpg_coverage', 0))}] "
              f"{breakdown.get('cpg_coverage', 0):.0%}  (weight: 20%)")
        print(f"  {'':>20}  {B}Overall: {score:.0%}{RST}")
    else:
        print(f"  Score: {score:.0%}")

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{_SEP}")
    print(f"  {B}SUMMARY{RST}")
    sandbox_status = f"{G}PASS{RST}" if sandbox.get("test_passed") else f"{R}NOT VERIFIED{RST}"
    print(f"  Vulns found : {len(vulns)}")
    print(f"  Patches     : {len(patches)}")
    print(f"  Diff lines  : {len(diff.splitlines()) if diff else 0}")
    print(f"  Sandbox     : {sandbox_status}")
    print(f"  Confidence  : {B}{score:.0%}{RST}")
    print(f"  LLM model   : {llm_model}")
    print(f"{_SEP}\n")


def _run(source: str, file_path: str) -> None:
    log.info("sentinel_core_start", version="0.1.0")

    # Log LLM availability once at run start
    llm = get_llm()
    active_model = getattr(llm, "model", None) if llm is not None else None
    if active_model:
        log.info(f"Using OpenRouter - Model: {active_model}")
    else:
        log.info("llm_inactive", note="No OPENROUTER_API_KEY — using rule-based agents")

    parser = CodeParser()
    parsed = parser.parse_source(source)
    log.info("parsed", lines=parsed.line_count, has_errors=parsed.has_errors)

    builder = CPGBuilder()
    cpg = builder.build(parsed)
    log.info("cpg_built", nodes=cpg.node_count, edges=cpg.edge_count)

    nx_graph = builder.to_networkx(cpg)

    result = run_pipeline(
        source_code=source,
        file_path=file_path,
        language="python",
        cpg_graph=nx_graph,
    )

    _display(result)
    log.info("sentinel_core_done")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="sentinel",
        description="Sentinel Core - Autonomous Neural Code Architect",
    )
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--demo", action="store_true", help="Run demo.")
    group.add_argument("--file", metavar="PATH", help="Analyse a file.")
    args = ap.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.is_file():
            log.error("file_not_found", path=str(path))
            sys.exit(1)
        _run(path.read_text(encoding="utf-8"), str(path))
    else:
        print("\n  Running demo on built-in vulnerable snippet...\n")
        _run(_DEMO_SOURCE, "<demo>")


if __name__ == "__main__":
    main()
