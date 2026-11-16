"""
Test suite for Deep Repository Analysis Validation & Security Engine Hardening.

Covers:
1. All 12 Vulnerability Categories:
   - SQL Injection
   - NoSQL Injection
   - Command Injection
   - Cross-Site Scripting (XSS)
   - Hardcoded Secrets (with Shannon entropy)
   - Unsafe Dynamic Execution (eval/exec)
   - Path Traversal
   - Server-Side Request Forgery (SSRF)
   - Insecure Deserialization
   - Broken Authentication / Insecure JWT
   - Weak Cryptography & Insecure Randomness
   - Insecure Permissions / File Upload
2. Dependency Manifest Auditing (requirements.txt & package.json)
3. Secret Redaction & Masking
4. Safe Code / Zero False Positives
5. Coverage-Aware Scoring Engine
6. Sandboxed Analysis Workspace Cache
7. Canonical File Inventory Lifecycle
"""
from __future__ import annotations

import os
import shutil
import pytest

from app.analysis.inventory import FileInventory, FileProcessingStatus
from app.analysis.workspace import AnalysisWorkspace
from app.analysis.finding_normalizer import CanonicalFinding, FindingNormalizer
from app.analysis.static_analysis import (
    StaticSecurityAnalyzer,
    mask_secret,
    shannon_entropy,
)


def test_sql_injection_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/db.py": """
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
""",
        "frontend/src/db.ts": """
export async function queryUser(name: string) {
    const sql = `SELECT * FROM accounts WHERE username = '${name}'`;
    return db.raw(sql);
}
""",
    }
    findings = analyzer.analyze_repository_files(files)
    sqli = [f for f in findings if f.type == "sql_injection"]
    assert len(sqli) >= 2
    assert any("db.py" in f.file_path for f in sqli)
    assert any("db.ts" in f.file_path for f in sqli)
    assert all(f.cwe == "CWE-89" for f in sqli)


def test_nosql_injection_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/mongo.py": """
def search_mongo(user_filter):
    return db.users.find({"$where": "this.name == '" + user_filter + "'"})
""",
    }
    findings = analyzer.analyze_repository_files(files)
    nosqli = [f for f in findings if f.type == "nosql_injection"]
    assert len(nosqli) >= 1
    assert nosqli[0].cwe == "CWE-943"


def test_command_injection_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/shell.py": """
import subprocess
import os

def ping(host):
    os.system("ping " + host)
    subprocess.run(f"nslookup {host}", shell=True)
""",
        "frontend/cli.js": """
const { exec } = require('child_process');
function run(cmd) {
    exec('echo ' + cmd);
}
""",
    }
    findings = analyzer.analyze_repository_files(files)
    cmd_inj = [f for f in findings if f.type in ("command_injection", "dangerous_subprocess")]
    assert len(cmd_inj) >= 2
    assert any("shell.py" in f.file_path for f in cmd_inj)
    assert any("cli.js" in f.file_path for f in cmd_inj)
    assert any(f.cwe == "CWE-78" for f in cmd_inj)


def test_xss_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "frontend/src/component.tsx": """
export function Profile({ userBio }: { userBio: string }) {
    return <div dangerouslySetInnerHTML={{ __html: userBio }} />;
}
""",
        "frontend/src/legacy.js": """
function render(msg) {
    document.getElementById("output").innerHTML = msg;
}
""",
    }
    findings = analyzer.analyze_repository_files(files)
    xss = [f for f in findings if f.type == "xss"]
    assert len(xss) >= 2
    assert all(f.cwe == "CWE-79" for f in xss)


def test_hardcoded_secrets_and_entropy():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/config.py": """
# Hardcoded high-entropy API key
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
SLACK_TOKEN = "xoxb-000000000000-TEST-FIXTURE-NOT-A-REAL-TOKEN"
GITHUB_PAT = "ghp_1234567890abcdefghijklmnopqrstuvwxyzAB"
""",
    }
    findings = analyzer.analyze_repository_files(files)
    secrets = [f for f in findings if f.type == "hardcoded_secret"]
    assert len(secrets) >= 2
    assert all(f.cwe == "CWE-798" for f in secrets)
    # Check that evidence was masked
    for s in secrets:
        assert "EXAMPLEKEY" not in s.evidence
    assert any("ghp_" in s.evidence for s in secrets)
    assert any("*" in s.evidence for s in secrets)


def test_unsafe_eval_exec_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/calculator.py": """
def calc(expr):
    return eval(expr)
""",
        "backend/runner.py": """
def run_code(code_str):
    exec(code_str)
""",
    }
    findings = analyzer.analyze_repository_files(files)
    dynamic_exec = [f for f in findings if f.type in ("unsafe_eval", "unsafe_dynamic_execution")]
    assert len(dynamic_exec) >= 2
    assert all(f.cwe == "CWE-95" for f in dynamic_exec)


def test_path_traversal_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/files.py": """
def read_user_file(filename):
    with open("/var/data/" + filename, "r") as f:
        return f.read()
""",
    }
    findings = analyzer.analyze_repository_files(files)
    traversal = [f for f in findings if f.type == "path_traversal"]
    assert len(traversal) >= 1
    assert traversal[0].cwe == "CWE-22"


def test_ssrf_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/proxy.py": """
import requests

def fetch_external(target_url):
    return requests.get(target_url)
""",
    }
    findings = analyzer.analyze_repository_files(files)
    ssrf = [f for f in findings if f.type == "ssrf"]
    assert len(ssrf) >= 1
    assert ssrf[0].cwe == "CWE-918"


def test_insecure_deserialization_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/session.py": """
import pickle
import yaml

def load_session(data):
    obj = pickle.loads(data)
    cfg = yaml.load(data, Loader=yaml.Loader)
    return obj, cfg
""",
    }
    findings = analyzer.analyze_repository_files(files)
    deser = [f for f in findings if f.type == "insecure_deserialization"]
    assert len(deser) >= 2
    assert all(f.cwe == "CWE-502" for f in deser)


def test_broken_auth_jwt_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/auth.py": """
import jwt

def verify_token(token):
    return jwt.decode(token, algorithms=['none'], options={"verify_signature": False})
""",
    }
    findings = analyzer.analyze_repository_files(files)
    auth_issues = [f for f in findings if f.type in ("broken_auth", "broken_authentication", "insecure_jwt")]
    assert len(auth_issues) >= 1
    assert auth_issues[0].cwe in ("CWE-287", "CWE-347")


def test_weak_crypto_and_randomness_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/hasher.py": """
import hashlib
import random

def hash_pw(pw):
    return hashlib.md5(pw.encode()).hexdigest()

def make_token():
    return str(random.random())
""",
    }
    findings = analyzer.analyze_repository_files(files)
    crypto_issues = [f for f in findings if f.type in ("weak_crypto", "weak_random", "weak_cryptography", "insecure_randomness")]
    assert len(crypto_issues) >= 2
    assert any(f.cwe == "CWE-327" for f in crypto_issues)
    assert any(f.cwe == "CWE-338" for f in crypto_issues)


def test_insecure_permissions_detection():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "backend/perms.py": """
import os

def init_file(path):
    os.chmod(path, 0o777)
""",
    }
    findings = analyzer.analyze_repository_files(files)
    perm_issues = [f for f in findings if f.type in ("insecure_file_handling", "insecure_permissions")]
    assert len(perm_issues) >= 1
    assert perm_issues[0].cwe == "CWE-732"


def test_dependency_manifest_auditing():
    analyzer = StaticSecurityAnalyzer()
    files = {
        "requirements.txt": """
requests==2.6.0
flask==0.12.0
urllib3==1.24.1
""",
        "package.json": """{
  "dependencies": {
    "lodash": "4.17.15",
    "axios": "0.18.0"
  }
}""",
    }
    findings = analyzer.analyze_repository_files(files)
    dep_findings = [f for f in findings if f.type in ("vulnerable_dependency", "dependency_vulnerability")]
    assert len(dep_findings) >= 3
    assert any("requests" in f.title.lower() or "requirements" in f.file_path for f in dep_findings)
    assert any("lodash" in f.description.lower() or "package" in f.file_path for f in dep_findings)


def test_secret_masking_utility():
    raw_secret = "AKIA1234567890EXAMPLE"
    masked = mask_secret(raw_secret)
    assert raw_secret not in masked
    assert "AKIA" in masked
    assert "*" in masked

    priv_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA..."
    masked_key = mask_secret(priv_key)
    assert "[REDACTED" in masked_key or "BEGIN" in masked_key


def test_safe_code_produces_no_false_positives():
    analyzer = StaticSecurityAnalyzer()
    safe_files = {
        "backend/safe_db.py": """
import hashlib
import secrets

def safe_user(cursor, user_id):
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

def safe_hash(data):
    return hashlib.sha256(data.encode()).hexdigest()

def safe_token():
    return secrets.token_hex(32)
""",
    }
    findings = analyzer.analyze_repository_files(safe_files)
    assert len(findings) == 0


def test_coverage_aware_scoring_insufficient_vs_adequate():
    normalizer = FindingNormalizer()

    # Case A: 0 files analyzed must strictly result in 0.0 scores
    res_zero = normalizer.calculate_scores(
        findings=[],
        files_analyzed_count=0,
        total_eligible_source_files=50,
    )
    assert res_zero["overall_score"] == 0.0
    assert res_zero["security_score"] == 0.0
    assert res_zero["quality_score"] == 0.0
    assert res_zero["coverage_percentage"] == 0.0
    assert res_zero["coverage_status"] == "INSUFFICIENT ANALYSIS COVERAGE"

    # Case B: 50 files analyzed with 0 findings must produce high score and transparent scope message
    res_clean = normalizer.calculate_scores(
        findings=[],
        files_analyzed_count=50,
        total_eligible_source_files=50,
    )
    assert res_clean["overall_score"] == 100.0
    assert res_clean["security_score"] == 100.0
    assert res_clean["coverage_percentage"] == 100.0
    assert res_clean["coverage_status"] == "ADEQUATE ANALYSIS COVERAGE"
    assert "NO VULNERABILITIES DETECTED" in res_clean["coverage_summary"]


def test_analysis_workspace_caching_and_sandboxing(tmp_path):
    test_review_id = "test-review-uuid-1234"
    workspace = AnalysisWorkspace(test_review_id, root_dir=tmp_path)

    test_files = {
        "backend/app.py": "print('hello')",
        "frontend/src/index.ts": "export const x = 1;",
    }

    # Save and load
    workspace.save_files(test_files)
    loaded = workspace.load_files()
    assert loaded == test_files

    # Path traversal attack guard
    with pytest.raises(ValueError):
        workspace.get_file("../../../etc/passwd")

    # Cleanup
    workspace.cleanup()
    assert not workspace.workspace_dir.exists()


def test_file_inventory_lifecycle():
    inventory = FileInventory(review_id="rev-1", commit_sha="abcdef123456")

    # Discovered
    inventory.record_discovered("src/main.py", 1200)
    inventory.record_discovered("src/utils.py", 800)
    inventory.record_discovered("node_modules/pkg/index.js", 50000)

    # Filtered
    inventory.record_filtered("node_modules/pkg/index.js", "Third-party dependency vendor")

    # Downloaded & Decoded
    inventory.record_downloaded("src/main.py", 1200)
    inventory.record_decoded("src/main.py", "import os\n")
    inventory.record_downloaded("src/utils.py", 800)
    inventory.record_decoded("src/utils.py", "def util(): pass\n")

    # Analyzed
    inventory.record_analyzed("src/main.py", "security_static")
    inventory.record_analyzed("src/main.py", "security_agent")
    inventory.record_analyzed("src/utils.py", "security_static")

    coverage = inventory.calculate_coverage(total_eligible_source=2)
    assert coverage.total_discovered == 3
    assert coverage.downloaded_count == 2
    assert coverage.analyzed_count == 2
    assert coverage.coverage_percentage == 100.0
    assert coverage.coverage_status == "ADEQUATE ANALYSIS COVERAGE"

    # Downloaded & Decoded
    inventory.record_downloaded("src/main.py", 1200)
    inventory.record_decoded("src/main.py", "import os\n")
    inventory.record_downloaded("src/utils.py", 800)
    inventory.record_decoded("src/utils.py", "def util(): pass\n")

    # Analyzed
    inventory.record_analyzed("src/main.py", "security_static")
    inventory.record_analyzed("src/main.py", "security_agent")
    inventory.record_analyzed("src/utils.py", "security_static")

    coverage = inventory.calculate_coverage(total_eligible_source=2)
    assert coverage.total_discovered == 3
    assert coverage.downloaded_count == 2
    assert coverage.analyzed_count == 2
    assert coverage.coverage_percentage == 100.0
    assert coverage.coverage_status == "ADEQUATE ANALYSIS COVERAGE"
