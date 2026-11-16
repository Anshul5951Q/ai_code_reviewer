"""
Unit tests for SecurityDetectionAgent and deterministic security rules.
"""
from __future__ import annotations

import pytest

from app.agents.base import AnalysisContext
from app.agents.security_detection import SecurityDetectionAgent
from app.analysis.chunker import FileChunk
from app.analysis.static_analysis import StaticSecurityAnalyzer
from app.llm.provider import MockLLMProvider


# ── Vulnerability Fixtures ────────────────────────────────────────────────────

SQLI_CODE = """
def get_user_profile(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchall()
"""

XSS_CODE = """
function renderGreeting(name) {
    document.getElementById("welcome").innerHTML = "<h1>Hello, " + name + "</h1>";
}
"""

COMMAND_INJECTION_CODE = """
import os
def ping_server(host):
    os.system(f"ping -c 1 {host}")
"""

PATH_TRAVERSAL_CODE = """
import os
def read_log_file(filename):
    path = os.path.join("/var/log/app", filename)
    with open(path, "r") as f:
        return f.read()
"""

SECRET_CODE = """
# Production AWS keys
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
"""

WEAK_AUTH_CODE = """
def verify_admin_request(headers):
    # Weak authentication: trust arbitrary debug header
    if headers.get("X-Debug-Admin") == "true":
        return True
    return False
"""

INSECURE_FILE_CODE = """
import os
def save_uploaded_script(filename, content):
    with open(f"/tmp/{filename}", "w") as f:
        f.write(content)
    os.chmod(f"/tmp/{filename}", 0o777)
"""


# ── Tests for Deterministic Static Scanner ────────────────────────────────────

def test_static_sqli_detection():
    analyzer = StaticSecurityAnalyzer()
    findings = analyzer.analyze_file("src/db.py", SQLI_CODE)
    sqli = [f for f in findings if "sql" in f.type.lower() or f.cwe == "CWE-89"]
    assert len(sqli) >= 1
    assert sqli[0].cwe == "CWE-89"
    assert sqli[0].severity in ("critical", "high")


def test_static_xss_detection():
    analyzer = StaticSecurityAnalyzer()
    findings = analyzer.analyze_file("src/render.js", XSS_CODE)
    xss = [f for f in findings if "xss" in f.type.lower() or f.cwe == "CWE-79"]
    assert len(xss) >= 1
    assert xss[0].cwe == "CWE-79"


def test_static_command_injection_detection():
    analyzer = StaticSecurityAnalyzer()
    findings = analyzer.analyze_file("src/net.py", COMMAND_INJECTION_CODE)
    cmdi = [f for f in findings if "command" in f.type.lower() or f.cwe == "CWE-78"]
    assert len(cmdi) >= 1
    assert cmdi[0].cwe == "CWE-78"


def test_static_secret_detection_and_redaction():
    analyzer = StaticSecurityAnalyzer()
    findings = analyzer.analyze_file("src/config.py", SECRET_CODE)
    secrets = [f for f in findings if f.cwe == "CWE-798" or "secret" in f.type.lower()]
    assert len(secrets) >= 1
    # Raw AWS key must NEVER appear unmasked in evidence
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in secrets[0].evidence
    assert "*" in secrets[0].evidence


# ── Tests for SecurityDetectionAgent ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_security_detection_agent_execution():
    provider = MockLLMProvider()
    agent = SecurityDetectionAgent(provider=provider)

    files = {
        "src/db.py": SQLI_CODE,
        "src/render.js": XSS_CODE,
        "src/net.py": COMMAND_INJECTION_CODE,
    }
    chunks = [
        FileChunk(file_path="src/db.py", start_line=1, end_line=6, chunk_index=0, content=SQLI_CODE, total_lines=6),
        FileChunk(file_path="src/render.js", start_line=1, end_line=5, chunk_index=0, content=XSS_CODE, total_lines=5),
    ]

    context = AnalysisContext(
        review_id="rev-s1",
        repository_id="repo-1",
        repository_name="test-org/sec-repo",
        commit_sha="abcdef123456",
        branch="main",
        agent_type="security_agent",
        languages={"python": {"files": 2, "percentage": 66.0}, "javascript": {"files": 1, "percentage": 34.0}},
        frameworks=["FastAPI"],
        dependencies=[],
        structure={"entry_points": []},
        statistics={"total_files": 3, "total_lines": 30},
        file_tree=list(files.keys()),
        selected_files=files,
        chunks=chunks,
    )

    result = await agent.analyze(context)
    assert result.status == "completed"
    assert result.agent_type == "security_agent"
    assert len(result.findings) >= 1

    # Findings must have valid security properties
    for f in result.findings:
        assert f.category == "security"
        assert f.cwe is not None
        assert f.confidence >= 0.70
        assert f.evidence is not None


@pytest.mark.asyncio
async def test_security_detection_agent_anti_cve_rule():
    class CVEInventingProvider(MockLLMProvider):
        async def structured_output(self, prompt, schema_class, system=None, options=None):
            from app.agents.security_detection import RawSecurityDetectionFinding, SecurityDetectionOutput
            return SecurityDetectionOutput(
                findings=[
                    RawSecurityDetectionFinding(
                        finding_id="fake-cve-1",
                        category="security",
                        type="sql_injection",
                        severity="high",
                        title="Critical CVE-2026-99999 Injection",
                        description="Exploitable via synthetic CVE-2026-99999 vulnerability.",
                        file_path="src/db.py",
                        start_line=2,
                        end_line=4,
                        evidence='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
                        cwe="CWE-89",
                    )
                ]
            )

    agent = SecurityDetectionAgent(provider=CVEInventingProvider())
    files = {"src/db.py": SQLI_CODE}
    context = AnalysisContext(
        review_id="rev-s2",
        repository_id="repo-1",
        repository_name="test-org/sec-repo",
        commit_sha="abcdef123456",
        branch="main",
        agent_type="security_agent",
        languages={"python": {"files": 1, "percentage": 100.0}},
        frameworks=["FastAPI"],
        dependencies=[],
        structure={"entry_points": []},
        statistics={"total_files": 1, "total_lines": 10},
        file_tree=["src/db.py"],
        selected_files=files,
        chunks=[],
    )

    result = await agent.analyze(context)
    assert result.status == "completed"
    finding = result.findings[0]
    # Synthetic CVE must be scrubbed
    assert "CVE-2026-99999" not in finding.title
    assert "CVE-2026-99999" not in finding.description

