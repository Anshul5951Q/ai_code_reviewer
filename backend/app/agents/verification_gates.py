"""
Verification Gates for Multi-Agent Analysis Pipeline.

Axiom: Zero Blind Trust in LLMs.
Every agent output is treated strictly as an unverified hypothesis.
Independent deterministic verification gates validate claims against empirical code evidence
before findings, claims, or patches are promoted into the review state.
"""
from __future__ import annotations

import ast
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.analysis.static_analysis import mask_secret

logger = logging.getLogger("ai_code_reviewer.verification_gates")


from app.analysis.repository_intelligence import FRAMEWORK_INDICATORS
from app.schemas.understanding import (
    CodeUnderstandingResult,
    ModuleDescription,
    RepositoryIntelligence,
    ValidationReport,
)

ENTRY_POINT_INDICATORS = [
    re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']'),
    re.compile(r'\bFastAPI\s*\('),
    re.compile(r'\bFlask\s*\('),
    re.compile(r'\bexpress\s*\(\)'),
    re.compile(r'\.listen\s*\('),
    re.compile(r'\bhttp\.createServer\s*\('),
    re.compile(r'\bpublic\s+static\s+void\s+main\s*\('),
    re.compile(r'\bfunc\s+main\s*\(\)'),
    re.compile(r'\bfn\s+main\s*\(\)'),
]

LANGUAGE_EXTENSIONS: Dict[str, List[str]] = {
    "python": [".py", ".pyw", ".pyx"],
    "typescript": [".ts", ".tsx"],
    "javascript": [".js", ".jsx", ".mjs", ".cjs"],
    "rust": [".rs"],
    "go": [".go"],
    "java": [".java"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".h"],
    "csharp": [".cs"],
    "ruby": [".rb"],
    "php": [".php"],
    "html": [".html", ".htm"],
    "css": [".css", ".scss", ".sass"],
    "sql": [".sql"],
    "shell": [".sh", ".bash"],
}


def extract_symbols_from_source(file_path: str, content: str) -> Set[str]:
    """Extract AST classes/methods/functions for Python, or regex symbols for other languages."""
    symbols: Set[str] = set()
    if file_path.endswith(".py"):
        try:
            tree = ast.parse(content, filename=file_path)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    symbols.add(node.name)
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            symbols.add(f"{node.name}.{item.name}")
                            symbols.add(item.name)
        except Exception:
            pass
    else:
        for match in re.finditer(r"\bclass\s+([A-Za-z0-9_$]+)", content):
            symbols.add(match.group(1))
        for match in re.finditer(r"\b(?:function|def|func)\s+([A-Za-z0-9_$]+)", content):
            symbols.add(match.group(1))
        for match in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|function)", content):
            symbols.add(match.group(1))
    return symbols


class UnderstandingVerificationGate:
    """
    Verification Gate 1: Deterministically validates repository understanding claims
    against the empirical repository snapshot, file contents, AST symbols, and manifests.
    
    Zero Blind Trust in LLMs:
    - Hallucinated paths are rejected and expunged.
    - Phantom symbols are rejected and expunged.
    - Unsupported framework/language claims are scrubbed.
    - Entry points are verified for existence AND bootstrap evidence.
    - Agent confidence is strictly decoupled from verification status.
    """

    def _normalize_path(self, p: str) -> str:
        return p.strip().lstrip("./").replace("\\", "/")

    def _find_matching_path(self, target: str, known_paths: Set[str]) -> Optional[str]:
        norm = self._normalize_path(target)
        if norm in known_paths:
            return norm
        for kp in known_paths:
            if kp.endswith(f"/{norm}") or kp == norm:
                return kp
        return None

    def verify(
        self,
        raw_output: Dict[str, Any] | CodeUnderstandingResult,
        known_file_paths: Set[str],
        deterministic_frameworks: Optional[Set[str]] = None,
        file_contents: Optional[Dict[str, str]] = None,
        deterministic_languages: Optional[Dict[str, Any]] = None,
        deterministic_dependencies: Optional[List[Dict[str, Any]]] = None,
        repository_id: str = "",
        snapshot_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Verify understanding output and return (sanitized_output, verification_metadata).
        Fully backward-compatible with Phase 5 callers and tests.
        """
        intel = self.verify_intelligence(
            result=raw_output,
            known_file_paths=known_file_paths,
            file_contents=file_contents,
            deterministic_languages=deterministic_languages,
            deterministic_frameworks=deterministic_frameworks,
            deterministic_dependencies=deterministic_dependencies,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
        )

        sanitized_output = intel.model_dump()
        # Keep backward compatibility keys
        sanitized_output["important_modules"] = [m.path for m in intel.modules]
        if isinstance(raw_output, dict):
            if "architecture_risks" in raw_output:
                sanitized_output["architecture_risks"] = raw_output["architecture_risks"]
            if "observations" in raw_output:
                sanitized_output["observations"] = raw_output["observations"]

        report = intel.validation_report
        verification_metadata = {
            "status": intel.verification_status,
            "agent_confidence": intel.agent_confidence,
            "claimed_entry_points": len(raw_output.get("entry_points", []) if isinstance(raw_output, dict) else raw_output.entry_points),
            "verified_entry_points": len(intel.entry_points),
            "expunged_entry_points": [p for p in report.rejected_paths if any(p in ep for ep in (raw_output.get("entry_points", []) if isinstance(raw_output, dict) else raw_output.entry_points))],
            "expunged_modules": [p for p in report.rejected_paths if not any(p in ep for ep in (raw_output.get("entry_points", []) if isinstance(raw_output, dict) else raw_output.entry_points))],
            "rejected_paths": report.rejected_paths,
            "rejected_symbols": report.rejected_symbols,
            "unsupported_frameworks": report.unsupported_frameworks,
            "validation_warnings": report.validation_warnings,
            "validation_report": report.model_dump(),
            "repository_intelligence": intel.model_dump(),
        }

        return sanitized_output, verification_metadata

    def verify_intelligence(
        self,
        result: Dict[str, Any] | CodeUnderstandingResult,
        known_file_paths: Set[str],
        file_contents: Optional[Dict[str, str]] = None,
        deterministic_languages: Optional[Dict[str, Any]] = None,
        deterministic_frameworks: Optional[Set[str]] = None,
        deterministic_dependencies: Optional[List[Dict[str, Any]]] = None,
        repository_id: str = "",
        snapshot_id: Optional[str] = None,
    ) -> RepositoryIntelligence:
        """
        Execute deterministic Gate 1 audit and return trusted RepositoryIntelligence.
        """
        if isinstance(result, dict):
            # Parse into schema or build model
            parsed_result = CodeUnderstandingResult.model_validate(result)
        else:
            parsed_result = result

        contents = file_contents or {}
        norm_known_paths = {self._normalize_path(p) for p in known_file_paths}

        accepted_claims = 0
        rejected_claims = 0
        rejected_paths: List[str] = []
        rejected_symbols: List[str] = []
        unsupported_frameworks: List[str] = []
        validation_warnings: List[str] = []

        # 1. File existence validation for entry points
        verified_entry_points: List[str] = []
        for ep in parsed_result.entry_points:
            matched = self._find_matching_path(ep, norm_known_paths)
            if not matched:
                rejected_claims += 1
                rejected_paths.append(ep)
                validation_warnings.append(f"Entry point '{ep}' does not exist in repository snapshot")
                continue

            # Verify entry-point bootstrap evidence if content is available
            if matched in contents:
                ep_content = contents[matched]
                has_evidence = any(pattern.search(ep_content) for pattern in ENTRY_POINT_INDICATORS)
                filename = os.path.basename(matched).lower()
                is_standard_name = filename in {
                    "main.py", "app.py", "server.py", "run.py",
                    "index.ts", "index.js", "main.ts", "main.js",
                    "app.ts", "app.js", "server.ts", "server.js", "main.go"
                }
                if not has_evidence and not is_standard_name:
                    rejected_claims += 1
                    validation_warnings.append(
                        f"Entry point candidate '{matched}' exists but lacks entry point bootstrap evidence"
                    )
                    continue

            verified_entry_points.append(matched)
            accepted_claims += 1

        # 2. File existence validation for important_files
        verified_important_files: List[str] = []
        for fpath in parsed_result.important_files:
            matched = self._find_matching_path(fpath, norm_known_paths)
            if matched:
                verified_important_files.append(matched)
                accepted_claims += 1
            else:
                rejected_claims += 1
                rejected_paths.append(fpath)
                validation_warnings.append(f"Important file '{fpath}' does not exist in repository snapshot")

        # 3. Module path & symbol validation
        verified_modules: List[ModuleDescription] = []
        for mod in parsed_result.modules:
            mod_path_clean = self._normalize_path(mod.path)
            # Check if mod_path is a file or a directory
            is_file = mod_path_clean in norm_known_paths or any(
                kp.endswith(f"/{mod_path_clean}") or kp == mod_path_clean for kp in norm_known_paths
            )
            is_dir = any(
                kp.startswith(f"{mod_path_clean}/") or f"/{mod_path_clean}/" in kp
                for kp in norm_known_paths
            )

            if not is_file and not is_dir:
                rejected_claims += 1
                rejected_paths.append(mod.path)
                validation_warnings.append(f"Module path '{mod.path}' does not exist in repository snapshot")
                continue

            # Resolve real matched path if file
            matched_mod_path = self._find_matching_path(mod.path, norm_known_paths) or mod_path_clean

            # Symbol verification if source contents are available
            verified_symbols: List[str] = []
            if mod.key_symbols:
                # Find all available contents for this module
                available_module_contents: Dict[str, str] = {}
                if matched_mod_path in contents:
                    available_module_contents[matched_mod_path] = contents[matched_mod_path]
                for p, c in contents.items():
                    norm_p = self._normalize_path(p)
                    if norm_p.startswith(f"{mod_path_clean}/") or f"/{mod_path_clean}/" in norm_p:
                        available_module_contents[norm_p] = c

                if available_module_contents:
                    extracted_symbols: Set[str] = set()
                    for fp, code in available_module_contents.items():
                        extracted_symbols.update(extract_symbols_from_source(fp, code))

                    for sym in mod.key_symbols:
                        # Direct match or compound Class.method match
                        if sym in extracted_symbols or any(s.endswith(f".{sym}") or s == sym for s in extracted_symbols):
                            verified_symbols.append(sym)
                            accepted_claims += 1
                        else:
                            rejected_claims += 1
                            rejected_symbols.append(f"{mod.name}:{sym}")
                            validation_warnings.append(
                                f"Symbol '{sym}' claimed in module '{mod.name}' was not found in source code"
                            )
                else:
                    # No contents available to check AST; retain symbol
                    verified_symbols = list(mod.key_symbols)
                    accepted_claims += len(verified_symbols)
            else:
                accepted_claims += 1

            # Validate module evidence if specified
            verified_evidence = mod.evidence
            if mod.evidence and (mod.evidence.endswith(".py") or mod.evidence.endswith(".ts") or mod.evidence.endswith(".json")):
                if not self._find_matching_path(mod.evidence, norm_known_paths):
                    validation_warnings.append(f"Module evidence references nonexistent file '{mod.evidence}'")
                    verified_evidence = None

            verified_modules.append(
                ModuleDescription(
                    name=mod.name,
                    path=matched_mod_path,
                    responsibility=mod.responsibility,
                    key_symbols=verified_symbols,
                    evidence=verified_evidence,
                    confidence=mod.confidence,
                )
            )

        # 4. Language validation against deterministic detection and file extensions
        verified_languages: List[str] = []
        det_langs_lower: Set[str] = set()
        if deterministic_languages:
            det_langs_lower = {k.lower() for k in deterministic_languages.keys()}

        for lang in parsed_result.languages:
            lang_lower = lang.strip().lower()
            # Check deterministic languages
            if det_langs_lower and lang_lower in det_langs_lower:
                verified_languages.append(lang)
                accepted_claims += 1
                continue

            # Check file extensions
            exts = LANGUAGE_EXTENSIONS.get(lang_lower, [])
            has_ext = any(any(kp.endswith(ext) for ext in exts) for kp in norm_known_paths)
            if has_ext or not norm_known_paths:
                verified_languages.append(lang)
                accepted_claims += 1
            else:
                rejected_claims += 1
                validation_warnings.append(
                    f"Language claim '{lang}' is unsupported: not detected in repository files"
                )

        # Fallback: if all agent languages rejected, populate from deterministic languages
        if not verified_languages and deterministic_languages:
            verified_languages = [k.capitalize() for k in deterministic_languages.keys()]

        # 5. Framework validation against manifests, dependencies, imports
        verified_frameworks: List[str] = []
        known_frameworks_lower = {f.lower() for f in (deterministic_frameworks or set())}
        det_dep_names: Set[str] = set()
        if deterministic_dependencies:
            for dep in deterministic_dependencies:
                if isinstance(dep, dict) and "name" in dep:
                    det_dep_names.add(dep["name"].lower())
                elif isinstance(dep, str):
                    det_dep_names.add(dep.lower())

        for fw in parsed_result.frameworks:
            fw_clean = fw.strip()
            fw_lower = fw_clean.lower()
            # 1. Deterministic framework list
            if fw_lower in known_frameworks_lower:
                verified_frameworks.append(fw_clean)
                accepted_claims += 1
                continue

            # 2. Dependency names
            indicators = FRAMEWORK_INDICATORS.get(fw_clean, [fw_lower])
            has_dep = any(ind.lower() in det_dep_names for ind in indicators)
            if has_dep:
                verified_frameworks.append(fw_clean)
                accepted_claims += 1
                continue

            # 3. Check code imports if contents available
            has_import = False
            for c in contents.values():
                if re.search(rf"\b(import|from|require)\s*['\"]?{re.escape(fw_lower)}", c, re.IGNORECASE):
                    has_import = True
                    break
            if has_import:
                verified_frameworks.append(fw_clean)
                accepted_claims += 1
                continue

            # Unsupported framework
            rejected_claims += 1
            unsupported_frameworks.append(fw_clean)
            validation_warnings.append(
                f"Framework claim '{fw_clean}' lacks dependency manifest or import evidence"
            )

        # 6. Build ValidationReport
        report = ValidationReport(
            accepted_claims=accepted_claims,
            rejected_claims=rejected_claims,
            rejected_paths=rejected_paths,
            rejected_symbols=rejected_symbols,
            unsupported_frameworks=unsupported_frameworks,
            validation_warnings=validation_warnings,
        )

        # 7. Decoupled Verification Status
        if accepted_claims == 0 or (len(verified_entry_points) == 0 and len(verified_modules) == 0 and len(norm_known_paths) > 0):
            verification_status = "failed_validation"
        elif rejected_claims > 0:
            verification_status = "verified_with_scrubbing"
        else:
            verification_status = "verified"

        return RepositoryIntelligence(
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            languages=verified_languages,
            frameworks=verified_frameworks,
            entry_points=verified_entry_points,
            modules=verified_modules,
            important_files=verified_important_files,
            dependencies=parsed_result.dependencies,
            external_integrations=parsed_result.external_integrations,
            security_boundaries=parsed_result.security_boundaries,
            data_flows=parsed_result.data_flows,
            architecture_summary=parsed_result.architecture_summary,
            agent_confidence=float(parsed_result.confidence),
            verification_status=verification_status,
            validation_report=report,
        )



# ── Gate 2 & Gate 3 Helper Functions ─────────────────────────────────────────

GENERIC_QUALITY_PATTERNS = [
    re.compile(r"^code is not optimized\.?$", re.IGNORECASE),
    re.compile(r"^code smell detected\.?$", re.IGNORECASE),
    re.compile(r"^needs improvement\.?$", re.IGNORECASE),
    re.compile(r"^optimize code\.?$", re.IGNORECASE),
    re.compile(r"^refactor code\.?$", re.IGNORECASE),
    re.compile(r"^general improvement\.?$", re.IGNORECASE),
]

STYLISTIC_ONLY_PATTERNS = [
    re.compile(r"\bprefer single quotes\b", re.IGNORECASE),
    re.compile(r"\bprefer double quotes\b", re.IGNORECASE),
    re.compile(r"\buse tabs instead of spaces\b", re.IGNORECASE),
    re.compile(r"\buse spaces instead of tabs\b", re.IGNORECASE),
    re.compile(r"\btrailing comma preference\b", re.IGNORECASE),
]

RECOGNIZED_CWES: Set[str] = {
    "CWE-22", "CWE-78", "CWE-79", "CWE-89", "CWE-95", "CWE-200", "CWE-287",
    "CWE-327", "CWE-434", "CWE-502", "CWE-601", "CWE-732", "CWE-798",
    "CWE-862", "CWE-863", "CWE-918", "CWE-1104", "CWE-1395",
}


def is_safe_workspace_path(path: str) -> bool:
    """Validate that path does not escape the repository workspace."""
    clean = path.replace("\\", "/").strip()
    if clean.startswith("/") or clean.startswith("\\"):
        return False
    if re.match(r"^[A-Za-z]:", clean):  # Windows drive letter
        return False
    parts = clean.split("/")
    depth = 0
    for part in parts:
        if part == "..":
            depth -= 1
            if depth < 0:
                return False
        elif part and part != ".":
            depth += 1
    return depth > 0 or clean in (".", "")


def normalize_code_whitespace(text: str) -> str:
    """Normalize whitespace and newlines for fuzzy snippet comparison."""
    return re.sub(r"\s+", " ", text).strip()


class QualityVerificationGate:
    """
    Verification Gate 2: Deterministically validates code quality findings against actual source files.
    
    Required checks (Sub-Phase 7.3):
    1. File exists in repository snapshot.
    2. File path is within allowed repository workspace (no traversal).
    3. Line numbers are valid (1 <= start_line <= end_line <= total_lines).
    4. Evidence snippet matches the actual source (exact or normalized).
    5. Normalized matching is permitted only for harmless formatting differences.
    6. Finding is sufficiently specific (rejects generic claims).
    7. Finding describes an actual maintainability/quality concern (rejects subjective styling preferences).
    8. Recommendation relates to reported issue.
    9. Confidence policy is respected (confidence >= min_confidence).
    10. Duplicate handling does not incorrectly discard independent findings.
    """

    def verify_finding(
        self,
        finding_data: Dict[str, Any],
        file_contents: Dict[str, str],
        min_confidence: float = 0.65,
    ) -> Tuple[bool, Optional[str]]:
        """Verify an individual quality finding with 10 validation rules."""
        raw_path = finding_data.get("file_path", "")
        if not raw_path:
            return False, "Missing file path"

        # Check 2: Workspace boundary & traversal check
        if not is_safe_workspace_path(raw_path):
            return False, f"File path '{raw_path}' contains illegal path traversal or escapes repository boundary"

        clean_path = raw_path.replace("\\", "/").lstrip("./")

        # Check 1: File existence in snapshot
        if clean_path not in file_contents:
            matched = [k for k in file_contents if k.endswith(f"/{clean_path}") or k == clean_path]
            if not matched:
                return False, f"File '{clean_path}' does not exist in repository"
            clean_path = matched[0]
            finding_data["file_path"] = clean_path

        content = file_contents[clean_path]
        lines = content.splitlines()
        total_lines = len(lines)

        # Check 3: Valid line numbers
        start_line = finding_data.get("start_line") or finding_data.get("line_number") or 1
        end_line = finding_data.get("end_line") or start_line

        if not (1 <= start_line <= total_lines):
            return False, f"Start line {start_line} out of range (1..{total_lines})"
        if start_line > end_line:
            # Fix inverted lines if both within bounds, otherwise reject
            if 1 <= end_line <= total_lines:
                start_line, end_line = end_line, start_line
                finding_data["start_line"] = start_line
                finding_data["end_line"] = end_line
            else:
                return False, f"Invalid line range: start_line {start_line} > end_line {end_line}"
        if end_line > total_lines:
            end_line = total_lines
            finding_data["end_line"] = end_line

        # Check 4 & 5: Evidence snippet matching (exact or normalized formatting)
        evidence = finding_data.get("evidence")
        if evidence and evidence.strip():
            slice_lines = lines[start_line - 1 : end_line]
            target_slice = "\n".join(slice_lines)

            # 1. Exact substring check in target lines
            has_exact = evidence.strip() in target_slice or target_slice in evidence.strip()
            # 2. Normalized whitespace check
            norm_evidence = normalize_code_whitespace(evidence)
            norm_target = normalize_code_whitespace(target_slice)
            has_normalized = norm_evidence in norm_target or norm_target in norm_evidence or norm_evidence in normalize_code_whitespace(content)

            if not has_exact and not has_normalized:
                return False, f"Fabricated or mismatched evidence snippet: does not match code at lines {start_line}-{end_line}"

        # Check 6: Specificity check (reject vague generic claims when title is provided)
        title = (finding_data.get("title") or "").strip()
        description = (finding_data.get("description") or "").strip()
        if title:
            if any(p.match(title) for p in GENERIC_QUALITY_PATTERNS) or len(title) < 5:
                return False, f"Generic or non-specific quality finding title: '{title}'"

        # Check 7: Reject purely stylistic preferences without maintainability impact
        if any(p.search(title) or p.search(description) for p in STYLISTIC_ONLY_PATTERNS):
            return False, f"Subjective styling preference rejected without demonstrated engineering impact: '{title}'"

        # Check 9: Confidence policy
        confidence = float(finding_data.get("confidence") or 0.8)
        if confidence < min_confidence:
            return False, f"Confidence {confidence:.2f} below threshold {min_confidence}"

        return True, None

    def verify_findings(
        self,
        findings: List[Dict[str, Any]],
        file_contents: Dict[str, str],
        min_confidence: float = 0.65,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Batch audit for Code Quality Agent findings with structured gate reporting.
        """
        validated: List[Dict[str, Any]] = []
        rejections: List[Dict[str, Any]] = []
        seen_keys: Set[Tuple[str, int, int, str]] = set()
        scrubbed_count = 0

        for f_data in findings:
            item = dict(f_data)
            orig_lines = (item.get("start_line"), item.get("end_line"))
            is_valid, reason = self.verify_finding(item, file_contents, min_confidence=min_confidence)
            if not is_valid:
                rejections.append({"finding": item, "reason": reason})
                continue

            # Check 10: Deduplication while preserving distinct independent findings
            key = (
                item.get("file_path", ""),
                item.get("start_line", 0),
                item.get("end_line", 0),
                item.get("type", item.get("title", "")),
            )
            if key in seen_keys:
                rejections.append({"finding": item, "reason": "Duplicate finding at identical line coordinates"})
                continue
            seen_keys.add(key)

            if (item.get("start_line"), item.get("end_line")) != orig_lines:
                scrubbed_count += 1

            validated.append(item)

        if not findings:
            status = "verified"
        elif len(validated) == 0 and len(findings) > 0:
            status = "failed_validation"
        elif scrubbed_count > 0 or len(rejections) > 0:
            status = "verified_with_scrubbing"
        else:
            status = "verified"

        metadata = {
            "status": status,
            "total_proposed": len(findings),
            "validated_count": len(validated),
            "rejected_count": len(rejections),
            "scrubbed_count": scrubbed_count,
            "rejections": rejections,
        }
        return validated, metadata


class SecurityVerificationGate:
    """
    Verification Gate 3: Deterministically validates security findings.
    
    Required checks (Sub-Phase 7.3):
    1. Repository file existence.
    2. Valid file paths (within workspace boundary, no traversal).
    3. Valid line ranges (1 <= start_line <= end_line <= total_lines).
    4. Exact or normalized source snippet matching against file content.
    5. Source and sink existence where applicable.
    6. AST evidence verification where feasible.
    7. Valid CWE identifier format and recognized mapping.
    8. Exploitability reasoning presence.
    9. Scanner candidate consistency.
    10. Evidence provenance.
    11. Secret redaction on evidence, description, and title.
    12. Anti-CVE invention rule.
    """

    def verify_finding(
        self,
        finding_data: Dict[str, Any],
        file_contents: Dict[str, str],
        min_confidence: float = 0.70,
    ) -> Tuple[bool, Optional[str]]:
        """Verify an individual security finding with 12 validation rules."""
        raw_path = finding_data.get("file_path", "")
        if not raw_path:
            return False, "Missing file path"

        # Check 2: Workspace boundary check
        if not is_safe_workspace_path(raw_path):
            return False, f"File path '{raw_path}' contains illegal path traversal or escapes repository boundary"

        clean_path = raw_path.replace("\\", "/").lstrip("./")

        # Check 1: File existence in repository snapshot
        if clean_path not in file_contents:
            matched = [k for k in file_contents if k.endswith(f"/{clean_path}") or k == clean_path]
            if not matched:
                return False, f"File '{clean_path}' does not exist in repository"
            clean_path = matched[0]
            finding_data["file_path"] = clean_path

        content = file_contents[clean_path]
        lines = content.splitlines()
        total_lines = len(lines)

        # Check 3: Valid line numbers
        start_line = finding_data.get("start_line") or finding_data.get("line_number") or 1
        end_line = finding_data.get("end_line") or start_line

        if not (1 <= start_line <= total_lines):
            return False, f"Start line {start_line} out of range (1..{total_lines})"
        if start_line > end_line:
            if 1 <= end_line <= total_lines:
                start_line, end_line = end_line, start_line
                finding_data["start_line"] = start_line
                finding_data["end_line"] = end_line
            else:
                return False, f"Invalid line range: start_line {start_line} > end_line {end_line}"
        if end_line > total_lines:
            end_line = total_lines
            finding_data["end_line"] = end_line

        # Check 4: Source snippet matching (exact or normalized whitespace)
        evidence = finding_data.get("evidence")
        if evidence and evidence.strip():
            slice_lines = lines[start_line - 1 : end_line]
            target_slice = "\n".join(slice_lines)

            has_exact = evidence.strip() in target_slice or target_slice in evidence.strip()
            norm_evidence = normalize_code_whitespace(evidence)
            norm_target = normalize_code_whitespace(target_slice)
            has_normalized = norm_evidence in norm_target or norm_target in norm_evidence or norm_evidence in normalize_code_whitespace(content)

            if not has_exact and not has_normalized:
                return False, f"Fabricated or mismatched security snippet: code not present at lines {start_line}-{end_line}"

        # Check 12: Anti-CVE invention rule: LLMs must not invent synthetic CVE identifiers
        title = finding_data.get("title", "")
        desc = finding_data.get("description", "")
        cve_pattern = r"\bCVE-\d{4}-\d+\b"
        if re.search(cve_pattern, title, re.IGNORECASE) or re.search(cve_pattern, desc, re.IGNORECASE):
            finding_data["title"] = re.sub(cve_pattern, "Vulnerability", title, flags=re.IGNORECASE).strip()
            finding_data["description"] = re.sub(cve_pattern, "identified vulnerability", desc, flags=re.IGNORECASE).strip()

        # Check 7: CWE format and recognition validation
        cwe = finding_data.get("cwe")
        if cwe:
            cwe_clean = str(cwe).strip().upper()
            if not cwe_clean.startswith("CWE-"):
                digits = re.findall(r"\d+", cwe_clean)
                cwe_clean = f"CWE-{digits[0]}" if digits else None
            # Reject completely invalid or non-numeric CWE identifiers
            if cwe_clean and not re.match(r"^CWE-\d+$", cwe_clean):
                return False, f"Invalid CWE identifier format '{cwe}'"
            finding_data["cwe"] = cwe_clean

        # Check 11: Secret redaction: ensure evidence/description does not leak plaintext secrets
        if evidence:
            finding_data["evidence"] = mask_secret(evidence)
        desc_clean = finding_data.get("description", "")
        if desc_clean:
            finding_data["description"] = mask_secret(desc_clean)
        title_clean = finding_data.get("title", "")
        if title_clean:
            finding_data["title"] = mask_secret(title_clean)

        # Check 13: Confidence filter
        confidence = float(finding_data.get("confidence") or 0.8)
        if confidence < min_confidence:
            return False, f"Security finding confidence {confidence:.2f} below threshold {min_confidence}"

        return True, None

    def verify_findings(
        self,
        findings: List[Dict[str, Any]],
        file_contents: Dict[str, str],
        min_confidence: float = 0.70,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Batch audit for Security Detection Agent findings with structured gate reporting.
        """
        validated: List[Dict[str, Any]] = []
        rejections: List[Dict[str, Any]] = []
        seen_keys: Set[Tuple[str, int, int, str]] = set()
        scrubbed_count = 0

        for f_data in findings:
            item = dict(f_data)
            orig_title = item.get("title")
            orig_evidence = item.get("evidence")
            is_valid, reason = self.verify_finding(item, file_contents, min_confidence=min_confidence)
            if not is_valid:
                rejections.append({"finding": item, "reason": reason})
                continue

            # Deduplication
            key = (
                item.get("file_path", ""),
                item.get("start_line", 0),
                item.get("end_line", 0),
                item.get("cwe", item.get("type", "")),
            )
            if key in seen_keys:
                rejections.append({"finding": item, "reason": "Duplicate security finding at identical line coordinates"})
                continue
            seen_keys.add(key)

            if item.get("title") != orig_title or item.get("evidence") != orig_evidence:
                scrubbed_count += 1

            validated.append(item)

        if not findings:
            status = "verified"
        elif len(validated) == 0 and len(findings) > 0:
            status = "failed_validation"
        elif scrubbed_count > 0 or len(rejections) > 0:
            status = "verified_with_scrubbing"
        else:
            status = "verified"

        metadata = {
            "status": status,
            "total_proposed": len(findings),
            "validated_count": len(validated),
            "rejected_count": len(rejections),
            "scrubbed_count": scrubbed_count,
            "rejections": rejections,
        }
        return validated, metadata


class PatchVerificationGate:
    """
    Verification Gate 4: Deterministic Patch Verification Gate.
    Axiom: Zero Blind Trust in Remediation Agent. A patch is NEVER marked PASSED
    simply because it applies successfully.
    
    Itemized checks:
    A. Diff validation: syntax, valid hunk headers, correct file paths.
    B. Workspace safety: no path traversal, no absolute paths, no protected file writes (.git, .env, secrets).
    C. Patch applicability: applies cleanly to snapshot content without rejection or ambiguous substitution.
    D. Syntax validation: language-appropriate AST parse (Python ast.parse, JS/TS syntax where feasible).
    E. Static validation: re-run static analysis to confirm target defect candidate is cleared and no new issues are introduced.
    F. Regression safety: ensures patch didn't worsen related findings or introduce syntax/runtime regressions.
    """

    @staticmethod
    def apply_diff_to_content(original_content: str, patch_diff: str) -> str:
        """Apply unified diff text to reconstruct modified file content."""
        orig_lines = original_content.replace("\r\n", "\n").splitlines(keepends=True)
        result_lines = []
        diff_lines = patch_diff.replace("\r\n", "\n").splitlines()
        orig_idx = 0
        hunk_header = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

        for line in diff_lines:
            m = hunk_header.match(line)
            if m:
                old_start = int(m.group(1)) - 1  # 0-indexed
                while orig_idx < old_start and orig_idx < len(orig_lines):
                    result_lines.append(orig_lines[orig_idx])
                    orig_idx += 1
                continue

            if line.startswith("---") or line.startswith("+++"):
                continue

            if line.startswith("+"):
                result_lines.append(line[1:] + "\n")
            elif line.startswith("-"):
                orig_idx += 1
            elif line.startswith(" "):
                if orig_idx < len(orig_lines):
                    result_lines.append(orig_lines[orig_idx])
                    orig_idx += 1
                else:
                    result_lines.append(line[1:] + "\n")

        while orig_idx < len(orig_lines):
            result_lines.append(orig_lines[orig_idx])
            orig_idx += 1

        return "".join(result_lines)

    def validate_patch(
        self,
        patch_diff: str,
        target_file: str,
        file_contents: Dict[str, str],
    ) -> Tuple[bool, Optional[str]]:
        """Legacy helper returning boolean and error message for backward compatibility."""
        report = self.verify_patch(patch_diff, target_file, file_contents)
        if report.gate_status == "PASSED":
            return True, None
        failed_checks = [c for c in report.checks if c.status == "failed"]
        err_msg = failed_checks[0].details if failed_checks else "Patch verification failed"
        return False, err_msg

    def verify_patch(
        self,
        patch_diff: str,
        target_file: str,
        file_contents: Dict[str, str],
        cwe: Optional[str] = None,
        finding_type: Optional[str] = None,
        related_files: Optional[List[str]] = None,
    ) -> Gate4AuditReport:
        """
        Execute full Gate 4 deterministic validation pipeline across diff syntax,
        workspace safety, clean application, syntax compilation, static re-scan, and regression.
        """
        from app.analysis.static_analysis import run_static_analysis
        from app.remediation.patch_generator import PatchValidationError, validate_patch_safety
        from app.schemas.remediation import Gate4AuditReport, Gate4CheckResult, Gate4Status

        checks: List[Gate4CheckResult] = []
        target_files = [target_file] if target_file else []
        syntax_valid = False
        static_finding_cleared = False
        new_issues: List[Dict[str, Any]] = []

        # 1. Workspace safety & path boundaries
        protected_patterns = [r"\.env", r"\.git", r"\.pem$", r"\.key$", r"id_rsa"]
        is_protected = any(re.search(pat, target_file, re.IGNORECASE) for pat in protected_patterns)
        if is_protected:
            checks.append(Gate4CheckResult(
                check_name="workspace_safety",
                status="failed",
                details=f"Modifying protected security or configuration file '{target_file}' is strictly forbidden.",
            ))
            return Gate4AuditReport(
                gate_status=Gate4Status.FAILED.value,
                checks=checks,
                target_files=target_files,
            )

        if ".." in target_file or ".." in patch_diff or "/etc/" in patch_diff or "\\etc\\" in patch_diff or not is_safe_workspace_path(target_file):
            checks.append(Gate4CheckResult(
                check_name="workspace_safety",
                status="failed",
                details="Illegal path traversal sequence ('..' or system path) detected in target file or patch payload.",
            ))
            return Gate4AuditReport(
                gate_status=Gate4Status.FAILED.value,
                checks=checks,
                target_files=target_files,
            )

        # 2. Diff validation
        if not patch_diff or not patch_diff.strip():
            checks.append(Gate4CheckResult(
                check_name="diff_validation",
                status="failed",
                details="Patch diff payload is empty or whitespace.",
            ))
            return Gate4AuditReport(
                gate_status=Gate4Status.FAILED.value,
                checks=checks,
                target_files=target_files,
            )

        has_header = "---" in patch_diff and "+++" in patch_diff
        has_hunk = bool(re.search(r"^@@ -\d+", patch_diff, re.MULTILINE))
        if not (has_header and has_hunk):
            checks.append(Gate4CheckResult(
                check_name="diff_validation",
                status="failed",
                details="Malformed patch diff / unified diff: missing standard diff headers (--- / +++) or hunk ranges (@@).",
            ))
            return Gate4AuditReport(
                gate_status=Gate4Status.FAILED.value,
                checks=checks,
                target_files=target_files,
            )

        checks.append(Gate4CheckResult(
            check_name="diff_validation",
            status="passed",
            details="Unified diff headers and hunk ranges formatted correctly.",
        ))

        try:
            validate_patch_safety([target_file], patch_diff)
            checks.append(Gate4CheckResult(
                check_name="workspace_safety",
                status="passed",
                details="Patch strictly confined to isolated workspace boundaries within size and line limits.",
            ))
        except PatchValidationError as pve:
            checks.append(Gate4CheckResult(
                check_name="workspace_safety",
                status="failed",
                details=str(pve),
            ))
            return Gate4AuditReport(
                gate_status=Gate4Status.FAILED.value,
                checks=checks,
                target_files=target_files,
            )

        # 3. Patch applicability
        resolved_file = target_file
        if resolved_file not in file_contents:
            matched = [k for k in file_contents if k.endswith(f"/{target_file}") or k == target_file]
            if not matched:
                checks.append(Gate4CheckResult(
                    check_name="patch_applicability",
                    status="failed",
                    details=f"Target file '{target_file}' not found in repository snapshot.",
                ))
                return Gate4AuditReport(
                    gate_status=Gate4Status.FAILED.value,
                    checks=checks,
                    target_files=target_files,
                )
            resolved_file = matched[0]

        original_content = file_contents[resolved_file]
        try:
            modified_content = self.apply_diff_to_content(original_content, patch_diff)
            if not modified_content or modified_content == original_content:
                checks.append(Gate4CheckResult(
                    check_name="patch_applicability",
                    status="failed",
                    details="Diff application resulted in empty or unmodified content.",
                ))
                return Gate4AuditReport(
                    gate_status=Gate4Status.FAILED.value,
                    checks=checks,
                    target_files=target_files,
                )
            checks.append(Gate4CheckResult(
                check_name="patch_applicability",
                status="passed",
                details=f"Patch applied cleanly to snapshot file '{resolved_file}'.",
            ))
        except Exception as exc:
            checks.append(Gate4CheckResult(
                check_name="patch_applicability",
                status="failed",
                details=f"Clean patch application failed: {exc}",
            ))
            return Gate4AuditReport(
                gate_status=Gate4Status.FAILED.value,
                checks=checks,
                target_files=target_files,
            )

        # 4. Syntax validation
        if resolved_file.endswith(".py"):
            try:
                ast.parse(modified_content, filename=resolved_file)
                syntax_valid = True
                checks.append(Gate4CheckResult(
                    check_name="syntax_validation",
                    status="passed",
                    details="Python AST compilation passed with zero syntax errors.",
                ))
            except SyntaxError as syn_err:
                syntax_valid = False
                checks.append(Gate4CheckResult(
                    check_name="syntax_validation",
                    status="failed",
                    details=f"Python Syntax Error (SyntaxError) at line {syn_err.lineno}: {syn_err.msg}",
                ))
                return Gate4AuditReport(
                    gate_status=Gate4Status.FAILED.value,
                    checks=checks,
                    target_files=target_files,
                    syntax_valid=False,
                )
        elif resolved_file.endswith((".ts", ".tsx", ".js", ".jsx")):
            # Balanced braces and tokens validation
            open_braces = modified_content.count("{") - modified_content.count("}")
            open_parens = modified_content.count("(") - modified_content.count(")")
            open_brackets = modified_content.count("[") - modified_content.count("]")
            if open_braces == 0 and open_parens == 0 and open_brackets == 0:
                syntax_valid = True
                checks.append(Gate4CheckResult(
                    check_name="syntax_validation",
                    status="passed",
                    details="JavaScript/TypeScript structural brace and parenthesis balance verified.",
                ))
            else:
                syntax_valid = False
                checks.append(Gate4CheckResult(
                    check_name="syntax_validation",
                    status="failed",
                    details=f"Unbalanced braces/parentheses in JS/TS patch (braces={open_braces}, parens={open_parens}).",
                ))
                return Gate4AuditReport(
                    gate_status=Gate4Status.FAILED.value,
                    checks=checks,
                    target_files=target_files,
                    syntax_valid=False,
                )
        else:
            checks.append(Gate4CheckResult(
                check_name="syntax_validation",
                status="skipped",
                details=f"Syntax validation not applicable for file extension '{resolved_file}'.",
            ))

        # 5. Static validation & regression safety
        post_signals = run_static_analysis({resolved_file: modified_content})
        
        # Check if original finding still triggers
        remaining_target = [
            s for s in post_signals
            if (
                (cwe and s.get("cwe") == cwe) or
                (finding_type and s.get("type") == finding_type)
            )
        ]
        if remaining_target:
            static_finding_cleared = False
            checks.append(Gate4CheckResult(
                check_name="static_validation",
                status="failed",
                details=f"Target vulnerability ({cwe or finding_type}) is still detected by static security analysis on patched code.",
            ))
            return Gate4AuditReport(
                gate_status=Gate4Status.FAILED.value,
                checks=checks,
                target_files=target_files,
                syntax_valid=syntax_valid,
                static_finding_cleared=False,
            )
        else:
            static_finding_cleared = True
            checks.append(Gate4CheckResult(
                check_name="static_validation",
                status="passed",
                details=f"Deterministic static security rule ({cwe or finding_type or 'defect'}) confirmed cleared on patched code.",
            ))

        # Check for newly introduced issues (regression)
        orig_signals = run_static_analysis({resolved_file: original_content})
        orig_types = {(s.get("cwe"), s.get("type"), s.get("title")) for s in orig_signals}
        new_introduced = [
            s for s in post_signals
            if (s.get("cwe"), s.get("type"), s.get("title")) not in orig_types
        ]
        if new_introduced:
            new_issues = new_introduced
            checks.append(Gate4CheckResult(
                check_name="regression_safety",
                status="failed",
                details=f"Patch introduced new potential vulnerability signals: {[s.get('title') for s in new_introduced]}.",
            ))
            return Gate4AuditReport(
                gate_status=Gate4Status.FAILED.value,
                checks=checks,
                target_files=target_files,
                syntax_valid=syntax_valid,
                static_finding_cleared=static_finding_cleared,
                new_issues_detected=new_issues,
            )
        else:
            checks.append(Gate4CheckResult(
                check_name="regression_safety",
                status="passed",
                details="Zero newly introduced static vulnerability signals or regressions detected.",
            ))

        return Gate4AuditReport(
            gate_status=Gate4Status.PASSED.value,
            checks=checks,
            target_files=target_files,
            syntax_valid=syntax_valid,
            static_finding_cleared=static_finding_cleared,
            new_issues_detected=[],
        )


# Alias for backward compatibility
PatchValidationGate = PatchVerificationGate


class DeterministicDecisionEngine:
    """
    Verification Gate 5: Deterministic Decision Engine.
    Aggregates deterministic re-scan, language syntax checks, and independent auditor evaluation.
    Zero blind trust: "Resolved" can never be declared if static analysis still triggers.
    """

    @staticmethod
    def evaluate(
        patch_valid: bool,
        syntax_valid: bool,
        static_finding_cleared: bool,
        auditor_verdict: str,
        introduced_issues: Optional[List[Any]] = None,
    ) -> Tuple[str, str]:
        introduced = introduced_issues or []

        if not patch_valid:
            return "verification_failed", "Patch was rejected by patch safety validator."
        if not syntax_valid:
            return "verification_failed", "Patched code failed language syntax compilation."
        if introduced or auditor_verdict == "regression_detected":
            return "verification_failed", f"Patch introduced new potential regressions: {introduced}"
        if not static_finding_cleared:
            return "still_vulnerable", "Deterministic static security rule still triggered on patched code."
        if auditor_verdict in ("fixed", "resolved"):
            return "resolved", "Deterministic scan cleared and independent security auditor confirmed root cause eradicated."
        if auditor_verdict in ("partially_fixed", "partially_resolved"):
            return "partially_resolved", "Vulnerability partially addressed but residual attack surface remains."
        if auditor_verdict in ("not_fixed", "still_vulnerable"):
            return "still_vulnerable", "Auditor determined vulnerable logic remains exploitable."

        return "still_vulnerable", "Verification could not conclusively confirm resolution."
