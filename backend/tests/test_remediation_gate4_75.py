"""
Comprehensive test suite for Sub-Phase 7.5:
Remediation Agent, Patch Generator, Deterministic Patch Risk Assessment, and Gate 4 Patch Verification Gate.

Zero Blind Trust:
- Gate 4 verifies diff formatting, workspace isolation, patch applicability, AST syntax, static clearing, and regression absence.
- Deterministic risk assessment objectively scores patch blast radius without relying on LLM claims.
- Remediation agent incorporates root-cause and correlated cluster context.
- Dedicated REST API endpoints are exercised with full persistence checks.
"""
from __future__ import annotations

import json
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.remediation import RemediationAgent
from app.agents.verification_gates import PatchVerificationGate
from app.analysis.patch_risk import calculate_patch_risk
from app.llm.provider import MockLLMProvider, OllamaProvider
from app.models.correlated_finding import CorrelatedFinding
from app.models.finding import Finding
from app.models.finding_relationship import FindingRelationship
from app.models.remediation_run import RemediationRun
from app.models.repository_snapshot import RepositorySnapshot
from app.models.review import Review
from app.remediation.context_builder import build_remediation_context
from app.remediation.patch_generator import PatchGenerator, PatchValidationError
from app.schemas.remediation import Gate4Status, PatchRiskLevel


# ── 1. Deterministic Patch Risk Engine Tests ─────────────────────────────────

def test_patch_risk_low():
    """Single file, compact diff, non-security category -> LOW risk."""
    diff = "--- a/utils.py\n+++ b/utils.py\n@@ -2,2 +2,2 @@\n-    return False\n+    return True\n"
    assessment = calculate_patch_risk(
        files_changed=["src/utils.py"],
        diff=diff,
        category="quality",
        finding_title="Improve boolean logic",
    )
    assert assessment.level == PatchRiskLevel.LOW.value
    assert assessment.score < 0.25
    assert "Single-file localized change" in assessment.factors
    assert "Compact diff scope: 2 lines changed" in assessment.factors


def test_patch_risk_medium():
    """Single file, compact diff, but high-impact security CWE-89 -> MEDIUM risk."""
    diff = "--- a/db.py\n+++ b/db.py\n@@ -1,2 +1,2 @@\n-cursor.execute(f'SELECT {x}')\n+cursor.execute('SELECT %s', (x,))\n"
    assessment = calculate_patch_risk(
        files_changed=["src/db.py"],
        diff=diff,
        category="security",
        cwe="CWE-89",
        finding_title="SQL Injection",
    )
    assert assessment.level == PatchRiskLevel.MEDIUM.value
    assert 0.25 <= assessment.score < 0.45
    assert "High-impact vulnerability class: CWE-89" in assessment.factors


def test_patch_risk_high():
    """Multi-file modification + security CWE -> HIGH risk."""
    diff = "--- a/db.py\n+++ b/db.py\n@@ -1,2 +1,2 @@\n-x = 1\n+x = 2\n"
    assessment = calculate_patch_risk(
        files_changed=["src/db.py", "src/auth.py"],
        diff=diff,
        category="security",
        cwe="CWE-798",
        finding_title="Hardcoded Secret Key",
    )
    assert assessment.level in (PatchRiskLevel.HIGH.value, PatchRiskLevel.CRITICAL.value)
    assert assessment.score >= 0.45
    assert any("Multi-file" in f for f in assessment.factors)


def test_patch_risk_critical():
    """Multi-file (>3), critical configuration file, large diff scope -> CRITICAL risk."""
    lines_added = "\n".join(f"+line_{i} = True" for i in range(85))
    diff = f"--- a/settings.py\n+++ b/settings.py\n@@ -1,1 +1,86 @@\n-line_0 = False\n{lines_added}\n"
    assessment = calculate_patch_risk(
        files_changed=["backend/app/core/settings.py", "auth/jwt.py", "models/user.py", "alembic/env.py"],
        diff=diff,
        category="security",
        cwe="CWE-287",
        finding_title="Authentication Bypass in Settings",
    )
    assert assessment.level == PatchRiskLevel.CRITICAL.value
    assert assessment.score >= 0.70
    assert any("critical configuration" in f for f in assessment.factors)
    assert any("Large diff scope" in f for f in assessment.factors)


def test_patch_risk_function_signature_alteration():
    """Altering public function signature adds interface modification factor."""
    diff = (
        "--- a/service.py\n+++ b/service.py\n"
        "@@ -10,2 +10,2 @@\n"
        "-def process_order(order_id: int):\n"
        "+def process_order(order_id: int, user_context: dict = None):\n"
        "     pass\n"
    )
    assessment = calculate_patch_risk(
        files_changed=["src/service.py"],
        diff=diff,
        category="quality",
        finding_title="Add user context to order processing",
    )
    assert "Modifies public function or method signature" in assessment.factors


# ── 2. Gate 4 (PatchVerificationGate) Itemized Verification Tests ─────────────

def test_gate4_passes_clean_patch():
    """Clean diff, safe workspace, valid python syntax, vulnerability cleared -> PASSED."""
    gate = PatchVerificationGate()
    target_file = "src/db.py"
    orig_code = (
        "import db\n"
        "def query_user(user_id):\n"
        "    cursor = db.get_cursor()\n"
        '    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        "    return cursor.fetchone()\n"
    )
    diff = (
        "--- a/src/db.py\n"
        "+++ b/src/db.py\n"
        "@@ -4,1 +4,1 @@\n"
        '-    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        '+    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))\n'
    )

    report = gate.verify_patch(
        patch_diff=diff,
        target_file=target_file,
        file_contents={target_file: orig_code},
        cwe="CWE-89",
        finding_type="sql_injection",
    )

    assert report.gate_status == Gate4Status.PASSED.value
    assert report.syntax_valid is True
    assert report.static_finding_cleared is True
    assert len(report.new_issues_detected) == 0

    check_names = [c.check_name for c in report.checks]
    assert "diff_validation" in check_names
    assert "workspace_safety" in check_names
    assert "patch_applicability" in check_names
    assert "syntax_validation" in check_names
    assert "static_validation" in check_names
    assert "regression_safety" in check_names


def test_gate4_rejects_malformed_diff():
    """Malformed diff lacking unified diff header -> FAILED at diff_validation."""
    gate = PatchVerificationGate()
    target_file = "src/calc.py"
    orig_code = "def add(a, b):\n    return a + b\n"
    malformed_diff = "Just replace line 2 with return a * b please."

    report = gate.verify_patch(
        patch_diff=malformed_diff,
        target_file=target_file,
        file_contents={target_file: orig_code},
    )

    assert report.gate_status == Gate4Status.FAILED.value
    diff_check = next(c for c in report.checks if c.check_name == "diff_validation")
    assert diff_check.status == "failed"
    assert "malformed" in diff_check.details.lower()


def test_gate4_rejects_protected_files():
    """Targeting protected secret files (.env, id_rsa, .pem) -> FAILED at workspace_safety."""
    gate = PatchVerificationGate()
    target_file = ".env"
    diff = "--- a/.env\n+++ b/.env\n@@ -1,1 +1,1 @@\n-KEY=1\n+KEY=2\n"

    report = gate.verify_patch(
        patch_diff=diff,
        target_file=target_file,
        file_contents={target_file: "KEY=1\n"},
    )

    assert report.gate_status == Gate4Status.FAILED.value
    ws_check = next(c for c in report.checks if c.check_name == "workspace_safety")
    assert ws_check.status == "failed"
    assert "protected" in ws_check.details.lower()


def test_gate4_rejects_python_syntax_error():
    """Patch producing invalid Python syntax (e.g. unclosed parenthesis) -> FAILED at syntax_validation."""
    gate = PatchVerificationGate()
    target_file = "src/api.py"
    orig_code = "def get_data():\n    return {'status': 'ok'}\n"
    broken_diff = (
        "--- a/src/api.py\n"
        "+++ b/src/api.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def get_data():\n"
        "-    return {'status': 'ok'}\n"
        "+    return {'status': (broken_syntax\n"
    )

    report = gate.verify_patch(
        patch_diff=broken_diff,
        target_file=target_file,
        file_contents={target_file: orig_code},
    )

    assert report.gate_status == Gate4Status.FAILED.value
    assert report.syntax_valid is False
    syntax_check = next(c for c in report.checks if c.check_name == "syntax_validation")
    assert syntax_check.status == "failed"
    assert "syntaxerror" in syntax_check.details.lower() or "ast" in syntax_check.details.lower()


def test_gate4_rejects_unbalanced_javascript_syntax():
    """Patch on JS/TS file with unbalanced braces -> FAILED at syntax_validation."""
    gate = PatchVerificationGate()
    target_file = "src/component.tsx"
    orig_code = "export function Button() { return <button>Click</button>; }"
    broken_diff = (
        "--- a/src/component.tsx\n"
        "+++ b/src/component.tsx\n"
        "@@ -1,1 +1,1 @@\n"
        "-export function Button() { return <button>Click</button>; }\n"
        "+export function Button() { return <button>Click</button>; \n"
    )

    report = gate.verify_patch(
        patch_diff=broken_diff,
        target_file=target_file,
        file_contents={target_file: orig_code},
    )

    assert report.gate_status == Gate4Status.FAILED.value
    assert report.syntax_valid is False
    syntax_check = next(c for c in report.checks if c.check_name == "syntax_validation")
    assert syntax_check.status == "failed"
    assert "Unbalanced braces" in syntax_check.details


def test_gate4_rejects_still_vulnerable_code():
    """Patch that fails to clear the security rule (CWE-89) -> FAILED at static_validation."""
    gate = PatchVerificationGate()
    target_file = "src/db.py"
    orig_code = (
        "import db\n"
        "def query_user(user_id):\n"
        "    cursor = db.get_cursor()\n"
        '    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        "    return cursor.fetchone()\n"
    )
    # Flawed patch: changes formatting but keeps f-string interpolation!
    ineffective_diff = (
        "--- a/src/db.py\n"
        "+++ b/src/db.py\n"
        "@@ -4,1 +4,1 @@\n"
        '-    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        '+    cursor.execute(f"/* query */ SELECT * FROM users WHERE id = {user_id}")\n'
    )

    report = gate.verify_patch(
        patch_diff=ineffective_diff,
        target_file=target_file,
        file_contents={target_file: orig_code},
        cwe="CWE-89",
        finding_type="sql_injection",
    )

    assert report.gate_status == Gate4Status.FAILED.value
    assert report.static_finding_cleared is False
    static_check = next(c for c in report.checks if c.check_name == "static_validation")
    assert static_check.status == "failed"
    assert "still detected" in static_check.details


def test_gate4_rejects_regression_introduction():
    """Patch introducing a new vulnerability signal (e.g. hardcoded AWS secret) -> FAILED at regression_safety."""
    gate = PatchVerificationGate()
    target_file = "src/service.py"
    orig_code = (
        "def compute(a, b):\n"
        "    return a + b\n"
    )
    # Patch fixes compute but introduces hardcoded AWS credentials!
    regressive_diff = (
        "--- a/src/service.py\n"
        "+++ b/src/service.py\n"
        "@@ -1,2 +1,3 @@\n"
        "+AWS_SECRET = 'AKIA1234567890ABCDEF'\n"
        " def compute(a, b):\n"
        "     return a + b\n"
    )

    report = gate.verify_patch(
        patch_diff=regressive_diff,
        target_file=target_file,
        file_contents={target_file: orig_code},
    )

    assert report.gate_status == Gate4Status.FAILED.value
    assert len(report.new_issues_detected) > 0
    reg_check = next(c for c in report.checks if c.check_name == "regression_safety")
    assert reg_check.status == "failed"
    assert "introduced new potential vulnerability" in reg_check.details


# ── 3. RemediationAgent with Correlated Cluster & Root Cause ─────────────────

@pytest.mark.asyncio
async def test_remediation_agent_with_correlated_cluster():
    """RemediationAgent incorporates root-cause intelligence and cluster context."""
    finding = Finding(
        id="f-primary",
        review_id="rev-75",
        category="security",
        severity="high",
        title="SQL Injection in User Lookup",
        file_path="src/api/users.py",
        start_line=25,
        end_line=28,
        cwe="CWE-89",
        evidence='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        description="Dynamic SQL query allows injection.",
    )

    file_content = (
        "import db\n\n"
        "def get_user(user_id):\n"
        "    cursor = db.get_cursor()\n"
        '    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        "    return cursor.fetchone()\n"
    )

    constituent_findings = [
        {
            "id": "f-secondary",
            "title": "Unvalidated Input in User ID",
            "category": "quality",
            "severity": "medium",
            "file_path": "src/api/users.py",
            "start_line": 23,
            "source": "quality_agent",
        }
    ]

    ctx = build_remediation_context(
        finding=finding,
        file_content=file_content,
        repository_name="test-repo",
        languages={"primary": {"name": "Python"}},
        frameworks=["FastAPI"],
        root_cause="Unsanitized user input reaching raw database query layer",
        constituent_findings=constituent_findings,
    )

    assert ctx.root_cause == "Unsanitized user input reaching raw database query layer"
    assert len(ctx.constituent_findings) == 1

    mock_llm = MockLLMProvider()
    agent = RemediationAgent(llm_provider=mock_llm)

    plan = await agent.generate_fix(ctx)

    assert plan.strategy is not None
    assert plan.root_cause == ctx.root_cause
    assert plan.risk_assessment is not None
    assert plan.risk_assessment.level in [l.value for l in PatchRiskLevel]
    assert len(plan.changes) >= 1


# ── 4. Dedicated Remediation REST API Endpoints ──────────────────────────────

@pytest.mark.asyncio
async def test_remediate_correlated_finding_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """POST /reviews/{id}/correlated-findings/{cid}/remediate triggers remediation for correlated cluster."""
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    review = Review(
        id=review_id,
        repository_id="fake-repo-75",
        commit_sha="abcdef",
        branch="main",
        status="completed",
    )
    db_session.add(review)

    primary_finding = Finding(
        id=finding_id,
        review_id=review_id,
        category="security",
        severity="high",
        title="SQL Injection",
        file_path="src/api/users.py",
        start_line=25,
        end_line=28,
        cwe="CWE-89",
        evidence='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        status="open",
    )
    db_session.add(primary_finding)

    correlated = CorrelatedFinding(
        id=corr_id,
        review_id=review_id,
        title="Unified SQL Injection & Missing Validation",
        description="Direct SQL interpolation coupled with missing input validation.",
        category="security",
        severity="high",
        primary_finding_id=finding_id,
        file_path="src/api/users.py",
        start_line=25,
        end_line=28,
        root_cause="Unvalidated input passed directly to database execution",
    )
    db_session.add(correlated)

    snapshot = RepositorySnapshot(
        review_id=review_id,
        commit_sha="abcdef",
        branch="main",
        languages=json.dumps({"primary": {"name": "Python"}}),
    )
    db_session.add(snapshot)
    await db_session.commit()

    resp = await client.post(f"/api/reviews/{review_id}/correlated-findings/{corr_id}/remediate?wait=true")
    assert resp.status_code == 201
    data = resp.json()
    assert data["review_id"] == review_id
    assert data["correlated_finding_id"] == corr_id
    assert data["status"] in ("completed", "generating", "patch_generated", "failed")

    # Verify run record in DB
    run_id = data["id"]
    run_res = await db_session.execute(select(RemediationRun).where(RemediationRun.id == run_id))
    persisted_run = run_res.scalar_one_or_none()
    assert persisted_run is not None
    assert persisted_run.correlated_finding_id == corr_id


@pytest.mark.asyncio
async def test_remediate_eligible_batch_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """POST /reviews/{id}/remediate-eligible batches remediation runs for open findings."""
    review_id = str(uuid.uuid4())
    f1_id = str(uuid.uuid4())
    f2_id = str(uuid.uuid4())

    review = Review(
        id=review_id,
        repository_id="batch-repo-75",
        commit_sha="112233",
        branch="main",
        status="completed",
    )
    db_session.add(review)

    f1 = Finding(
        id=f1_id,
        review_id=review_id,
        category="security",
        severity="high",
        title="SQL Injection",
        file_path="src/api/users.py",
        start_line=10,
        end_line=12,
        status="open",
    )
    f2 = Finding(
        id=f2_id,
        review_id=review_id,
        category="quality",
        severity="medium",
        title="Resource Leak",
        file_path="src/utils.py",
        start_line=5,
        end_line=7,
        status="open",
    )
    db_session.add_all([f1, f2])

    cf = CorrelatedFinding(
        id=str(uuid.uuid4()),
        review_id=review_id,
        primary_finding_id=f1_id,
        title="Correlated SQL Injection",
        category="security",
        severity="high",
        confidence=0.90,
    )
    db_session.add(cf)

    snapshot = RepositorySnapshot(
        review_id=review_id,
        commit_sha="112233",
        branch="main",
        languages=json.dumps({"primary": {"name": "Python"}}),
    )
    db_session.add(snapshot)
    await db_session.commit()

    resp = await client.post(
        f"/api/reviews/{review_id}/remediate-eligible",
        json={"categories": ["security"], "min_confidence": 0.7},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_id"] == review_id
    assert data["total_queued"] >= 1
    assert len(data["queued_runs"]) >= 1


@pytest.mark.asyncio
async def test_get_remediation_gate4_and_risk_endpoints(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """GET /remediations/{id}/gate-4 and /remediations/{id}/risk return structured audit telemetry."""
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    review = Review(id=review_id, repository_id="r", commit_sha="c", branch="m", status="completed")
    finding = Finding(id=finding_id, review_id=review_id, category="security", severity="high", title="SQL", file_path="src/db.py", status="open")
    
    meta = {
        "strategy": "Use parameterized queries",
        "explanation": "Safely parameterize SQL inputs",
        "gate_4_status": "PASSED",
        "gate_4_checks": [
            {"check_name": "diff_validation", "status": "passed", "details": "Clean diff"},
            {"check_name": "workspace_safety", "status": "passed", "details": "Confined to sandbox"},
            {"check_name": "syntax_validation", "status": "passed", "details": "AST passed"},
        ],
        "risk_assessment": {
            "level": "MEDIUM",
            "score": 0.35,
            "factors": ["Single-file localized change", "High-impact vulnerability class: CWE-89"],
            "explanation": "Medium risk patch.",
        },
    }

    run = RemediationRun(
        id=run_id,
        review_id=review_id,
        finding_id=finding_id,
        status="completed",
        gate_4_status="PASSED",
        risk_level="MEDIUM",
        patch_valid=True,
        metadata_json=json.dumps(meta),
    )
    db_session.add_all([review, finding, run])
    await db_session.commit()

    # 1. Gate 4 endpoint
    g4_resp = await client.get(f"/api/remediations/{run_id}/gate-4")
    assert g4_resp.status_code == 200
    g4_data = g4_resp.json()
    assert g4_data["gate_status"] == "PASSED"
    assert len(g4_data["checks"]) == 3

    # 2. Risk endpoint
    risk_resp = await client.get(f"/api/remediations/{run_id}/risk")
    assert risk_resp.status_code == 200
    risk_data = risk_resp.json()
    assert risk_data["level"] == "MEDIUM"
    assert risk_data["score"] == 0.35
    assert len(risk_data["factors"]) == 2


@pytest.mark.asyncio
async def test_retry_remediation_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """POST /remediations/{id}/retry creates a subsequent attempt with incremented patch version."""
    review_id = str(uuid.uuid4())
    finding_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    review = Review(id=review_id, repository_id="r", commit_sha="c", branch="m", status="completed")
    finding = Finding(id=finding_id, review_id=review_id, category="security", severity="high", title="SQL", file_path="src/db.py", status="open")
    run = RemediationRun(
        id=run_id,
        review_id=review_id,
        finding_id=finding_id,
        status="failed",
        patch_version=1,
    )
    db_session.add_all([review, finding, run])
    await db_session.commit()

    retry_resp = await client.post(f"/api/remediations/{run_id}/retry?wait=false")
    assert retry_resp.status_code == 201
    retry_data = retry_resp.json()
    assert retry_data["id"] != run_id
    assert retry_data["review_id"] == review_id
    assert retry_data["status"] == "queued"
    assert retry_data["patch_version"] == 2


def _is_ollama_online() -> bool:
    import urllib.request
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", headers={"User-Agent": "test"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


@pytest.mark.asyncio
@pytest.mark.skipif(not _is_ollama_online(), reason="Local Ollama not reachable on localhost:11434")
async def test_live_ollama_remediation_agent_inference():
    """Live inference test with local Ollama qwen2.5-coder:7b."""
    provider = OllamaProvider(base_url="http://localhost:11434", model="qwen2.5-coder:7b", timeout=60.0)
    agent = RemediationAgent(llm_provider=provider)

    finding = Finding(
        id="live-f1",
        review_id="live-r1",
        category="security",
        severity="high",
        title="SQL Injection in User Lookup",
        file_path="src/users.py",
        start_line=4,
        end_line=4,
        cwe="CWE-89",
        evidence='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        description="Dynamic string formatting into raw SQL query",
    )
    code = (
        "import db\n"
        "def get_user(user_id):\n"
        "    cursor = db.get_cursor()\n"
        '    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        "    return cursor.fetchone()\n"
    )
    ctx = build_remediation_context(
        finding=finding,
        file_content=code,
        repository_name="test-repo",
        languages={"primary": {"name": "Python"}},
        frameworks=["FastAPI"],
    )
    plan = await agent.generate_fix(ctx)
    assert plan.strategy is not None
    assert len(plan.changes) >= 1
    assert plan.risk_assessment is not None

