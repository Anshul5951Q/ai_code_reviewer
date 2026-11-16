"""
Deterministic Re-Scanning Engine.
Re-evaluates security rules and AST quality analyzers against patched snapshots.
Empirically compares pre-patch and post-patch detection signals to verify defect eradication
and detect regression introduction.
"""
from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.analysis.static_analysis import StaticSecurityAnalyzer, run_static_analysis
from app.schemas.verification import ScannerComparisonResult


class DeterministicReScanner:
    """
    Executes rule-based static analysis against original vs patched code snapshots.
    Produces empirical signal deltas without relying on LLM judgment.
    """

    def __init__(self) -> None:
        self.security_analyzer = StaticSecurityAnalyzer()

    def rescan_file(
        self,
        file_path: str,
        original_content: str,
        patched_content: str,
        target_cwe: Optional[str] = None,
        target_type: Optional[str] = None,
        target_evidence: Optional[str] = None,
    ) -> ScannerComparisonResult:
        """
        Compare static security and quality signals before and after patch application.
        """
        # 1. Scan original content
        orig_findings = self.security_analyzer.analyze_file(file_path, original_content)
        orig_dicts = [f.to_dict() for f in orig_findings]

        # 2. Scan patched content
        post_findings = self.security_analyzer.analyze_file(file_path, patched_content)
        post_dicts = [f.to_dict() for f in post_findings]

        # 3. Identify target defect presence in patched code
        target_still_present = False
        norm_target_cwe = (target_cwe or "").strip().upper()
        norm_target_type = (target_type or "").strip().lower()

        for pf in post_dicts:
            cwe_match = norm_target_cwe and pf.get("cwe") == norm_target_cwe
            type_match = norm_target_type and pf.get("type", "").lower() == norm_target_type
            if cwe_match or type_match:
                target_still_present = True
                break

        # Additional regex/evidence check if provided
        if not target_still_present and target_evidence:
            clean_ev = target_evidence.strip()
            # If the exact dangerous snippet is still in patched content unmodified
            if len(clean_ev) > 10 and clean_ev in patched_content:
                # Target evidence remains in modified source
                target_still_present = True

        # 4. Partition findings: cleared, retained, newly introduced
        orig_signatures = {
            (f.get("cwe"), f.get("type"), f.get("start_line")): f
            for f in orig_dicts
        }
        post_signatures = {
            (f.get("cwe"), f.get("type"), f.get("start_line")): f
            for f in post_dicts
        }

        cleared_findings: List[Dict[str, Any]] = []
        retained_findings: List[Dict[str, Any]] = []
        new_findings: List[Dict[str, Any]] = []

        # Items in original that disappeared in patched
        for sig, item in orig_signatures.items():
            # Check by CWE and type
            still_there = any(
                p.get("cwe") == item.get("cwe") and p.get("type") == item.get("type")
                for p in post_dicts
            )
            if not still_there:
                cleared_findings.append(item)
            else:
                retained_findings.append(item)

        # Items in post that were not in original (regressions)
        orig_types = {(f.get("cwe"), f.get("type")) for f in orig_dicts}
        for item in post_dicts:
            if (item.get("cwe"), item.get("type")) not in orig_types:
                new_findings.append(item)

        # 5. AST syntax inspection for Python files
        if file_path.endswith(".py"):
            try:
                ast.parse(patched_content, filename=file_path)
            except SyntaxError as syn_err:
                new_findings.append({
                    "category": "quality",
                    "type": "syntax_error",
                    "severity": "critical",
                    "title": "Syntax Error Introduced by Patch",
                    "description": f"Python SyntaxError at line {syn_err.lineno}: {syn_err.msg}",
                    "file_path": file_path,
                    "start_line": syn_err.lineno or 1,
                    "end_line": syn_err.lineno or 1,
                    "evidence": str(syn_err),
                    "cwe": "CWE-1104",
                    "source": "ast_parser",
                })

        return ScannerComparisonResult(
            pre_patch_findings_count=len(orig_dicts),
            post_patch_findings_count=len(post_dicts),
            target_defect_cleared=not target_still_present,
            cleared_findings=cleared_findings,
            retained_findings=retained_findings,
            new_findings=new_findings,
        )

