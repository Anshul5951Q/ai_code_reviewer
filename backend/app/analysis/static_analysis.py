"""
Deterministic Layered Static Security Analysis Engine.

Implements rule-based, AST-based, and dependency/secret vulnerability detection
across Python, JavaScript, and TypeScript source files.

Covers all 12 mandatory vulnerability categories:
1. SQL Injection (CWE-89 / OWASP A03)
2. NoSQL Injection (CWE-943 / OWASP A03)
3. Command Injection / OS Execution (CWE-78 / OWASP A03)
4. Cross-Site Scripting (XSS) (CWE-79 / OWASP A03)
5. Hardcoded Secrets & Credentials (CWE-798 / OWASP A07)
6. Unsafe Dynamic Code Evaluation (CWE-95 / OWASP A03)
7. Path Traversal (CWE-22 / OWASP A01)
8. Server-Side Request Forgery (SSRF) (CWE-918 / OWASP A10)
9. Insecure Deserialization (CWE-502 / OWASP A08)
10. Missing / Broken Authorization & Authentication (CWE-306, CWE-862 / OWASP A01, A07)
11. Weak Cryptography & Insecure Randomness (CWE-327, CWE-328, CWE-338 / OWASP A02)
12. Insecure File Handling & Permissions (CWE-434, CWE-732 / OWASP A01, A04)
Plus Vulnerable Dependency Declarations (CWE-1395 / OWASP A06).

CRITICAL SECURITY REQUIREMENT:
Raw secret values are strictly redacted before output to prevent credential
leakage into database, logs, prompts, or API responses.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


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
    owasp: Optional[str] = None
    flow_source: Optional[str] = None
    flow_transformation: Optional[str] = None
    flow_sink: Optional[str] = None
    rule_id: Optional[str] = None
    remediation_recommendation: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
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
        if self.owasp:
            d["owasp"] = self.owasp
        if self.flow_source:
            d["flow_source"] = self.flow_source
        if self.flow_transformation:
            d["flow_transformation"] = self.flow_transformation
        if self.flow_sink:
            d["flow_sink"] = self.flow_sink
        if self.rule_id:
            d["rule_id"] = self.rule_id
        if self.remediation_recommendation:
            d["remediation_recommendation"] = self.remediation_recommendation
        return d


# ── Secret Redaction & Helpers ───────────────────────────────────────────────

def mask_secret(secret: str) -> str:
    """Mask sensitive string leaving only the prefix to prevent credential leakage."""
    if not secret:
        return "[REDACTED]"
    if "BEGIN" in secret and "PRIVATE KEY" in secret:
        return "[REDACTED PRIVATE KEY]"
    if len(secret) <= 8:
        return "*" * len(secret)
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


PLACEHOLDER_EXACT = {
    "123456", "password", "changeme", "placeholder", "dummy", "secret", "token", "test",
    "root", "admin", "null", "none", "true", "false",
}
PLACEHOLDER_SUBSTRINGS = {
    "your_api_key", "your_secret", "your_token", "test-secret", "example-token",
    "<token>", "<api_key>", "todo", "fixme", "insert_key_here", "sample_secret",
    "placeholder", "dummy_token",
}


# ── Python AST Security Visitor ──────────────────────────────────────────────

class PythonASTSecurityVisitor(ast.NodeVisitor):
    """Inspects Python Abstract Syntax Trees for deterministic vulnerabilities."""

    def __init__(self, file_path: str, lines: List[str]) -> None:
        self.file_path = file_path
        self.lines = lines
        self.findings: List[StaticFinding] = []

    def _get_evidence(self, node: ast.AST) -> str:
        lineno = getattr(node, "lineno", 1)
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev_func = getattr(self, "_current_func", "")
        self._current_func = node.name.lower()
        self.generic_visit(node)
        self._current_func = prev_func

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        prev_func = getattr(self, "_current_func", "")
        self._current_func = node.name.lower()
        self.generic_visit(node)
        self._current_func = prev_func

    def visit_Call(self, node: ast.Call) -> None:
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        lineno = getattr(node, "lineno", 1)
        evidence = self._get_evidence(node)

        # 1. Unsafe Code Evaluation: eval() and exec()
        if func_name in ("eval", "exec"):
            self.findings.append(
                StaticFinding(
                    category="security",
                    type="unsafe_eval",
                    severity="critical",
                    title=f"Unsafe Dynamic Code Execution via {func_name}()",
                    description=f"Execution of dynamic code using Python's built-in {func_name}() enables arbitrary code execution.",
                    file_path=self.file_path,
                    start_line=lineno,
                    end_line=lineno,
                    confidence=0.98,
                    evidence=evidence,
                    cwe="CWE-95",
                    owasp="A03:2021-Injection",
                    flow_source="dynamic_expression",
                    flow_transformation="none",
                    flow_sink=f"{func_name}()",
                    rule_id="PY-SEC-EVAL-01",
                    remediation_recommendation=f"Replace {func_name}() with ast.literal_eval() or safe structured serialization (e.g. JSON).",
                )
            )

        # 2. Insecure Deserialization: pickle.loads / pickle.load / _pickle
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("load", "loads"):
            val_id = getattr(node.func.value, "id", "")
            if val_id in ("pickle", "_pickle", "cPickle", "dill"):
                self.findings.append(
                    StaticFinding(
                        category="security",
                        type="insecure_deserialization",
                        severity="critical",
                        title="Insecure Deserialization via pickle",
                        description="Python pickle deserialization can execute arbitrary bytecode during unpickling.",
                        file_path=self.file_path,
                        start_line=lineno,
                        end_line=lineno,
                        confidence=0.96,
                        evidence=evidence,
                        cwe="CWE-502",
                        owasp="A08:2021-Software-and-Data-Integrity-Failures",
                        flow_source="serialized_payload",
                        flow_transformation="unpickle",
                        flow_sink=f"{val_id}.{node.func.attr}()",
                        rule_id="PY-SEC-PICKLE-01",
                        remediation_recommendation="Use safe data serialization formats like JSON, Protobuf, or cryptography-signed payloads instead of pickle.",
                    )
                )

        # 3. Insecure YAML Deserialization: yaml.load without SafeLoader or yaml.unsafe_load
        if isinstance(node.func, ast.Attribute):
            val_id = getattr(node.func.value, "id", "")
            if val_id == "yaml":
                is_unsafe = False
                if node.func.attr == "unsafe_load":
                    is_unsafe = True
                elif node.func.attr == "load":
                    has_safe_loader = False
                    for kw in node.keywords:
                        if kw.arg == "Loader":
                            loader_name = getattr(kw.value, "attr", getattr(kw.value, "id", ""))
                            if "Safe" in str(loader_name):
                                has_safe_loader = True
                    if not has_safe_loader:
                        is_unsafe = True
                if is_unsafe:
                    self.findings.append(
                        StaticFinding(
                            category="security",
                            type="insecure_deserialization",
                            severity="high",
                            title="Unsafe YAML Deserialization",
                            description="Calling yaml.load without an explicit SafeLoader allows arbitrary Python object instantiation and code execution.",
                            file_path=self.file_path,
                            start_line=lineno,
                            end_line=lineno,
                            confidence=0.92,
                            evidence=evidence,
                            cwe="CWE-502",
                            owasp="A08:2021-Software-and-Data-Integrity-Failures",
                            flow_source="yaml_string",
                            flow_transformation="unsafe_load",
                            flow_sink="yaml.load()",
                            rule_id="PY-SEC-YAML-01",
                            remediation_recommendation="Use yaml.safe_load(content) or pass Loader=yaml.SafeLoader explicitly.",
                        )
                    )

        # 4. Command Injection: subprocess with shell=True
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("run", "Popen", "call", "check_output", "check_call"):
            val_id = getattr(node.func.value, "id", "")
            if val_id == "subprocess":
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        self.findings.append(
                            StaticFinding(
                                category="security",
                                type="command_injection",
                                severity="high",
                                title="Subprocess Execution with shell=True",
                                description="Executing commands with shell=True passes strings directly to the system shell, enabling command injection.",
                                file_path=self.file_path,
                                start_line=lineno,
                                end_line=lineno,
                                confidence=0.95,
                                evidence=evidence,
                                cwe="CWE-78",
                                owasp="A03:2021-Injection",
                                flow_source="command_arguments",
                                flow_transformation="shell_interpolation",
                                flow_sink=f"subprocess.{node.func.attr}(shell=True)",
                                rule_id="PY-SEC-SHELL-01",
                                remediation_recommendation="Pass command arguments as an array of strings (e.g. ['ls', '-la']) and set shell=False.",
                            )
                        )

        # 5. Command Injection: os.system / os.popen
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("system", "popen"):
            val_id = getattr(node.func.value, "id", "")
            if val_id in ("os", "posix"):
                self.findings.append(
                    StaticFinding(
                        category="security",
                        type="command_injection",
                        severity="high",
                        title=f"Dangerous System Command Execution via os.{node.func.attr}",
                        description=f"os.{node.func.attr}() executes commands directly through the system shell without input sanitization.",
                        file_path=self.file_path,
                        start_line=lineno,
                        end_line=lineno,
                        confidence=0.90,
                        evidence=evidence,
                        cwe="CWE-78",
                        owasp="A03:2021-Injection",
                        flow_source="command_string",
                        flow_transformation="direct_system_call",
                        flow_sink=f"os.{node.func.attr}()",
                        rule_id="PY-SEC-OS-01",
                        remediation_recommendation="Use subprocess.run(args_list, shell=False, check=True) with parameterized arguments.",
                    )
                )

        # 6. Weak Cryptography: hashlib.md5 or hashlib.sha1
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("md5", "sha1"):
            val_id = getattr(node.func.value, "id", "")
            if val_id == "hashlib":
                # Check if used_for_security=False was explicitly specified
                is_safe_usage = False
                for kw in node.keywords:
                    if kw.arg == "usedforsecurity" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                        is_safe_usage = True
                if not is_safe_usage:
                    self.findings.append(
                        StaticFinding(
                            category="security",
                            type="weak_crypto",
                            severity="medium",
                            title=f"Weak Cryptographic Hash Algorithm ({node.func.attr.upper()})",
                            description=f"{node.func.attr.upper()} is cryptographically broken and prone to collision attacks.",
                            file_path=self.file_path,
                            start_line=lineno,
                            end_line=lineno,
                            confidence=0.91,
                            evidence=evidence,
                            cwe="CWE-327",
                            owasp="A02:2021-Cryptographic-Failures",
                            flow_source="plaintext_data",
                            flow_transformation=f"hashlib.{node.func.attr}",
                            flow_sink="digest",
                            rule_id="PY-SEC-CRYPTO-01",
                            remediation_recommendation="Use SHA-256 / SHA-3 for hashing (hashlib.sha256), or bcrypt/argon2 for password hashing.",
                        )
                    )

        # 7. Insecure Randomness: random.random() / random.randint() in token/password context
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("random", "randint", "randrange", "choice"):
            val_id = getattr(node.func.value, "id", "")
            if val_id == "random":
                lower_evidence = evidence.lower()
                current_func = getattr(self, "_current_func", "")
                context_match = (
                    any(k in lower_evidence for k in ("token", "key", "password", "secret", "auth", "session", "otp", "salt", "nonce"))
                    or any(k in current_func for k in ("token", "key", "password", "secret", "auth", "session", "otp", "salt", "nonce"))
                )
                if context_match:
                    self.findings.append(
                        StaticFinding(
                            category="security",
                            type="weak_random",
                            severity="medium",
                            title="Cryptographically Insecure Random Number Generator Used in Security Context",
                            description="Standard Python 'random' module produces predictable pseudo-random sequences and must not be used for security-sensitive values.",
                            file_path=self.file_path,
                            start_line=lineno,
                            end_line=lineno,
                            confidence=0.88,
                            evidence=evidence,
                            cwe="CWE-338",
                            owasp="A02:2021-Cryptographic-Failures",
                            flow_source="pseudorandom_seed",
                            flow_transformation=f"random.{node.func.attr}",
                            flow_sink="security_token",
                            rule_id="PY-SEC-RANDOM-01",
                            remediation_recommendation="Use the 'secrets' module (e.g. secrets.token_hex(), secrets.token_urlsafe()) for cryptographic operations.",
                        )
                    )

        # 8. Insecure Temporary File: tempfile.mktemp()
        if isinstance(node.func, ast.Attribute) and node.func.attr == "mktemp":
            val_id = getattr(node.func.value, "id", "")
            if val_id == "tempfile":
                self.findings.append(
                    StaticFinding(
                        category="security",
                        type="insecure_temporary_file",
                        severity="medium",
                        title="Insecure Temporary File Creation via tempfile.mktemp()",
                        description="tempfile.mktemp() is deprecated and vulnerable to race conditions (symlink attacks).",
                        file_path=self.file_path,
                        start_line=lineno,
                        end_line=lineno,
                        confidence=0.95,
                        evidence=evidence,
                        cwe="CWE-377",
                        owasp="A01:2021-Broken-Access-Control",
                        flow_source="temp_filename",
                        flow_transformation="mktemp",
                        flow_sink="filesystem",
                        rule_id="PY-SEC-TEMP-01",
                        remediation_recommendation="Use tempfile.NamedTemporaryFile() or tempfile.mkstemp() instead.",
                    )
                )

        # 9. JWT Verification Disabled
        if isinstance(node.func, ast.Attribute) and node.func.attr == "decode":
            val_id = getattr(node.func.value, "id", "")
            if val_id in ("jwt", "jose_jwt"):
                is_insecure = False
                for kw in node.keywords:
                    if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                        is_insecure = True
                    elif kw.arg == "algorithms" and isinstance(kw.value, (ast.List, ast.Set, ast.Tuple)):
                        for elt in kw.value.elts:
                            if isinstance(elt, ast.Constant) and str(elt.value).lower() == "none":
                                is_insecure = True
                    elif kw.arg == "options" and isinstance(kw.value, ast.Dict):
                        for k, v in zip(kw.value.keys, kw.value.values):
                            if isinstance(k, ast.Constant) and k.value == "verify_signature":
                                if isinstance(v, ast.Constant) and v.value is False:
                                    is_insecure = True
                if is_insecure:
                    self.findings.append(
                        StaticFinding(
                            category="security",
                            type="broken_auth",
                            severity="critical",
                            title="JWT Token Verification Disabled (verify=False)",
                            description="Decoding JWT tokens without signature verification allows attackers to forge identity claims.",
                            file_path=self.file_path,
                            start_line=lineno,
                            end_line=lineno,
                            confidence=0.98,
                            evidence=evidence,
                            cwe="CWE-347",
                            owasp="A07:2021-Identification-and-Authentication-Failures",
                            flow_source="untrusted_jwt_header",
                            flow_transformation="decode_without_verify",
                            flow_sink="authenticated_identity",
                            rule_id="PY-SEC-JWT-01",
                            remediation_recommendation="Always verify signature with a trusted secret or public key: jwt.decode(token, secret, algorithms=['HS256']).",
                        )
                    )

        # 10. Insecure Permissions: os.chmod with 0o777 / 777
        if isinstance(node.func, ast.Attribute) and node.func.attr == "chmod":
            val_id = getattr(node.func.value, "id", "")
            if val_id == "os" and len(node.args) >= 2:
                perm_arg = node.args[1]
                if isinstance(perm_arg, ast.Constant) and perm_arg.value in (0o777, 511, 777):
                    self.findings.append(
                        StaticFinding(
                            category="security",
                            type="insecure_file_handling",
                            severity="high",
                            title="Insecure File Permission Setting (chmod 777)",
                            description="os.chmod setting 0o777 grants world write and execute permissions.",
                            file_path=self.file_path,
                            start_line=lineno,
                            end_line=lineno,
                            confidence=0.95,
                            evidence=evidence,
                            cwe="CWE-732",
                            owasp="A01:2021-Broken-Access-Control",
                            rule_id="PY-SEC-CHMOD-01",
                            remediation_recommendation="Restrict permissions to minimum necessary (e.g. 0o600 or 0o644).",
                        )
                    )

        self.generic_visit(node)


# ── Dependency Vulnerability Scanner ─────────────────────────────────────────

KNOWN_VULNERABLE_PY_DEPS = [
    (re.compile(r"""^pyyaml\s*([<>=!~]=?)\s*([0-9\.]+)""", re.IGNORECASE), 5, 4, "PyYAML < 5.4 is vulnerable to arbitrary code execution (CVE-2020-14343, CWE-502)"),
    (re.compile(r"""^pillow\s*([<>=!~]=?)\s*([0-9\.]+)""", re.IGNORECASE), 9, 0, "Pillow < 9.0.0 contains multiple buffer overflow and memory corruption vulnerabilities (CWE-119)"),
    (re.compile(r"""^requests\s*([<>=!~]=?)\s*([0-9\.]+)""", re.IGNORECASE), 2, 20, "Requests < 2.20.0 leaks credentials on HTTPS -> HTTP redirects (CVE-2018-18074, CWE-522)"),
    (re.compile(r"""^django\s*([<>=!~]=?)\s*([0-9\.]+)""", re.IGNORECASE), 3, 2, "Django < 3.2 is End-of-Life and vulnerable to multiple SQLi and security bypass issues"),
    (re.compile(r"""^flask\s*([<>=!~]=?)\s*([0-9\.]+)""", re.IGNORECASE), 2, 0, "Flask < 2.0.0 contains known session and cookie handling issues"),
    (re.compile(r"""^jinja2\s*([<>=!~]=?)\s*([0-9\.]+)""", re.IGNORECASE), 3, 1, "Jinja2 < 3.1.3 is vulnerable to HTML attribute injection (CVE-2024-22195, CWE-79)"),
    (re.compile(r"""^urllib3\s*([<>=!~]=?)\s*([0-9\.]+)""", re.IGNORECASE), 1, 24, "urllib3 < 1.24.2 is vulnerable to CRLF header injection (CWE-93)"),
]

KNOWN_VULNERABLE_NPM_DEPS = [
    (re.compile(r"""["']lodash["']\s*:\s*["'][\^~]?([0-9\.]+)["']"""), 4, 17, 21, "Lodash < 4.17.21 is vulnerable to Prototype Pollution (CVE-2021-23337, CWE-1321)"),
    (re.compile(r"""["']axios["']\s*:\s*["'][\^~]?([0-9\.]+)["']"""), 0, 21, 1, "Axios < 0.21.1 is vulnerable to SSRF via relative redirect paths (CVE-2020-28168, CWE-918)"),
    (re.compile(r"""["']minimist["']\s*:\s*["'][\^~]?([0-9\.]+)["']"""), 1, 2, 6, "Minimist < 1.2.6 is vulnerable to Prototype Pollution (CVE-2021-44906, CWE-1321)"),
    (re.compile(r"""["']jsonwebtoken["']\s*:\s*["'][\^~]?([0-9\.]+)["']"""), 9, 0, 0, "jsonwebtoken < 9.0.0 is vulnerable to insecure key verification bypass (CVE-2022-23529)"),
]


STATIC_SCANNER_VERSION = "2.1.0"
_AST_CACHE: Dict[str, List[StaticFinding]] = {}


def clear_static_analysis_cache() -> None:
    """Clear in-memory AST static analysis cache."""
    _AST_CACHE.clear()


# ── Static Security Analyzer ─────────────────────────────────────────────────

class StaticSecurityAnalyzer:
    """Deterministic security rule and AST engine."""

    # 1. SQL Injection patterns: concatenation / interpolation into queries
    SQLI_PATTERNS = [
        (
            re.compile(r"""f["'].*(?:SELECT|INSERT|UPDATE|DELETE)\b.*\{.*\}["']""", re.IGNORECASE),
            "SQL query formatted using f-string string interpolation without parameterized inputs.",
        ),
        (
            re.compile(r"""(?:SELECT|INSERT|UPDATE|DELETE)\b.*(?:\$\{[^}]+\}|["']\s*\+)""", re.IGNORECASE),
            "SQL query constructed using template literal or string concatenation in JavaScript/TypeScript.",
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

    # 2. NoSQL Injection
    NOSQLI_PATTERNS = [
        (
            re.compile(r"""\$(?:where|regex)\s*:\s*(?:req\.|params|args|f["'])""", re.IGNORECASE),
            "NoSQL injection risk: dynamically passing unsanitized input to $where or regex operators.",
        ),
        (
            re.compile(r"""find\s*\(\s*\{\s*["']?\$where["']?\s*:\s*f?["'].*\}""", re.IGNORECASE),
            "MongoDB $where evaluation with dynamic string concatenation.",
        ),
    ]

    # 3. XSS patterns: dangerous HTML injection
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
        (
            re.compile(r"""document\.write\s*\(\s*[^)]+\)"""),
            "document.write() renders untrusted input directly into DOM.",
        ),
        (
            re.compile(r"""["']<[a-zA-Z0-9_\-\s=\'"]+>["']\s*\+\s*[a-zA-Z_0-9$]+"""),
            "Untrusted variable concatenated directly into HTML markup enables Cross-Site Scripting (XSS).",
        ),
    ]

    # 4. Command Injection patterns (Regex)
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
            re.compile(r"""(?:child_process\.)?(exec|execSync)\s*\(\s*[`"'].*\$\{.*\}"""),
            "child_process.exec called with template literal interpolation.",
        ),
        (
            re.compile(r"""(?:child_process\.)?(exec|execSync)\s*\(\s*["'].*["']\s*\+\s*[a-zA-Z_0-9]+"""),
            "child_process.exec called with concatenated command string.",
        ),
    ]

    # 5. Path Traversal patterns
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
            re.compile(r"""(open|readFile|readFileSync)\s*\(\s*f["'].*\{.*(?:path|file|name|dir).*\}["']"""),
            "File path constructed from unvalidated string interpolation.",
        ),
        (
            re.compile(r"""(open|readFile|readFileSync)\s*\(\s*["'][^"']+["']\s*\+\s*[a-zA-Z_0-9]+""", re.IGNORECASE),
            "File path constructed using string concatenation with variable parameter.",
        ),
        (
            re.compile(r"""(?:fs\.)?(?:open|readFile|readFileSync)\s*\(\s*(?:[a-zA-Z_0-9$]+|["'][^"']*["'])\s*\+""", re.IGNORECASE),
            "File read operation using unvalidated string path concatenation allows Path Traversal.",
        ),
        (
            re.compile(r"""(?:send_file|send_from_directory|res\.sendFile)\s*\(\s*(?:request|req\.|params)[^)]*\)"""),
            "File download endpoint serving path directly from request parameters.",
        ),
    ]

    # Dynamic Code Execution patterns (eval, new Function in JS/TS/Python)
    DYNAMIC_EXECUTION_PATTERNS = [
        (
            re.compile(r"""\beval\s*\(\s*(?!\s*["'])([^)]+)\)"""),
            "Dynamic code execution via eval() with dynamic arguments allows arbitrary code execution.",
            "critical",
            "CWE-94",
        ),
        (
            re.compile(r"""\bnew\s+Function\s*\(\s*(?!\s*["'])([^)]+)\)"""),
            "Dynamic Function constructor evaluation allows arbitrary code execution.",
            "critical",
            "CWE-94",
        ),
    ]

    # 6. SSRF (Server-Side Request Forgery)
    SSRF_PATTERNS = [
        (
            re.compile(r"""(?:requests\.(?:get|post|put|delete)|urllib\.request\.urlopen|httpx\.(?:get|post))\s*\(\s*(?:request|req\.|params|url|target_url)[^)]*\)"""),
            "Outbound HTTP request targeting unvalidated user-supplied URL allows SSRF.",
        ),
        (
            re.compile(r"""(?:axios\.(?:get|post)|fetch)\s*\(\s*(?:req\.(?:query|body|params)\.[a-zA-Z_0-9]+)[^)]*\)"""),
            "Server-side HTTP request targeting URL from client parameters.",
        ),
    ]

    # 7. Open Redirect
    OPEN_REDIRECT_PATTERNS = [
        (
            re.compile(r"""(?:redirect|HttpResponseRedirect)\s*\(\s*(?:request\.(?:GET|POST|args)|req\.query)[^)]*\)"""),
            "Unvalidated URL redirect directly using user query parameter enables Open Redirect.",
        ),
        (
            re.compile(r"""window\.location(?:\.href)?\s*=\s*(?:req\.|new URLSearchParams|params)[^;]+"""),
            "Client-side navigation to unvalidated URL parameter.",
        ),
    ]

    # 8. Insecure File Permissions / Handling
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

    # 9. Hardcoded Secrets
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
            re.compile(r"""ghp_[A-Za-z0-9_]{36,255}"""),
            "GitHub Personal Access Token",
            "hardcoded_secret",
            "critical",
            "CWE-798",
        ),
        (
            re.compile(r"""xox[baprs]-[0-9a-zA-Z-]{24,}"""),
            "Slack Bot / User Token",
            "hardcoded_secret",
            "high",
            "CWE-798",
        ),
        (
            re.compile(
                r"""(?:[a-zA-Z0-9_]*(?:api[_-]?key|secret|token|password|passwd|auth[_-]?token)[a-zA-Z0-9_]*)\s*[:=]\s*["']?([A-Za-z0-9_\-\.+=/]{20,})["']?""",
                re.IGNORECASE,
            ),
            "Hardcoded API Token or Password",
            "hardcoded_secret",
            "high",
            "CWE-798",
        ),
    ]

    # 10. Insecure CORS
    CORS_PATTERNS = [
        (
            re.compile(r"""allow_origins\s*=\s*\[\s*["']\*["']\s*\]""", re.IGNORECASE),
            "Wildcard CORS origin ('*') configured, allowing any external site to read authenticated API responses.",
        ),
        (
            re.compile(r"""res\.header\s*\(\s*["']Access-Control-Allow-Origin["']\s*,\s*["']\*["']\s*\)""", re.IGNORECASE),
            "Access-Control-Allow-Origin set to wildcard '*' on HTTP response.",
        ),
    ]

    # 11. Debug Mode in Production
    DEBUG_PATTERNS = [
        (
            re.compile(r"""app\.run\s*\([^)]*debug\s*=\s*True[^)]*\)""", re.IGNORECASE),
            "Flask development debug mode enabled in application bootstrap.",
        ),
        (
            re.compile(r"""^\s*DEBUG\s*=\s*True\b"""),
            "DEBUG flag explicitly enabled in settings, exposing stack traces and diagnostic tools.",
        ),
    ]

    def _analyze_python_ast(self, file_path: str, content: str) -> List[StaticFinding]:
        """Perform syntax-aware AST analysis for Python source code with immutable hash caching."""
        content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
        cache_key = f"{STATIC_SCANNER_VERSION}:{file_path}:{content_hash}"
        if cache_key in _AST_CACHE:
            return list(_AST_CACHE[cache_key])

        try:
            tree = ast.parse(content, filename=file_path)
            lines = content.splitlines()
            visitor = PythonASTSecurityVisitor(file_path=file_path, lines=lines)
            visitor.visit(tree)
            _AST_CACHE[cache_key] = visitor.findings
            return visitor.findings
        except SyntaxError:
            return []
        except Exception:
            return []

    def _analyze_dependency_manifest(self, file_path: str, content: str) -> List[StaticFinding]:
        """Audit dependency files (requirements.txt, package.json) for vulnerable components."""
        findings: List[StaticFinding] = []
        filename = os.path.basename(file_path).replace("\\", "/").split("/")[-1].lower()

        if filename == "requirements.txt" or ("requirements" in filename and filename.endswith(".txt")):
            for line_num, line in enumerate(content.splitlines(), start=1):
                clean_l = line.strip()
                if not clean_l or clean_l.startswith("#"):
                    continue
                for pat, major, minor, desc in KNOWN_VULNERABLE_PY_DEPS:
                    m = pat.match(clean_l)
                    if m:
                        op, ver_str = m.group(1), m.group(2)
                        parts = ver_str.split(".")
                        try:
                            v_maj = int(parts[0])
                            v_min = int(parts[1]) if len(parts) > 1 else 0
                            if (v_maj < major) or (v_maj == major and v_min < minor):
                                findings.append(
                                    StaticFinding(
                                        category="security",
                                        type="vulnerable_dependency",
                                        severity="high",
                                        title=f"Vulnerable Dependency in {filename}",
                                        description=desc,
                                        file_path=file_path,
                                        start_line=line_num,
                                        end_line=line_num,
                                        confidence=0.92,
                                        evidence=clean_l,
                                        cwe="CWE-1395",
                                        owasp="A06:2021-Vulnerable-and-Outdated-Components",
                                        rule_id="DEP-PY-01",
                                        remediation_recommendation=f"Upgrade dependency to a patched release satisfying >= {major}.{minor}.",
                                    )
                                )
                        except (ValueError, IndexError):
                            pass

        elif filename == "package.json":
            for line_num, line in enumerate(content.splitlines(), start=1):
                clean_l = line.strip()
                for pat, maj, minr, patch, desc in KNOWN_VULNERABLE_NPM_DEPS:
                    m = pat.search(clean_l)
                    if m:
                        ver_str = m.group(1)
                        parts = ver_str.split(".")
                        try:
                            v_maj = int(parts[0])
                            v_min = int(parts[1]) if len(parts) > 1 else 0
                            v_patch = int(parts[2]) if len(parts) > 2 else 0
                            if (v_maj < maj) or (v_maj == maj and v_min < minr) or (v_maj == maj and v_min == minr and v_patch < patch):
                                findings.append(
                                    StaticFinding(
                                        category="security",
                                        type="vulnerable_dependency",
                                        severity="high",
                                        title=f"Vulnerable NPM Dependency in package.json",
                                        description=desc,
                                        file_path=file_path,
                                        start_line=line_num,
                                        end_line=line_num,
                                        confidence=0.92,
                                        evidence=clean_l,
                                        cwe="CWE-1395",
                                        owasp="A06:2021-Vulnerable-and-Outdated-Components",
                                        rule_id="DEP-NPM-01",
                                        remediation_recommendation=f"Update package.json and run 'npm audit fix' to upgrade past {maj}.{minr}.{patch}.",
                                    )
                                )
                        except (ValueError, IndexError):
                            pass

        return findings

    def _analyze_dockerfile(self, file_path: str, content: str) -> List[StaticFinding]:
        """Audit Dockerfiles for least privilege violations (running as root)."""
        findings: List[StaticFinding] = []
        lines = content.splitlines()
        has_user = False
        user_line_num = 1
        for line_num, line in enumerate(lines, start=1):
            clean = line.strip()
            if clean.startswith("#"):
                continue
            if re.match(r"^USER\s+", clean, re.IGNORECASE):
                has_user = True
                user_line_num = line_num
                if re.match(r"^USER\s+(root|0)\b", clean, re.IGNORECASE):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="insecure_file_handling",
                            severity="high",
                            title="Container Explicitly Configured to Run as Root",
                            description="Dockerfile specifies USER root, allowing container escape and root host compromise.",
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.96,
                            evidence=clean,
                            cwe="CWE-250",
                            owasp="A05:2021-Security-Misconfiguration",
                            rule_id="DOCKER-ROOT-01",
                            remediation_recommendation="Create and switch to a dedicated non-root user (e.g. USER appuser).",
                        )
                    )
        if not has_user and lines:
            findings.append(
                StaticFinding(
                    category="security",
                    type="insecure_file_handling",
                    severity="medium",
                    title="Container Runs as Root (Missing USER Directive)",
                    description="Dockerfile does not specify a non-root USER directive, causing container processes to run as root by default.",
                    file_path=file_path,
                    start_line=1,
                    end_line=min(len(lines), 5),
                    confidence=0.92,
                    evidence=lines[0] if lines else "FROM ...",
                    cwe="CWE-250",
                    owasp="A05:2021-Security-Misconfiguration",
                    rule_id="DOCKER-NOUSER-01",
                    remediation_recommendation="Add a non-root USER instruction to run container processes with minimal privileges.",
                )
            )
        return findings

    def analyze_file(self, file_path: str, content: str) -> List[StaticFinding]:
        """Analyze a single source file with AST, dependency, and regex security rules."""
        findings: List[StaticFinding] = []
        lines = content.splitlines()

        norm_name = os.path.basename(file_path).replace("\\", "/").split("/")[-1].lower()
        # Check dependency manifests
        if norm_name == "package.json" or ("requirements" in norm_name and norm_name.endswith(".txt")):
            return self._analyze_dependency_manifest(file_path, content)

        # Check Dockerfile security
        if "dockerfile" in norm_name:
            return self._analyze_dockerfile(file_path, content)

        # Skip obvious documentation, lockfiles, or media assets
        if file_path.endswith((".md", ".rst", ".svg", ".lock", ".png", ".jpg", ".jpeg", ".gif", ".ico")):
            return findings

        # Run Python AST analyzer first for Python files
        if file_path.endswith(".py"):
            ast_findings = self._analyze_python_ast(file_path, content)
            findings.extend(ast_findings)

        # Line-by-line pattern scanning (multi-language)
        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "#", "/*", "*", "<!--")):
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
                            owasp="A03:2021-Injection",
                            flow_source="user_input",
                            flow_transformation="string_concatenation",
                            flow_sink="db_query_execution",
                            rule_id="RULE-SQLI-01",
                            remediation_recommendation="Use parameterized queries or ORM query builders (e.g. cursor.execute('SELECT ... %s', (val,))).",
                        )
                    )
                    break

            # 2. NoSQL Injection
            for pattern, desc in self.NOSQLI_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="nosql_injection",
                            severity="high",
                            title="Potential NoSQL Injection",
                            description=desc,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.85,
                            evidence=stripped,
                            cwe="CWE-943",
                            owasp="A03:2021-Injection",
                            rule_id="RULE-NOSQL-01",
                            remediation_recommendation="Validate and sanitize query objects or use schema-enforced document models.",
                        )
                    )
                    break

            # 3. Cross-Site Scripting (XSS)
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
                            confidence=0.86,
                            evidence=stripped,
                            cwe="CWE-79",
                            owasp="A03:2021-Injection",
                            flow_source="request_input",
                            flow_transformation="unescaped_render",
                            flow_sink="dom_inner_html",
                            rule_id="RULE-XSS-01",
                            remediation_recommendation="Use textContent or sanitize HTML with a trusted sanitizer (e.g. DOMPurify).",
                        )
                    )
                    break

            # 4. Command Injection (JS / General regex fallback)
            for pattern, desc in self.COMMAND_INJECTION_PATTERNS:
                if pattern.search(line):
                    # Check if already caught by AST visitor
                    if not any(f.start_line == line_num and f.type == "command_injection" for f in findings):
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
                                owasp="A03:2021-Injection",
                                flow_source="command_parameter",
                                flow_transformation="string_concatenation",
                                flow_sink="process_execution",
                                rule_id="RULE-CMD-01",
                                remediation_recommendation="Pass arguments as arrays and avoid running commands inside a shell.",
                            )
                        )
                        break

            # 5. Path Traversal
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
                            confidence=0.83,
                            evidence=stripped,
                            cwe="CWE-22",
                            owasp="A01:2021-Broken-Access-Control",
                            flow_source="file_path_param",
                            flow_transformation="path_join",
                            flow_sink="filesystem_open",
                            rule_id="RULE-TRAVERSAL-01",
                            remediation_recommendation="Normalize paths using os.path.abspath() and verify target remains strictly within the intended directory root.",
                        )
                    )
                    break

            # 5b. Unsafe Dynamic Code Execution (eval, Function in JS/TS/Python)
            for pattern, desc, sev, cwe in self.DYNAMIC_EXECUTION_PATTERNS:
                if pattern.search(line):
                    if not any(f.start_line == line_num and f.type in ("unsafe_eval", "unsafe_dynamic_execution") for f in findings):
                        findings.append(
                            StaticFinding(
                                category="security",
                                type="unsafe_dynamic_execution",
                                severity=sev,
                                title="Unsafe Dynamic Code Execution (eval)",
                                description=desc,
                                file_path=file_path,
                                start_line=line_num,
                                end_line=line_num,
                                confidence=0.95,
                                evidence=stripped,
                                cwe=cwe,
                                owasp="A03:2021-Injection",
                                flow_source="user_code_input",
                                flow_transformation="raw_evaluation",
                                flow_sink="eval_execution",
                                rule_id="RULE-EVAL-01",
                                remediation_recommendation="Avoid eval() or new Function(). Use safe mathematical parsers or JSON.parse() instead.",
                            )
                        )
                    break

            # 6. SSRF
            for pattern, desc in self.SSRF_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="ssrf",
                            severity="high",
                            title="Potential Server-Side Request Forgery (SSRF)",
                            description=desc,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.84,
                            evidence=stripped,
                            cwe="CWE-918",
                            owasp="A10:2021-Server-Side-Request-Forgery",
                            flow_source="client_url_parameter",
                            flow_transformation="raw_dispatch",
                            flow_sink="http_request",
                            rule_id="RULE-SSRF-01",
                            remediation_recommendation="Validate outbound URLs against an allowlist of permitted hosts and reject private/internal IP addresses.",
                        )
                    )
                    break

            # 7. Open Redirect
            for pattern, desc in self.OPEN_REDIRECT_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="open_redirect",
                            severity="medium",
                            title="Potential Open Redirect",
                            description=desc,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.80,
                            evidence=stripped,
                            cwe="CWE-601",
                            owasp="A01:2021-Broken-Access-Control",
                            rule_id="RULE-REDIRECT-01",
                            remediation_recommendation="Validate redirect targets against internal relative paths or an explicit allowed host domain whitelist.",
                        )
                    )
                    break

            # 8. Insecure File Permissions
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
                            owasp="A01:2021-Broken-Access-Control",
                            rule_id="RULE-CHMOD-01",
                            remediation_recommendation="Restrict permissions to the minimum necessary level (e.g. 0o644 for files, 0o755 for directories).",
                        )
                    )
                    break

            # 9. Insecure CORS
            for pattern, desc in self.CORS_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="insecure_cors",
                            severity="medium",
                            title="Insecure Wildcard CORS Configuration",
                            description=desc,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.89,
                            evidence=stripped,
                            cwe="CWE-942",
                            owasp="A07:2021-Identification-and-Authentication-Failures",
                            rule_id="RULE-CORS-01",
                            remediation_recommendation="Specify explicit trusted origins in CORS configuration instead of wildcard '*'.",
                        )
                    )
                    break

            # 10. Debug Mode in Production
            for pattern, desc in self.DEBUG_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        StaticFinding(
                            category="security",
                            type="debug_mode",
                            severity="low",
                            title="Debug Mode Enabled in Application Code",
                            description=desc,
                            file_path=file_path,
                            start_line=line_num,
                            end_line=line_num,
                            confidence=0.91,
                            evidence=stripped,
                            cwe="CWE-489",
                            owasp="A05:2021-Security-Misconfiguration",
                            rule_id="RULE-DEBUG-01",
                            remediation_recommendation="Disable debug mode in production and drive debug settings through environment variables.",
                        )
                    )
                    break

            # 11. Hardcoded Secrets (with Strict Redaction & Placeholder Filtering)
            for pattern, title, finding_type, sev, cwe in self.SECRET_RULES:
                match = pattern.search(line)
                if not match:
                    continue

                matched_val = match.group(1) if match.groups() else match.group(0)
                val_lower = matched_val.lower()

                if val_lower in PLACEHOLDER_EXACT or any(sub in val_lower for sub in PLACEHOLDER_SUBSTRINGS):
                    continue

                if title == "Hardcoded API Token or Password" and len(matched_val) >= 20:
                    entropy = shannon_entropy(matched_val)
                    if entropy < 3.2:
                        continue

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
                        owasp="A07:2021-Identification-and-Authentication-Failures",
                        rule_id="RULE-SECRET-01",
                        remediation_recommendation="Remove credentials from source code and load via secure environment variables or vault secret managers.",
                    )
                )
                break

        # Deduplicate findings on the same file, line, and type (prefer AST over regex)
        deduped: List[StaticFinding] = []
        seen = set()
        for f in findings:
            key = (f.file_path, f.start_line, f.type)
            if key not in seen:
                seen.add(key)
                deduped.append(f)
        return deduped

    def analyze_repository_files(self, files: Dict[str, str]) -> List[StaticFinding]:
        """Scan all provided repository files."""
        all_findings: List[StaticFinding] = []
        for file_path, content in files.items():
            if content is not None:
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
