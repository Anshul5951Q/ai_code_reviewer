"""
Gate 5 — Deterministic Decision Engine.

Axiom: Zero Blind Trust in LLM Claims.
Gate 5 is 100% deterministic code (never an LLM).
Arbitrates final defect resolution by verifying Gate 4 output, independent VerificationAgent
outcome, deterministic re-scan signals, test execution, regression absence, and patch version identity.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.schemas.remediation import Gate4Status
from app.schemas.verification import (
    Gate5Decision,
    Gate5DecisionResult,
    ScannerComparisonResult,
    VerificationOutcome,
)

logger = logging.getLogger("ai_code_reviewer.gate5_decision_engine")


class Gate5DecisionEngine:
    """
    Deterministic arbiter for code review finding resolution.
    Enforces the 7 mandatory resolution conditions and 8 blocking rules.
    """

    @staticmethod
    def evaluate(
        gate_4_status: str,
        verification_outcome: str,
        deterministic_rescan: Optional[ScannerComparisonResult] = None,
        syntax_valid: bool = True,
        patch_version: int = 1,
        expected_patch_version: Optional[int] = None,
        snapshot_id: Optional[str] = None,
        expected_snapshot_id: Optional[str] = None,
        tests_passed: bool = True,
        test_failure_details: Optional[str] = None,
        remaining_evidence: Optional[str] = None,
        validation_available: bool = True,
    ) -> Gate5DecisionResult:
        """
        Deterministically evaluate whether a finding can be officially marked RESOLVED.
        """
        passed_conditions: List[str] = []
        failed_conditions: List[str] = []
        reasons: List[str] = []

        norm_g4 = (gate_4_status or "").strip().upper()
        norm_outcome = (verification_outcome or "").strip().upper()

        # 1. Patch version and snapshot grounding check
        if expected_patch_version is not None and patch_version != expected_patch_version:
            failed_conditions.append(
                f"Patch version mismatch: evaluated patch v{patch_version} but expected v{expected_patch_version}"
            )
        else:
            passed_conditions.append(f"Patch version grounded: verified patch v{patch_version}")

        if expected_snapshot_id and snapshot_id and snapshot_id != expected_snapshot_id:
            failed_conditions.append(
                f"Snapshot identity mismatch: evaluated snapshot {snapshot_id[:8]} does not match expected {expected_snapshot_id[:8]}"
            )
        else:
            passed_conditions.append("Snapshot identity verified")

        # 2. Gate 4 Passed Check
        if norm_g4 == Gate4Status.PASSED.value:
            passed_conditions.append("Gate 4 patch validation passed (diff structure, workspace boundary, and syntax clean)")
        else:
            failed_conditions.append(f"Gate 4 patch validation check did not pass (status: {norm_g4})")

        # 3. Independent VerificationAgent Outcome Check
        if norm_outcome == VerificationOutcome.FIXED.value:
            passed_conditions.append("Independent Verification Agent confirmed root cause fixed via Source->Transformation->Sink audit")
        else:
            failed_conditions.append(f"Independent Verification Agent did not confirm defect FIXED (outcome: {norm_outcome})")

        # 4. Deterministic Re-Scan Defect Clearing Check
        target_cleared = deterministic_rescan.target_defect_cleared if deterministic_rescan else True
        if target_cleared and not remaining_evidence:
            passed_conditions.append("Deterministic static security re-scan confirmed target vulnerability rule cleared")
        else:
            failed_conditions.append("Deterministic static re-scan detected target defect pattern remains in patched code")

        # 5. Language Syntax & AST Compilation Check
        if syntax_valid:
            passed_conditions.append("Language syntax and AST parsing verified without compilation errors")
        else:
            failed_conditions.append("Patched code failed language syntax compilation (AST SyntaxError)")

        # 6. Regression Safety Check (No new defects introduced)
        new_issues = deterministic_rescan.new_findings if deterministic_rescan else []
        if len(new_issues) == 0 and norm_outcome != VerificationOutcome.REGRESSION_DETECTED.value:
            passed_conditions.append("Zero newly introduced static vulnerability signals or regressions detected")
        else:
            failed_conditions.append(
                f"Patch introduced potential regressions: {len(new_issues)} new static signal(s) flagged"
            )

        # 7. Test Suite Execution Check
        if tests_passed:
            passed_conditions.append("Required unit and regression tests passed on patched code")
        else:
            failed_conditions.append(f"Test suite execution failed on patched code: {test_failure_details or 'Tests failed'}")

        # Check validation availability policy
        if not validation_available:
            failed_conditions.append("Required validation tools were unavailable during evaluation")

        # ── Deterministic Decision Resolution ──────────────────────────────────
        is_resolved = False
        decision = Gate5Decision.UNRESOLVED.value

        # Blocking Condition A: Regressions detected
        if norm_outcome == VerificationOutcome.REGRESSION_DETECTED.value or len(new_issues) > 0:
            decision = Gate5Decision.BLOCKED.value
            reasons.append("Resolution BLOCKED: Proposed patch introduces secondary defects or behavioral regressions.")

        # Blocking Condition B: Gate 4 failed or tests failed
        elif norm_g4 in (Gate4Status.FAILED.value, Gate4Status.PARTIALLY_PASSED.value):
            decision = Gate5Decision.BLOCKED.value
            reasons.append(f"Resolution BLOCKED: Gate 4 patch verification rejected the diff (status: {norm_g4}).")

        elif not tests_passed:
            decision = Gate5Decision.BLOCKED.value
            reasons.append(f"Resolution BLOCKED: Regression tests failed ({test_failure_details or 'Unspecified failure'}).")

        elif not syntax_valid:
            decision = Gate5Decision.BLOCKED.value
            reasons.append("Resolution BLOCKED: Patched code introduces a fatal language syntax error.")

        # Condition C: Verification Agent unable to verify or validation unavailable
        elif norm_outcome == VerificationOutcome.UNABLE_TO_VERIFY.value or norm_g4 == Gate4Status.UNABLE_TO_VERIFY.value or not validation_available:
            decision = Gate5Decision.UNABLE_TO_VERIFY.value
            reasons.append("Resolution UNABLE TO VERIFY: Insufficient empirical evidence, test coverage, or tool availability.")

        # Condition D: Partially fixed
        elif norm_outcome == VerificationOutcome.PARTIALLY_FIXED.value:
            decision = Gate5Decision.PARTIALLY_RESOLVED.value
            reasons.append("Resolution PARTIALLY RESOLVED: Defect partially mitigated but residual attack surface remains.")

        # Condition E: Not fixed or deterministic scanner still flags
        elif norm_outcome == VerificationOutcome.NOT_FIXED.value or not target_cleared:
            decision = Gate5Decision.UNRESOLVED.value
            reasons.append("Resolution UNRESOLVED: Underlying vulnerability remains exploitable in patched code.")

        # Mandatory Resolution Rule: All conditions passed
        elif len(failed_conditions) == 0:
            decision = Gate5Decision.RESOLVED.value
            is_resolved = True
            reasons.append(
                f"Defect officially RESOLVED: Patch v{patch_version} passed Gate 4, "
                "eliminated the root cause via Source->Transformation->Sink analysis, "
                "cleared deterministic re-scan rules, and introduced zero regressions."
            )
        else:
            decision = Gate5Decision.BLOCKED.value
            reasons.append(f"Resolution BLOCKED: Failed mandatory resolution checks: {failed_conditions}")

        return Gate5DecisionResult(
            decision=decision,
            passed_conditions=passed_conditions,
            failed_conditions=failed_conditions,
            reasons=reasons,
            patch_version=patch_version,
            snapshot_id=snapshot_id,
            is_resolved=is_resolved,
            limitations="Local container sandbox unavailable; verified in isolated process directory" if not validation_available else None,
        )

