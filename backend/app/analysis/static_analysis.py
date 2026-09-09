"""
Deterministic static security analysis engine.

Implements rule-based and regex/entropy detection for common vulnerabilities:
- SQL Injection (CWE-89)
- Cross-Site Scripting (CWE-79)
- Hardcoded Secrets with strict redaction (CWE-798)
- Command Injection (CWE-78)
- Path Traversal (CWE-22)
- Insecure File Handling (CWE-732 / CWE-434)

CRITICAL SECURITY REQUIREMENT:
Raw secret values are strictly redacted before output to prevent credential
leakage into database, logs, prompts, or API responses.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class StaticFinding:
    """A finding produced by deterministic static analysis."""

    category: str
    type: str
    severity: str
    title: str
    description: str
    file_path: str
    start_line: int
    end_line: int
    confidence: float
    evidence: str
    cwe: str
    source: str = "security_static"

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "type": self.type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "cwe": self.cwe,
            "source": self.source,
        }


# ── Secret Redaction & Helpers ───────────────────────────────────────────────

def mask_secret(secret: str) -> str:
    """Mask sensitive string leaving only the prefix to prevent credential leakage."""
    if not secret:
        return "[REDACTED]"
    if len(secret) <= 8:
        return "*" * len(secret)
    # Keep up to first 4 chars, mask the rest
    prefix = secret[:4]
    return prefix + "*" * (len(secret) - 4)


def shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy for a string to detect random high-entropy keys."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    for x in set(data):
        p_x = float(data.count(x)) / length
        if p_x > 0:
            entropy += - p_x * math.log2(p_x)
    return entropy


# Known placeholder keywords to suppress false-positive secret warnings
PLACEHOLDER_EXACT = {
    "123456", "password", "changeme", "placeholder", "dummy", "secret", "token",
}
PLACEHOLDER_SUBSTRINGS = {
    "your_api_key", "your_secret", "your_token", "test-secret", "example-token",
    "<token>", "<api_key>", "todo", "fixme", "insert_key_here", "sample_secret",
}


# ── Static Security Rules ───────────────────────────────────────────────────

class StaticSecurityAnalyzer:
    """Deterministic security rule engine."""

    # 1. SQL Injection patterns: concatenation / interpolation into queries
    SQLI_PATTERNS = [
        (
            re.compile(r"""f["'].*(?:SELECT|INSERT|UPDATE|DELETE)\b.*\{.*\}["']""", re.IGNORECASE),
            "SQL query formatted using f-string string interpolation without parameterized inputs.",
        ),
        (
            re.compile(r"""(?:SELECT|INSERT|UPDATE|DELETE)\b.*["']\s*\+\s*[a-zA-Z_0-9]+""", re.IGNORECASE),
            "SQL query constructed using string concatenation without parameterized bindings.",
        ),
        (
            re.compile(r"""(?:execute|raw|query)\s*\(\s*f["'].*\{.*\}["']\s*\)""", re.IGNORECASE),
            "Database execution of interpolated f-string without parameterization.",
        ),
        (
            re.compile(r"""(?:execute|raw|query)\s*\(\s*["'].*["']\s*\+\s*[a-zA-Z_0-9]+\s*\)""", re.IGNORECASE),
            "Database execution of dynamically concatenated string query.",
        ),
    ]

    # 2. XSS patterns: dangerous HTML injection
    XSS_PATTERNS = [
        (
            re.compile(r"""dangerouslySetInnerHTML\s*=\s*\{\s*\{\s*__html\s*:\s*([^}]+)\s*\}\s*\}"""),
            "Direct HTML injection via dangerouslySetInnerHTML without sanitization.",
        ),
        (
            re.compile(r"""\binnerHTML\s*=\s*(?!["'`]<)(?!["'`]$)(.+);"""),
            "Direct assignment of variable to innerHTML property can enable Cross-Site Scripting.",
        ),
        (
            re.compile(r"""v-html\s*=\s*["']([^"']+)["']"""),
            "Vue v-html directive rendering unsanitized user content.",
        ),
    ]

    # 3. Command Injection patterns
    COMMAND_INJECTION_PATTERNS = [
        (
            re.compile(r"""subprocess\.(run|Popen|call|check_output)\s*\([^)]*shell\s*=\s*True[^)]*\)"""),
            "Subprocess invocation with shell=True allows command injection if arguments include user input.",
        ),
        (
            re.compile(r"""os\.system\s*\(\s*f["'].*\{.*\}["']\s*\)"""),
            "os.system execution with formatted string interpolation.",
        ),
        (
            re.compile(r"""os\.system\s*\(\s*["'].*["']\s*\+\s*[a-zA-Z_0-9]+\s*\)"""),
            "os.system execution with concatenated string command.",
        ),
        (
            re.compile(r"""child_process\.exec\s*\(\s*[`"'].*\$\{.*\}"""),
            "child_process.exec called with template literal interpolation.",
        ),
    ]

    # 4. Path Traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        (
            re.compile(r"""(open|readFile|readFileSync)\s*\(\s*(?:os\.path\.join|path\.join)\s*\([^)]*(?:request|req\.|params|args|user)[^)]*\)"""),
            "File read operation using path.join with unsanitized user/request parameters.",
        ),
        (
            re.compile(r"""(?:os\.path\.join|path\.join)\s*\([^)]*(?:request|req\.|params|args|user)[^)]*\)"""),
            "Path constructed from user/request parameters without path normalization.",
        ),
        (
            re.compile(r"""(open|readFile|readFileSync)\s*\(\s*f["'].*\{.*(?:path|file|name|dir).*\}["']\s*\)"""),
            "File path constructed from unvalidated string interpolation.",
        ),
    ]

    # 5. Insecure File Handling patterns
    INSECURE_FILE_PATTERNS = [
        (
            re.compile(r"""(chmod|fchmod)\s*\([^,]+,\s*(?:0o777|0777|777)\)"""),
            "Overly permissive file permissions (0777) granted.",
            "high",
            "CWE-732",
        ),
        (
            re.compile(r"""os\.chmod\s*\([^,]+,\s*(?:0o777|0777|777|stat\.S_IRWXU\s*\|\s*stat\.S_IRWXG\s*\|\s*stat\.S_IRWXO)\)"""),
            "Overly permissive file permissions (chmod 777) allowing world write and execute access.",
            "high",
            "CWE-732",
        ),
    ]

    # 6. Secret patterns (with regex capture groups for redaction)
    SECRET_RULES = [
        (
            re.compile(r"""\b(AKIA[0-9A-Z]{16})\b"""),
            "AWS Access Key ID",
            "hardcoded_secret",
            "critical",
            "CWE-798",
        ),
        (
            re.compile(r"""-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"""),
            "Embedded Private Key",
            "hardcoded_secret",
            "critical",
            "CWE-798",
        ),
        (
            re.compile(
                r"""(?:api[_-]?key|secret|token|password|passwd|auth[_-]?token)\s*[:=]\s*["']([A-Za-z0-9_\-\.+=/]{20,})["']""",
                re.IGNORECASE,
            ),
            "Hardcoded API Token or Password",
            "hardcoded_secret",
            "high",
            "CWE-798",
        ),
    ]

    def analyze_file(self, file_path: str, content: str) -> List[StaticFinding]:
        """Analyze a single source file with all deterministic security rules."""
        findings: List[StaticFinding] = []
        lines = content.splitlines()

        # Skip obvious documentation or markdown from false positives
        if file_path.endswith((".md", ".txt", ".rst", ".svg", ".lock")):
            return findings

        # Check line-by-line and multi-line patterns
        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "#", "/*", "*")):
                # Skip pure comments
                continue

            # 1. SQL Injection
            for pattern, desc in self.SQLI_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="sql_injection",
                            severity="high",
                            title="Potential SQL Injection",
                            description=desc,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.88,
                            evidence=stripped,
                            cwe="CWE-89",
                        )
                    )
                    break  # avoid multiple hits on same line

            # 2. XSS
            for pattern, desc in self.XSS_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="xss",
                            severity="medium",
                            title="Potential Cross-Site Scripting (XSS)",
                            description=desc,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.85,
                            evidence=stripped,
                            cwe="CWE-79",
                        )
                    )
                    break

            # 3. Command Injection
            for pattern, desc in self.COMMAND_INJECTION_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="command_injection",
                            severity="high",
                            title="Potential Command Injection",
                            description=desc,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.90,
                            evidence=stripped,
                            cwe="CWE-78",
                        )
                    )
                    break

            # 4. Path Traversal
            for pattern, desc in self.PATH_TRAVERSAL_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="path_traversal",
                            severity="medium",
                            title="Potential Path Traversal",
                            description=desc,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.82,
                            evidence=stripped,
                            cwe="CWE-22",
                        )
                    )
                    break

            # 5. Insecure File Permissions
            for item in self.INSECURE_FILE_PATTERNS:
                pattern, desc, sev, cwe = item[0], item[1], item[2], item[3]
                if pattern.search(line):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="insecure_file_handling",
                            severity=sev,
                            title="Insecure File Permission Setting",
                            description=desc,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.95,
                            evidence=stripped,
                            cwe=cwe,
                        )
                    )
                    break

            # 6. Hardcoded Secrets (with Redaction & Placeholder Suppression)
            for pattern, title, finding_type, sev, cwe in self.SECRET_RULES:
                match = pattern.search(line)
                if not match:
                    continue

                matched_val = match.group(1) if match.groups() else match.group(0)
                val_lower = matched_val.lower()

                # Check if it is an obvious placeholder
                if val_lower in PLACEHOLDER_EXACT or any(sub in val_lower for sub in PLACEHOLDER_SUBSTRINGS):
                    continue

                # Check entropy for generic tokens
                if title == "Hardcoded API Token or Password" and len(matched_val) >= 20:
                    entropy = shannon_entropy(matched_val)
                    if entropy < 3.2:
                        # Low entropy string (e.g. repeated or dictionary word), likely false positive
                        continue

                # STRICT REDACTION: Replace secret with masked version in evidence
                masked = mask_secret(matched_val)
                redacted_evidence = line.replace(matched_val, masked).strip()

                findings.append(
                    StaticFinding(
                        category="security",
                        type=finding_type,
                        severity=sev,
                        title=title,
                        description=f"Hardcoded sensitive credential pattern detected ({title}).",
                        file_path=file_path,
                        start_line=line_num,
                        end_line=line_num,
                        confidence=0.94,
                        evidence=redacted_evidence,
                        cwe=cwe,
                    )
                )
                break

        return findings

    def analyze_repository_files(self, files: Dict[str, str]) -> List[StaticFinding]:
        """Scan all provided repository files."""
        all_findings: List[StaticFinding] = []
        for file_path, content in files.items():
            all_findings.extend(self.analyze_file(file_path, content))
        return all_findings


def run_static_analysis(files: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Run deterministic static analysis across a dictionary of {file_path: content}.
    Returns a list of finding dictionaries.
    """
    analyzer = StaticSecurityAnalyzer()
    findings = analyzer.analyze_repository_files(files)
    return [f.to_dict() for f in findings]
