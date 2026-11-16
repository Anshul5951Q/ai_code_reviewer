"""
Comprehensive test suite for Sub-Phase 7.6:
Independent Verification Agent, Deterministic Re-Scanner, Gate 5 Decision Engine, and End-to-End Resolution Pipeline.

Enforces:
- Zero Blind Trust in LLM claims.
- 100% deterministic Gate 5 arbitration (7 mandatory conditions, 8 blocking rules).
- Confirmation bias mitigation: RemediationAgent rationale withheld from VerificationAgent.
- Source -> Transformation -> Sink data flow analysis.
- Deterministic Re-Scanner verifying static clearing without regressions.
- REST API verification history, Gate 5 audit telemetry, and defect resolution status.
"""
from __future__ import annotations

import inspect
import json
import urllib.request
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.decision_engine import Gate5DecisionEngine
from app.agents.verification import VerificationAgent
from app.analysis.rescan import DeterministicReScanner
from app.llm.provider import MockLLMProvider, OllamaProvider
from app.models.correlated_finding import CorrelatedFinding
from app.models.finding import Finding
from app.models.remediation_run import RemediationRun
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.models.verification_run import VerificationRun
from app.remediation.orchestrator import RemediationOrchestrator
from app.schemas.remediation import Gate4Status
from app.schemas.verification import (
    Gate5Decision,
    Gate5DecisionResult,
    ScannerComparisonResult,
    SourceTransformationSinkAssessment,
    VerificationOutcome,
)


def _is_ollama_online() -> bool:
    """Helper to check if local Ollama daemon is reachable on port 11434."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", headers={"User-Agent": "test"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


# ── 1. Deterministic Decision Engine (Gate 5) Tests ──────────────────────────

def test_gate5_decision_engine_resolved_when_all_conditions_pass():
    """All 7 mandatory conditions met -> Finding officially RESOLVED."""
    rescan = ScannerComparisonResult(
        pre_patch_findings_count=1,
        post_patch_findings_count=0,
        target_defect_cleared=True,
        cleared_findings=[{"id": "sqli-1", "title": "SQL Injection"}],
        new_findings=[],
    )

    result = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="FIXED",
        deterministic_rescan=rescan,
        syntax_valid=True,
        patch_version=1,
        expected_patch_version=1,
        snapshot_id="snap-1234",
        expected_snapshot_id="snap-1234",
        tests_passed=True,
        validation_available=True,
    )

    assert result.decision == Gate5Decision.RESOLVED.value
    assert result.is_resolved is True
    assert len(result.failed_conditions) == 0
    assert len(result.passed_conditions) >= 6
    assert any("officially RESOLVED" in r for r in result.reasons)


def test_gate5_decision_engine_blocked_on_gate4_failure():
    """Blocking Rule: Gate 4 failed -> BLOCKED even if Verification claims FIXED."""
    rescan = ScannerComparisonResult(target_defect_cleared=True, new_findings=[])
    result = Gate5DecisionEngine.evaluate(
        gate_4_status="FAILED",
        verification_outcome="FIXED",
        deterministic_rescan=rescan,
        syntax_valid=True,
        tests_passed=True,
    )

    assert result.decision == Gate5Decision.BLOCKED.value
    assert result.is_resolved is False
    assert any("Gate 4 patch validation check did not pass" in f for f in result.failed_conditions)
    assert any("Gate 4 patch verification rejected" in r for r in result.reasons)


def test_gate5_decision_engine_blocked_on_tests_failure():
    """Blocking Rule: Required test suite failed -> BLOCKED."""
    rescan = ScannerComparisonResult(target_defect_cleared=True, new_findings=[])
    result = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="FIXED",
        deterministic_rescan=rescan,
        syntax_valid=True,
        tests_passed=False,
        test_failure_details="2 test(s) failed: test_auth_token_expiry, test_login_csrf",
    )

    assert result.decision == Gate5Decision.BLOCKED.value
    assert result.is_resolved is False
    assert any("Test suite execution failed" in f for f in result.failed_conditions)
    assert any("Regression tests failed" in r for r in result.reasons)


def test_gate5_decision_engine_blocked_on_syntax_error():
    """Blocking Rule: AST SyntaxError -> BLOCKED."""
    result = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="FIXED",
        syntax_valid=False,
        tests_passed=True,
    )

    assert result.decision == Gate5Decision.BLOCKED.value
    assert result.is_resolved is False
    assert any("AST SyntaxError" in f for f in result.failed_conditions)


def test_gate5_decision_engine_blocked_on_regression_detected():
    """Blocking Rule: VerificationAgent flags REGRESSION_DETECTED -> BLOCKED."""
    result = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="REGRESSION_DETECTED",
        syntax_valid=True,
        tests_passed=True,
    )

    assert result.decision == Gate5Decision.BLOCKED.value
    assert result.is_resolved is False
    assert any("secondary defects or behavioral regressions" in r for r in result.reasons)


def test_gate5_decision_engine_blocked_on_new_static_signals():
    """Blocking Rule: Deterministic re-scanner flags newly introduced security findings -> BLOCKED."""
    rescan = ScannerComparisonResult(
        pre_patch_findings_count=1,
        post_patch_findings_count=1,
        target_defect_cleared=True,
        cleared_findings=[{"title": "SQL Injection"}],
        new_findings=[{"title": "Command Injection in subprocess.run(shell=True)"}],
    )
    result = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="FIXED",
        deterministic_rescan=rescan,
        syntax_valid=True,
        tests_passed=True,
    )

    assert result.decision == Gate5Decision.BLOCKED.value
    assert result.is_resolved is False
    assert any("new static signal(s) flagged" in f for f in result.failed_conditions)


def test_gate5_decision_engine_blocked_on_patch_version_mismatch():
    """Blocking Rule: Patch version evaluated (e.g. 2) does not match expected (1) -> BLOCKED."""
    result = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="FIXED",
        patch_version=2,
        expected_patch_version=1,
    )

    assert result.decision == Gate5Decision.BLOCKED.value
    assert result.is_resolved is False
    assert any("Patch version mismatch" in f for f in result.failed_conditions)


def test_gate5_decision_engine_blocked_on_snapshot_mismatch():
    """Blocking Rule: Snapshot hash mismatch -> BLOCKED."""
    result = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="FIXED",
        snapshot_id="snap-current-9999",
        expected_snapshot_id="snap-original-1111",
    )

    assert result.decision == Gate5Decision.BLOCKED.value
    assert result.is_resolved is False
    assert any("Snapshot identity mismatch" in f for f in result.failed_conditions)


def test_gate5_decision_engine_partially_resolved():
    """Outcome PARTIALLY_FIXED -> Gate 5 PARTIALLY_RESOLVED."""
    result = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="PARTIALLY_FIXED",
        syntax_valid=True,
        tests_passed=True,
    )

    assert result.decision == Gate5Decision.PARTIALLY_RESOLVED.value
    assert result.is_resolved is False
    assert any("PARTIALLY RESOLVED" in r for r in result.reasons)


def test_gate5_decision_engine_unresolved_on_not_fixed():
    """Outcome NOT_FIXED -> Gate 5 UNRESOLVED."""
    result = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="NOT_FIXED",
        syntax_valid=True,
        tests_passed=True,
    )

    assert result.decision == Gate5Decision.UNRESOLVED.value
    assert result.is_resolved is False
    assert any("remains exploitable" in r for r in result.reasons)


def test_gate5_decision_engine_unresolved_when_scanner_still_flags():
    """Even if Verification claims FIXED, if re-scanner detects defect remains -> UNRESOLVED."""
    rescan = ScannerComparisonResult(
        target_defect_cleared=False,
        retained_findings=[{"title": "SQL Injection"}],
    )
    result = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="FIXED",
        deterministic_rescan=rescan,
        syntax_valid=True,
        tests_passed=True,
    )

    assert result.decision == Gate5Decision.UNRESOLVED.value
    assert result.is_resolved is False
    assert any("target defect pattern remains" in f for f in result.failed_conditions)


def test_gate5_decision_engine_unable_to_verify():
    """Outcome UNABLE_TO_VERIFY or validation tool unavailable -> UNABLE_TO_VERIFY."""
    result1 = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="UNABLE_TO_VERIFY",
        syntax_valid=True,
    )
    assert result1.decision == Gate5Decision.UNABLE_TO_VERIFY.value

    result2 = Gate5DecisionEngine.evaluate(
        gate_4_status="PASSED",
        verification_outcome="FIXED",
        validation_available=False,
    )
    assert result2.decision == Gate5Decision.UNABLE_TO_VERIFY.value
    assert result2.limitations is not None


# ── 2. Deterministic Re-Scanner Tests ────────────────────────────────────────

def test_rescan_sqli_cleared_by_parameterization():
    """Original dynamic f-string query is flagged; parameterized replacement clears defect."""
    orig_code = (
        "import db\n"
        "def query_user(user_id):\n"
        "    cursor = db.get_cursor()\n"
        '    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        "    return cursor.fetchone()\n"
    )
    patched_code = (
        "import db\n"
        "def query_user(user_id):\n"
        "    cursor = db.get_cursor()\n"
        '    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))\n'
        "    return cursor.fetchone()\n"
    )

    scanner = DeterministicReScanner()
    rescan = scanner.rescan_file(
        file_path="src/api/users.py",
        original_content=orig_code,
        patched_content=patched_code,
        target_cwe="CWE-89",
        target_evidence='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
    )

    assert rescan.target_defect_cleared is True
    assert rescan.pre_patch_findings_count >= 1
    assert len(rescan.new_findings) == 0
    assert any("SQL" in str(f) or "CWE-89" in str(f) for f in rescan.cleared_findings)


def test_rescan_command_injection_cleared_vs_new_regression():
    """Patch eliminates os.system but introduces subprocess with shell=True -> retained finding detected."""
    orig_code = (
        "import os\n"
        "def ping(host):\n"
        '    os.system(f"ping -c 1 {host}")\n'
    )
    regressive_code = (
        "import subprocess\n"
        "def ping(host):\n"
        '    subprocess.run(f"ping -c 1 {host}", shell=True)\n'
    )

    scanner = DeterministicReScanner()
    rescan = scanner.rescan_file(
        file_path="src/utils.py",
        original_content=orig_code,
        patched_content=regressive_code,
        target_cwe="CWE-78",
        target_evidence='os.system(f"ping -c 1 {host}")',
    )

    # Defect pattern not cleared because shell=True retained the command injection vector
    assert rescan.target_defect_cleared is False
    assert len(rescan.retained_findings) >= 1
    assert any("CWE-78" in str(f) or "command_injection" in str(f) for f in rescan.retained_findings)


def test_rescan_new_regression_detected():
    """Patch fixes original SQL injection but introduces an entirely new vulnerability (CWE-78)."""
    orig_code = (
        "import db\n"
        "def get_user(uid):\n"
        '    cursor.execute(f"SELECT * FROM users WHERE id = {uid}")\n'
    )
    regressive_code = (
        "import db, os\n"
        "def get_user(uid):\n"
        '    cursor.execute("SELECT * FROM users WHERE id = %s", (uid,))\n'
        '    os.system(f"logger user_{uid}")\n'
    )

    scanner = DeterministicReScanner()
    rescan = scanner.rescan_file(
        file_path="src/users.py",
        original_content=orig_code,
        patched_content=regressive_code,
        target_cwe="CWE-89",
        target_evidence='cursor.execute(f"SELECT * FROM users WHERE id = {uid}")',
    )

    assert rescan.target_defect_cleared is True
    assert len(rescan.new_findings) >= 1
    assert any("CWE-78" in str(f) or "command_injection" in str(f) for f in rescan.new_findings)


def test_rescan_quality_resource_leak_cleared_with_context_manager():
    """Bare file open cleared with `with open(...)`."""
    orig_code = (
        "def read_data(path):\n"
        "    f = open(path)\n"
        "    return f.read()\n"
    )
    patched_code = (
        "def read_data(path):\n"
        "    with open(path) as f:\n"
        "        return f.read()\n"
    )

    scanner = DeterministicReScanner()
    rescan = scanner.rescan_file(
        file_path="src/io.py",
        original_content=orig_code,
        patched_content=patched_code,
        target_evidence="f = open(path)",
    )

    assert rescan.target_defect_cleared is True
    assert len(rescan.new_findings) == 0


def test_rescan_syntax_error_handling():
    """Syntax error in patched code is handled without crashing."""
    orig = "def foo():\n    return 1\n"
    broken = "def foo(:\n    return 1\n"

    scanner = DeterministicReScanner()
    rescan = scanner.rescan_file(
        file_path="foo.py",
        original_content=orig,
        patched_content=broken,
    )
    assert len(rescan.new_findings) >= 1
    assert rescan.new_findings[0]["type"] == "syntax_error"


# ── 3. Verification Agent & Confirmation Bias Safeguards ─────────────────────

def test_verification_agent_withholds_remediation_rationale():
    """
    Safeguard against confirmation bias:
    VerificationAgent prompt must withhold RemediationAgent strategy and explanation.
    """
    agent = VerificationAgent(llm_provider=MockLLMProvider())
    finding = Finding(
        id="f-secret",
        category="security",
        title="Hardcoded API Secret",
        file_path="src/config.py",
        evidence='API_KEY = "sk-live-1234567890"',
    )

    # Inspect signature of _build_prompt to ensure no plan parameter exists
    sig = inspect.signature(agent._build_prompt)
    assert "plan" not in sig.parameters
    assert "strategy" not in sig.parameters
    assert "explanation" not in sig.parameters

    prompt = agent._build_prompt(
        finding=finding,
        file_path="src/config.py",
        original_code='API_KEY = "sk-live-1234567890"',
        modified_code='import os\nAPI_KEY = os.environ.get("API_KEY")',
        unified_diff="--- a\n+++ b",
        static_signals=[],
    )

    # Remediation agent rationale MUST NOT appear in the prompt
    assert "Load secret from os.environ.get" not in prompt
    assert "Remediation Agent Rationale" not in prompt
    # Finding evidence and diff MUST appear
    assert "sk-live-1234567890" in prompt
    assert "Hardcoded API Secret" in prompt


@pytest.mark.asyncio
async def test_verification_agent_source_transformation_sink_parsing():
    """VerificationAgent evaluates untrusted input source, transformation, and sink."""
    agent = VerificationAgent(llm_provider=MockLLMProvider())
    finding = Finding(
        id="f-xss",
        category="security",
        cwe="CWE-79",
        title="Cross-Site Scripting (XSS)",
        file_path="src/views.py",
        evidence="return f'<div>{user_input}</div>'",
    )

    report = await agent.verify(
        finding=finding,
        file_path="src/views.py",
        original_code="return f'<div>{user_input}</div>'",
        modified_code="import html\nreturn f'<div>{html.escape(user_input)}</div>'",
        unified_diff="--- a\n+++ b",
        syntax_valid=True,
    )

    assert report.outcome == VerificationOutcome.FIXED.value
    assert report.confidence >= 0.90
    assert report.source_transformation_sink is not None
    assert report.source_transformation_sink.is_exploitable_path_severed is True
    assert report.status == "resolved"


# ── 4. Remediation Orchestrator + Gate 5 End-to-End Pipeline ─────────────────

@pytest.mark.asyncio
async def test_orchestrator_successful_gate5_resolution(
    db_session: AsyncSession,
):
    """
    End-to-End test:
    RemediationRun executes Gate 4 (PASS) -> DeterministicReScanner (CLEARED) ->
    VerificationAgent (FIXED) -> Gate 5 DecisionEngine (RESOLVED).
    VerificationRun is persisted, finding status updated to 'resolved', run gate_5_decision 'RESOLVED'.
    """
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    review = Review(
        id=review_id,
        repository_id="repo-gate5-test",
        commit_sha="c12345",
        branch="main",
        status="completed",
    )
    finding = Finding(
        id=finding_id,
        review_id=review_id,
        category="security",
        severity="high",
        cwe="CWE-89",
        title="SQL Injection Vulnerability",
        file_path="src/api/users.py",
        start_line=20,
        end_line=24,
        evidence='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        status="open",
    )
    snapshot = RepositorySnapshot(
        review_id=review_id,
        commit_sha="c12345",
        branch="main",
        languages=json.dumps({"primary": {"name": "Python"}}),
    )
    run = RemediationRun(
        id=run_id,
        review_id=review_id,
        finding_id=finding_id,
        status="queued",
    )

    db_session.add_all([review, finding, snapshot, run])
    await db_session.commit()

    snapshot_code = {
        "src/api/users.py": (
            "import db\n\n"
            "def get_user(user_id):\n"
            "    cursor = db.get_cursor()\n"
            '    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
            "    return cursor.fetchone()\n"
        )
    }

    maker = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    mock_llm = MockLLMProvider()
    orchestrator = RemediationOrchestrator(llm_provider=mock_llm)

    completed_run = await orchestrator.run(
        run_id,
        session_maker=maker,
        provided_files=snapshot_code,
    )

    assert completed_run.status == "completed"
    assert completed_run.gate_4_status == "PASSED"
    assert completed_run.gate_5_decision == Gate5Decision.RESOLVED.value
    assert completed_run.verification_status == "resolved"

    # Verify Finding updated in DB
    await db_session.refresh(finding)
    assert finding.status == "resolved"

    # Verify VerificationRun persisted in DB
    v_res = await db_session.execute(
        select(VerificationRun).where(VerificationRun.remediation_run_id == run_id)
    )
    v_run = v_res.scalar_one_or_none()
    assert v_run is not None
    assert v_run.outcome == VerificationOutcome.FIXED.value
    assert v_run.gate_5_decision == Gate5Decision.RESOLVED.value
    assert v_run.patch_version == 1
    assert v_run.methodology == "source_transformation_sink"
    assert v_run.source_transformation_sink_json is not None


@pytest.mark.asyncio
async def test_orchestrator_gate4_passed_but_gate5_blocked_on_simulated_regression(
    db_session: AsyncSession,
):
    """
    Edge case:
    Gate 4 passes basic diff checks, but independent verification discovers regression.
    Gate 5 issues BLOCKED, finding status remains 'open'.
    """
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    review = Review(id=review_id, repository_id="repo-reg", commit_sha="c22", branch="main", status="completed")
    # Finding title contains simulation keyword 'simulate_regression' to trigger regression in MockLLM
    finding = Finding(
        id=finding_id,
        review_id=review_id,
        category="security",
        severity="high",
        title="Query flaw simulate_regression check",
        file_path="src/db.py",
        start_line=10,
        end_line=12,
        evidence="query = data",
        status="open",
    )
    snapshot = RepositorySnapshot(
        review_id=review_id,
        commit_sha="c22",
        branch="main",
        languages=json.dumps({"primary": {"name": "Python"}}),
    )
    run = RemediationRun(
        id=run_id,
        review_id=review_id,
        finding_id=finding_id,
        status="queued",
    )

    db_session.add_all([review, finding, snapshot, run])
    await db_session.commit()

    code = {"src/db.py": "def run_query(data):\n    return data\n"}
    maker = async_sessionmaker(bind=db_session.bind, expire_on_commit=False, class_=AsyncSession)
    mock_llm = MockLLMProvider()
    orchestrator = RemediationOrchestrator(llm_provider=mock_llm)

    completed_run = await orchestrator.run(run_id, session_maker=maker, provided_files=code)

    assert completed_run.gate_5_decision == Gate5Decision.BLOCKED.value
    # Finding must NOT be marked resolved; state reflects verification_failed
    await db_session.refresh(finding)
    assert finding.status == "verification_failed"
    assert finding.status != "resolved"

    # Verification run recorded as REGRESSION_DETECTED
    v_res = await db_session.execute(
        select(VerificationRun).where(VerificationRun.remediation_run_id == run_id)
    )
    v_run = v_res.scalar_one_or_none()
    assert v_run is not None
    assert v_run.outcome == VerificationOutcome.REGRESSION_DETECTED.value
    assert v_run.gate_5_decision == Gate5Decision.BLOCKED.value


# ── 5. REST API Endpoints Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_remediation_gate5_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """GET /remediations/{id}/gate-5 returns full Gate 5 audit report."""
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    review = Review(id=review_id, repository_id="r1", commit_sha="c1", branch="m", status="completed")
    finding = Finding(id=finding_id, review_id=review_id, category="security", severity="high", title="SQLi", file_path="src/db.py", status="resolved")
    run = RemediationRun(
        id=run_id,
        review_id=review_id,
        finding_id=finding_id,
        status="completed",
        gate_4_status="PASSED",
        gate_5_decision="RESOLVED",
        patch_version=1,
    )
    v_run = VerificationRun(
        id=str(uuid.uuid4()),
        review_id=review_id,
        remediation_run_id=run_id,
        finding_id=finding_id,
        patch_version=1,
        status="completed",
        outcome="FIXED",
        gate_5_decision="RESOLVED",
        confidence=0.95,
        decision_reasons_json=json.dumps(["All 7 conditions satisfied"]),
        failed_conditions_json=json.dumps([]),
    )
    db_session.add_all([review, finding, run, v_run])
    await db_session.commit()

    resp = await client.get(f"/api/remediations/{run_id}/gate-5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "RESOLVED"
    assert data["is_resolved"] is True
    assert data["patch_version"] == 1
    assert "All 7 conditions satisfied" in data["reasons"]


@pytest.mark.asyncio
async def test_get_remediation_verification_history_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """GET /remediations/{id}/verification-history returns chronological audits."""
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    review = Review(id=review_id, repository_id="r1", commit_sha="c1", branch="m", status="completed")
    finding = Finding(id=finding_id, review_id=review_id, category="security", severity="high", title="SQLi", file_path="src/db.py", status="open")
    run = RemediationRun(id=run_id, review_id=review_id, finding_id=finding_id, status="completed")
    
    v1 = VerificationRun(
        id=str(uuid.uuid4()),
        review_id=review_id,
        remediation_run_id=run_id,
        finding_id=finding_id,
        patch_version=1,
        outcome="NOT_FIXED",
        gate_5_decision="UNRESOLVED",
    )
    v2 = VerificationRun(
        id=str(uuid.uuid4()),
        review_id=review_id,
        remediation_run_id=run_id,
        finding_id=finding_id,
        patch_version=2,
        outcome="FIXED",
        gate_5_decision="RESOLVED",
    )
    db_session.add_all([review, finding, run, v1, v2])
    await db_session.commit()

    resp = await client.get(f"/api/remediations/{run_id}/verification-history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_runs"] == 2
    assert len(data["runs"]) == 2
    assert data["runs"][0]["patch_version"] == 1
    assert data["runs"][1]["patch_version"] == 2


@pytest.mark.asyncio
async def test_get_finding_resolution_status_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """GET /findings/{id}/resolution-status returns composite status and gate outputs."""
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    review = Review(id=review_id, repository_id="r1", commit_sha="c1", branch="m", status="completed")
    finding = Finding(
        id=finding_id,
        review_id=review_id,
        category="security",
        severity="high",
        title="Command Injection",
        file_path="src/cmd.py",
        status="resolved",
    )
    run = RemediationRun(
        id=run_id,
        review_id=review_id,
        finding_id=finding_id,
        status="completed",
        gate_4_status="PASSED",
        gate_5_decision="RESOLVED",
        patch_version=1,
    )
    db_session.add_all([review, finding, run])
    await db_session.commit()

    resp = await client.get(f"/api/findings/{finding_id}/resolution-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["finding_id"] == finding_id
    assert data["finding_status"] == "resolved"
    assert data["is_resolved"] is True
    assert data["gate_4_status"] == "PASSED"
    assert data["gate_5_decision"] == "RESOLVED"
    assert data["patch_version"] == 1


# ── 6. Live Ollama Verification Inference Test ───────────────────────────────

@pytest.mark.asyncio
@pytest.mark.skipif(not _is_ollama_online(), reason="Local Ollama not reachable on localhost:11434")
async def test_live_ollama_verification_inference():
    """
    Verify live inference on local Ollama service (qwen2.5-coder:7b).
    Tests Source -> Transformation -> Sink evaluation and structured JSON extraction.
    """
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5-coder:7b", timeout=60.0)
    agent = VerificationAgent(llm_provider=provider)
    finding = Finding(
        id="f-live-sqli",
        category="security",
        cwe="CWE-89",
        severity="high",
        title="SQL Injection in User Profile Lookup",
        file_path="api/profile.py",
        start_line=12,
        evidence='cursor.execute(f"SELECT bio FROM profiles WHERE user_id = \'{uid}\'")',
        description="String interpolation allows SQL injection.",
    )

    orig_code = (
        "import db\n"
        "def get_user_bio(uid):\n"
        "    cursor = db.get_cursor()\n"
        '    cursor.execute(f"SELECT bio FROM profiles WHERE user_id = \'{uid}\'")\n'
        "    return cursor.fetchone()\n"
    )

    patched_code = (
        "import db\n"
        "def get_user_bio(uid):\n"
        "    cursor = db.get_cursor()\n"
        '    cursor.execute("SELECT bio FROM profiles WHERE user_id = %s", (uid,))\n'
        "    return cursor.fetchone()\n"
    )

    diff = (
        "--- a/api/profile.py\n"
        "+++ b/api/profile.py\n"
        "@@ -4,2 +4,2 @@\n"
        "-    cursor.execute(f\"SELECT bio FROM profiles WHERE user_id = '{uid}'\")\n"
        "+    cursor.execute(\"SELECT bio FROM profiles WHERE user_id = %s\", (uid,))\n"
    )

    report = await agent.verify(
        finding=finding,
        file_path="api/profile.py",
        original_code=orig_code,
        modified_code=patched_code,
        unified_diff=diff,
        syntax_valid=True,
    )

    assert report.outcome in (VerificationOutcome.FIXED.value, VerificationOutcome.PARTIALLY_FIXED.value)
    assert report.confidence >= 0.70
    assert report.reason is not None and len(report.reason) > 10
    if report.source_transformation_sink:
        assert report.source_transformation_sink.is_exploitable_path_severed is True
