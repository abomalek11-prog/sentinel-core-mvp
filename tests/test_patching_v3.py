"""
Tests for PatchEngine v3 — LLM-guided patching with PatchPlan.

Covers:
  - PatchDecision / PatchPlan models (validity, properties)
  - LLMPatchPlanner fallback (no LLM configured)
  - LLMPatchPlanner with mocked LLM — valid JSON response
  - LLMPatchPlanner with mocked LLM — malformed JSON (graceful fallback)
  - LLMPatchPlanner with mocked LLM — low-confidence decisions
  - LLMPatchPlanner with mocked LLM — missing vulnerability in response
  - PatchEngine.generate_patch_from_plan() — applies plan correctly
  - PatchEngine.generate_patch_from_plan() — rejects unknown kind
  - PatchEngine.generate_patch_from_plan() — rejects low-confidence decision
  - PatchEngine.generate_patch_from_plan() — fallback plan (rule_based strategy)
  - Full integration: planner + engine with fallback
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sentinel_core.patching import (
    LLMPatchPlanner,
    PatchDecision,
    PatchEngine,
    PatchPlan,
    PatchStrategy,
)
from sentinel_core.patching.llm_planner import _MIN_CONFIDENCE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VULNERABLE_SOURCE = """\
import os
import pickle
import yaml

def handle_request(user_input: str):
    result = eval(user_input)
    os.system("echo " + user_input)
    obj = pickle.loads(user_input.encode())
    cfg = yaml.load(user_input)
    return result
"""

_VULNS = [
    {"kind": "eval",         "location": "line 5", "severity": "HIGH",   "description": "eval()"},
    {"kind": "os.system",    "location": "line 6", "severity": "HIGH",   "description": "os.system()"},
    {"kind": "pickle.loads", "location": "line 7", "severity": "HIGH",   "description": "pickle.loads()"},
    {"kind": "yaml.load",    "location": "line 8", "severity": "MEDIUM", "description": "yaml.load()"},
]


def _make_decision(kind: str, location: str = "line 5",
                   strategy: PatchStrategy = PatchStrategy.SAFE_REPLACE,
                   confidence: float = 0.9) -> PatchDecision:
    return PatchDecision(
        kind=kind, location=location,
        strategy=strategy, safe_api="safe_api()",
        rationale="Test rationale.", test_hint="Test hint.",
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# PatchDecision model tests
# ---------------------------------------------------------------------------

class TestPatchDecision:
    def test_valid_decision(self) -> None:
        d = _make_decision("eval")
        assert d.is_valid()

    def test_invalid_empty_kind(self) -> None:
        d = _make_decision("")
        assert not d.is_valid()

    def test_invalid_confidence_out_of_range(self) -> None:
        d = PatchDecision(kind="eval", location="line 5", confidence=1.5)
        assert not d.is_valid()

    def test_default_strategy_is_rule_based(self) -> None:
        d = PatchDecision(kind="eval", location="line 5")
        assert d.strategy == PatchStrategy.RULE_BASED

    def test_accepted_defaults_false(self) -> None:
        d = _make_decision("eval")
        assert d.accepted is False


# ---------------------------------------------------------------------------
# PatchPlan model tests
# ---------------------------------------------------------------------------

class TestPatchPlan:
    def test_empty_plan(self) -> None:
        plan = PatchPlan()
        assert plan.accepted_count == 0
        assert plan.rejected_count == 0
        assert plan.by_kind("eval") is None

    def test_accepted_count(self) -> None:
        d1 = _make_decision("eval")
        d1.accepted = True
        d2 = _make_decision("os.system")
        plan = PatchPlan(decisions=[d1, d2])
        assert plan.accepted_count == 1
        assert plan.rejected_count == 1  # not accepted and has a kind

    def test_by_kind(self) -> None:
        d = _make_decision("yaml.load", location="line 8")
        plan = PatchPlan(decisions=[d])
        found = plan.by_kind("yaml.load")
        assert found is d
        assert plan.by_kind("eval") is None

    def test_summary_string(self) -> None:
        plan = PatchPlan(decisions=[_make_decision("eval")], llm_model="gpt-4o")
        s = plan.summary()
        assert "gpt-4o" in s
        assert "1 decision" in s


# ---------------------------------------------------------------------------
# LLMPatchPlanner — fallback (no LLM)
# ---------------------------------------------------------------------------

class TestLLMPatchPlannerFallback:
    def test_no_llm_returns_fallback_plan(self) -> None:
        with patch("sentinel_core.patching.llm_planner._get_llm", return_value=None):
            planner = LLMPatchPlanner()
            plan = planner.plan(_VULNS, _VULNERABLE_SOURCE)

        assert plan.used_fallback is True
        assert len(plan.decisions) == len(_VULNS)
        for d in plan.decisions:
            assert d.strategy == PatchStrategy.RULE_BASED

    def test_empty_vulns_returns_empty_plan(self) -> None:
        planner = LLMPatchPlanner()
        plan = planner.plan([], _VULNERABLE_SOURCE)
        assert len(plan.decisions) == 0
        assert plan.used_fallback is False


# ---------------------------------------------------------------------------
# LLMPatchPlanner — with mocked LLM
# ---------------------------------------------------------------------------

def _mock_llm_response(json_str: str) -> MagicMock:
    """Build a mock LLM that returns *json_str* as its response content."""
    response = MagicMock()
    response.content = json_str
    llm = MagicMock()
    llm.invoke.return_value = response
    llm.model_name = "gpt-4o"
    return llm


_VALID_PLAN_JSON = """\
{
  "planning_notes": "Apply safe replacements for all four vulnerabilities.",
  "decisions": [
    {"kind": "eval",         "location": "line 5", "strategy": "wrap_try_except",
     "safe_api": "ast.literal_eval", "rationale": "Prevents arbitrary execution.",
     "test_hint": "assert 'eval' not in patched", "confidence": 0.95},
    {"kind": "os.system",    "location": "line 6", "strategy": "safe_replace",
     "safe_api": "subprocess.run",  "rationale": "Prevents command injection.",
     "test_hint": "assert 'subprocess.run' in patched", "confidence": 0.90},
    {"kind": "pickle.loads", "location": "line 7", "strategy": "safe_replace",
     "safe_api": "json.loads", "rationale": "Avoids arbitrary deserialization.",
     "test_hint": "assert 'json.loads' in patched", "confidence": 0.88},
    {"kind": "yaml.load",    "location": "line 8", "strategy": "safe_replace",
     "safe_api": "yaml.safe_load", "rationale": "Uses safe loader.",
     "test_hint": "assert 'yaml.safe_load' in patched", "confidence": 0.92}
  ]
}
"""


class TestLLMPatchPlannerWithMockedLLM:
    def test_valid_response_produces_plan(self) -> None:
        llm = _mock_llm_response(_VALID_PLAN_JSON)
        with patch("sentinel_core.patching.llm_planner._get_llm", return_value=llm):
            plan = LLMPatchPlanner().plan(_VULNS, _VULNERABLE_SOURCE)

        assert plan.used_fallback is False
        assert len(plan.decisions) == 4
        assert plan.planning_notes.startswith("Apply safe")
        kinds = {d.kind for d in plan.decisions}
        assert kinds == {"eval", "os.system", "pickle.loads", "yaml.load"}

    def test_correct_strategies_parsed(self) -> None:
        llm = _mock_llm_response(_VALID_PLAN_JSON)
        with patch("sentinel_core.patching.llm_planner._get_llm", return_value=llm):
            plan = LLMPatchPlanner().plan(_VULNS, _VULNERABLE_SOURCE)

        eval_d = plan.by_kind("eval")
        assert eval_d is not None
        assert eval_d.strategy == PatchStrategy.WRAP_TRY_EXCEPT
        assert eval_d.confidence == pytest.approx(0.95)

    def test_malformed_json_falls_back(self) -> None:
        llm = _mock_llm_response("this is NOT json {{{")
        with patch("sentinel_core.patching.llm_planner._get_llm", return_value=llm):
            plan = LLMPatchPlanner().plan(_VULNS, _VULNERABLE_SOURCE)

        assert plan.used_fallback is True
        for d in plan.decisions:
            assert d.strategy == PatchStrategy.RULE_BASED

    def test_low_confidence_decision_is_rejected(self) -> None:
        low_conf_json = """\
{
  "planning_notes": "Low confidence test.",
  "decisions": [
    {"kind": "eval", "location": "line 5", "strategy": "safe_replace",
     "safe_api": "ast.literal_eval", "rationale": "Unsure.", "test_hint": "",
     "confidence": 0.10}
  ]
}
"""
        llm = _mock_llm_response(low_conf_json)
        with patch("sentinel_core.patching.llm_planner._get_llm", return_value=llm):
            plan = LLMPatchPlanner().plan(_VULNS[:1], _VULNERABLE_SOURCE)

        assert len(plan.decisions) >= 1
        eval_d = plan.by_kind("eval")
        assert eval_d is not None
        # Planner marks it as not accepted due to low confidence
        assert eval_d.accepted is False
        assert "confidence" in eval_d.rejection_reason

    def test_missing_vuln_in_response_is_filled(self) -> None:
        partial_json = """\
{
  "planning_notes": "Only patched eval.",
  "decisions": [
    {"kind": "eval", "location": "line 5", "strategy": "safe_replace",
     "safe_api": "ast.literal_eval", "rationale": "OK.", "test_hint": "",
     "confidence": 0.9}
  ]
}
"""
        llm = _mock_llm_response(partial_json)
        with patch("sentinel_core.patching.llm_planner._get_llm", return_value=llm):
            plan = LLMPatchPlanner().plan(_VULNS, _VULNERABLE_SOURCE)

        # Missing three vulns should be filled in with RULE_BASED
        assert len(plan.decisions) == 4
        rule_based = [d for d in plan.decisions if d.strategy == PatchStrategy.RULE_BASED]
        assert len(rule_based) == 3

    def test_unknown_strategy_defaults_to_rule_based(self) -> None:
        bad_strategy_json = """\
{
  "planning_notes": "Bad strategy.",
  "decisions": [
    {"kind": "eval", "location": "line 5", "strategy": "magic_wand",
     "safe_api": "ast.literal_eval", "rationale": "OK.", "test_hint": "",
     "confidence": 0.9}
  ]
}
"""
        llm = _mock_llm_response(bad_strategy_json)
        with patch("sentinel_core.patching.llm_planner._get_llm", return_value=llm):
            plan = LLMPatchPlanner().plan(_VULNS[:1], _VULNERABLE_SOURCE)

        eval_d = plan.by_kind("eval")
        assert eval_d is not None
        assert eval_d.strategy == PatchStrategy.RULE_BASED

    def test_llm_exception_falls_back(self) -> None:
        llm = MagicMock()
        llm.invoke.side_effect = ConnectionError("timeout")
        llm.model_name = "gpt-4o"
        with patch("sentinel_core.patching.llm_planner._get_llm", return_value=llm):
            plan = LLMPatchPlanner().plan(_VULNS, _VULNERABLE_SOURCE)

        assert plan.used_fallback is True


# ---------------------------------------------------------------------------
# PatchEngine.generate_patch_from_plan()
# ---------------------------------------------------------------------------

class TestPatchEngineWithPlan:
    _SOURCE = """\
import os

def run(cmd: str):
    eval(cmd)
    os.system(cmd)
"""

    def _make_plan(self, decisions: list[PatchDecision]) -> PatchPlan:
        return PatchPlan(decisions=decisions, llm_model="test-model")

    def test_applies_eval_fix_from_plan(self) -> None:
        plan = self._make_plan([
            PatchDecision(kind="eval", location="line 3",
                          strategy=PatchStrategy.WRAP_TRY_EXCEPT, confidence=0.9),
        ])
        result = PatchEngine().generate_patch_from_plan(self._SOURCE, plan)
        assert "ast.literal_eval" in result.patched_source
        assert result.has_changes

    def test_rejects_unknown_kind(self) -> None:
        plan = self._make_plan([
            PatchDecision(kind="unknown_sink", location="line 1",
                          strategy=PatchStrategy.SAFE_REPLACE, confidence=0.9),
        ])
        result = PatchEngine().generate_patch_from_plan(self._SOURCE, plan)
        # No changes — unknown kind rejected
        assert not result.has_changes
        decision = plan.decisions[0]
        assert decision.accepted is False
        assert "no patch rule" in decision.rejection_reason

    def test_rewrites_subprocess_call_shell_true_safely(self) -> None:
        source = """\
import subprocess

def run_cmd(user_input: str):
    rc = subprocess.call("echo " + user_input, shell=True)
    return rc
"""
        plan = self._make_plan([
            PatchDecision(
                kind="subprocess.call",
                location="line 3",
                strategy=PatchStrategy.WRAP_TRY_EXCEPT,
                confidence=0.95,
            ),
        ])

        result = PatchEngine().generate_patch_from_plan(source, plan)

        assert result.has_changes
        assert "subprocess.call" not in result.patched_source
        assert "subprocess.run(" in result.patched_source
        assert "shell=False" in result.patched_source
        assert "shlex.quote" in result.patched_source
        assert "try:" in result.patched_source
        assert "except (subprocess.SubprocessError, ValueError, TypeError)" in result.patched_source
        assert result.diff.startswith("---")

    def test_rewrites_subprocess_check_output_shell_true_safely(self) -> None:
        source = """\
import subprocess

def process_image(image_name: str):
    result = subprocess.check_output(f"img-tool --input {image_name} --out /tmp/processed.png", shell=True)
    return result
"""
        plan = self._make_plan([
            PatchDecision(
                kind="subprocess.check_output",
                location="line 3",
                strategy=PatchStrategy.WRAP_TRY_EXCEPT,
                confidence=0.95,
            ),
        ])

        result = PatchEngine().generate_patch_from_plan(source, plan)

        assert result.has_changes
        assert "subprocess.check_output(" in result.patched_source
        assert "shell=True" not in result.patched_source
        assert "safe_image_name = shlex.quote(str(image_name))" in result.patched_source
        assert '"img-tool"' in result.patched_source
        assert '"--input", safe_image_name' in result.patched_source
        assert '"--out", "/tmp/processed.png"' in result.patched_source
        assert "stderr=subprocess.STDOUT" in result.patched_source
        assert "except (subprocess.SubprocessError, ValueError, TypeError)" in result.patched_source
        assert result.diff.startswith("---")

    def test_rewrites_subprocess_check_output_variable_ref_pattern(self) -> None:
        """Two-line pattern: command in variable → fixer resolves variable and
        uses img-tool special case, removing the variable assignment line."""
        source = """\
import subprocess

def process_image(image_name: str):
    command = f"img-tool --input {image_name} --out /tmp/processed.png"
    result = subprocess.check_output(command, shell=True)
    return result
"""
        plan = self._make_plan([
            PatchDecision(
                kind="subprocess.check_output",
                location="line 4",
                strategy=PatchStrategy.WRAP_TRY_EXCEPT,
                confidence=0.95,
            ),
        ])

        result = PatchEngine().generate_patch_from_plan(source, plan)

        assert result.has_changes
        assert "shell=True" not in result.patched_source
        assert "subprocess.check_output(" in result.patched_source
        assert "stderr=subprocess.STDOUT" in result.patched_source
        # Variable tracing should trigger the img-tool special case
        assert "safe_image_name = shlex.quote(str(image_name))" in result.patched_source
        assert '"img-tool"' in result.patched_source
        assert '"--input", safe_image_name' in result.patched_source
        # The old command= assignment line should be removed
        assert 'command = f"img-tool' not in result.patched_source
        assert "except (subprocess.SubprocessError, ValueError, TypeError)" in result.patched_source
        assert result.diff.startswith("---")

    def test_rewrites_subprocess_check_output_with_extra_kwargs(self) -> None:
        """Pattern where check_output already has stderr=subprocess.STDOUT plus shell=True."""
        source = """\
import subprocess

def process_image(safe_image_name: str):
    command = f"img-tool --input {safe_image_name} --out /tmp/processed.png"
    result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
    return result
"""
        plan = self._make_plan([
            PatchDecision(
                kind="subprocess.check_output",
                location="line 4",
                strategy=PatchStrategy.WRAP_TRY_EXCEPT,
                confidence=0.95,
            ),
        ])

        result = PatchEngine().generate_patch_from_plan(source, plan)

        assert result.has_changes
        assert "shell=True" not in result.patched_source
        assert "subprocess.check_output(" in result.patched_source
        assert "stderr=subprocess.STDOUT" in result.patched_source
        # Variable tracing resolves the img-tool pattern
        assert "safe_image_name = shlex.quote(str(image_name))" in result.patched_source or \
               '"img-tool"' in result.patched_source
        assert result.diff.startswith("---")

    def test_rewrites_subprocess_check_output_multiline_call(self) -> None:
        """Multi-line subprocess.check_output call with parens on separate lines."""
        source = """\
import subprocess

def process_image(image_name: str):
    result = subprocess.check_output(
        f"img-tool --input {image_name} --out /tmp/processed.png",
        shell=True
    )
    return result
"""
        plan = self._make_plan([
            PatchDecision(
                kind="subprocess.check_output",
                location="line 3",
                strategy=PatchStrategy.WRAP_TRY_EXCEPT,
                confidence=0.95,
            ),
        ])

        result = PatchEngine().generate_patch_from_plan(source, plan)

        assert result.has_changes
        assert "shell=True" not in result.patched_source
        assert "subprocess.check_output(" in result.patched_source
        assert "stderr=subprocess.STDOUT" in result.patched_source
        assert "except (subprocess.SubprocessError, ValueError, TypeError)" in result.patched_source
        assert result.diff.startswith("---")

    def test_rejects_low_confidence_at_engine_level(self) -> None:
        low = _MIN_CONFIDENCE - 0.01
        plan = self._make_plan([
            PatchDecision(kind="eval", location="line 3",
                          strategy=PatchStrategy.SAFE_REPLACE, confidence=low),
        ])
        result = PatchEngine().generate_patch_from_plan(self._SOURCE, plan)
        assert not result.has_changes
        assert plan.decisions[0].accepted is False

    def test_fallback_rule_based_plan_applies_all(self) -> None:
        """A RULE_BASED strategy plan is fully applied by the engine."""
        plan = self._make_plan([
            PatchDecision(kind="eval",      location="line 3",
                          strategy=PatchStrategy.RULE_BASED, confidence=1.0),
            PatchDecision(kind="os.system", location="line 4",
                          strategy=PatchStrategy.RULE_BASED, confidence=1.0),
        ])
        result = PatchEngine().generate_patch_from_plan(self._SOURCE, plan)
        assert result.has_changes
        assert "ast.literal_eval" in result.patched_source
        assert "subprocess.run" in result.patched_source

    def test_context_info_has_llm_fields(self) -> None:
        plan = self._make_plan([
            PatchDecision(kind="eval", location="line 3",
                          strategy=PatchStrategy.SAFE_REPLACE,
                          rationale="This is the rationale.",
                          test_hint="Check for ast.",
                          confidence=0.9),
        ])
        result = PatchEngine().generate_patch_from_plan(self._SOURCE, plan)
        assert len(result.context_info) >= 1
        ctx = result.context_info[0]
        assert ctx.get("llm_rationale") == "This is the rationale."
        assert ctx.get("llm_test_hint") == "Check for ast."

    def test_diff_is_generated(self) -> None:
        plan = self._make_plan([
            PatchDecision(kind="eval", location="line 3",
                          strategy=PatchStrategy.RULE_BASED, confidence=1.0),
        ])
        result = PatchEngine().generate_patch_from_plan(self._SOURCE, plan)
        assert result.diff.startswith("---")
        assert "ast.literal_eval" in result.diff


# ---------------------------------------------------------------------------
# Integration: planner + engine together (no real LLM)
# ---------------------------------------------------------------------------

class TestPlannerEngineIntegration:
    def test_fallback_pipeline_patches_all_vulns(self) -> None:
        """End-to-end: no LLM → fallback plan → engine patches all 4 vulns."""
        with patch("sentinel_core.patching.llm_planner._get_llm", return_value=None):
            plan = LLMPatchPlanner().plan(_VULNS, _VULNERABLE_SOURCE)

        result = PatchEngine().generate_patch_from_plan(_VULNERABLE_SOURCE, plan)

        assert result.has_changes
        assert "ast.literal_eval" in result.patched_source
        assert "subprocess.run" in result.patched_source
        assert "json.loads" in result.patched_source
        assert "yaml.safe_load" in result.patched_source
        # Original dangerous APIs should be gone
        assert "eval(" not in result.patched_source or "literal_eval" in result.patched_source
        assert "yaml.load(" not in result.patched_source

    def test_llm_plan_pipeline_patches_all_vulns(self) -> None:
        """End-to-end: valid LLM response → plan → engine patches all 4 vulns."""
        llm = _mock_llm_response(_VALID_PLAN_JSON)
        with patch("sentinel_core.patching.llm_planner._get_llm", return_value=llm):
            plan = LLMPatchPlanner().plan(_VULNS, _VULNERABLE_SOURCE)

        result = PatchEngine().generate_patch_from_plan(_VULNERABLE_SOURCE, plan)

        assert result.has_changes
        assert "ast.literal_eval" in result.patched_source
        assert "subprocess.run" in result.patched_source
        assert "json.loads" in result.patched_source
        assert "yaml.safe_load" in result.patched_source
        assert plan.llm_model == "gpt-4o"
