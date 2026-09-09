"""
Unit tests for deterministic static security rules and secret redaction.
"""
from app.analysis.static_analysis import (
    StaticSecurityAnalyzer,
    mask_secret,
    shannon_entropy,
)


def test_mask_secret():
    assert mask_secret("short") == "*****"
    assert mask_secret("AKIAIOSFODNN7EXAMPLE") == "AKIA****************"
    assert mask_secret("") == "[REDACTED]"


def test_shannon_entropy():
    # Low entropy (uniform or repeated)
    low_e = shannon_entropy("aaaaaaaaaaaaaaaaaaaa")
    assert low_e == 0.0

    # High entropy (random alphanumeric)
    high_e = shannon_entropy("k3N9f8L2q1P4z7W0x5Y8")
    assert high_e > 3.5


def test_sql_injection_detection():
    analyzer = StaticSecurityAnalyzer()
    vulnerable_code = """
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return db.execute(query)

def get_by_name(name):
    return db.execute("SELECT * FROM users WHERE name = '" + name + "'")
"""
    findings = analyzer.analyze_file("src/db.py", vulnerable_code)
    sqli_findings = [f for f in findings if f.type == "sql_injection"]
    assert len(sqli_findings) >= 2
    assert all(f.cwe == "CWE-89" for f in sqli_findings)


def test_sql_injection_parameterized_safe():
    analyzer = StaticSecurityAnalyzer()
    safe_code = """
def get_user_safe(user_id):
    return db.execute("SELECT * FROM users WHERE id = %s", (user_id,))
"""
    findings = analyzer.analyze_file("src/db_safe.py", safe_code)
    sqli_findings = [f for f in findings if f.type == "sql_injection"]
    assert len(sqli_findings) == 0


def test_xss_detection():
    analyzer = StaticSecurityAnalyzer()
    vulnerable_react = """
export function Profile({ bio }) {
    return <div dangerouslySetInnerHTML={{ __html: bio }} />;
}
"""
    findings = analyzer.analyze_file("src/Profile.tsx", vulnerable_react)
    xss_findings = [f for f in findings if f.type == "xss"]
    assert len(xss_findings) == 1
    assert xss_findings[0].cwe == "CWE-79"


def test_command_injection_detection():
    analyzer = StaticSecurityAnalyzer()
    vulnerable_cmd = """
import subprocess
import os

def ping(host):
    subprocess.run(f"ping -c 1 {host}", shell=True)
    os.system("echo " + host)
"""
    findings = analyzer.analyze_file("src/network.py", vulnerable_cmd)
    cmd_findings = [f for f in findings if f.type == "command_injection"]
    assert len(cmd_findings) >= 2
    assert all(f.cwe == "CWE-78" for f in cmd_findings)


def test_path_traversal_detection():
    analyzer = StaticSecurityAnalyzer()
    vulnerable_path = """
import os

def read_doc(request):
    doc_path = os.path.join("/var/docs", request.args.get("file"))
    with open(doc_path) as f:
        return f.read()
"""
    findings = analyzer.analyze_file("src/files.py", vulnerable_path)
    path_findings = [f for f in findings if f.type == "path_traversal"]
    assert len(path_findings) >= 1
    assert path_findings[0].cwe == "CWE-22"


def test_hardcoded_secrets_and_strict_redaction():
    analyzer = StaticSecurityAnalyzer()
    raw_aws_key = "AKIA1234567890ABCDEF"
    code = f"""
# Configuration
AWS_ACCESS_KEY = "{raw_aws_key}"
"""
    findings = analyzer.analyze_file("src/config.py", code)
    secret_findings = [f for f in findings if f.type == "hardcoded_secret"]
    assert len(secret_findings) == 1
    assert secret_findings[0].cwe == "CWE-798"

    # CRITICAL CHECK: Raw secret must NOT be in evidence!
    assert raw_aws_key not in secret_findings[0].evidence
    assert "AKIA****************" in secret_findings[0].evidence


def test_secret_placeholder_suppression():
    analyzer = StaticSecurityAnalyzer()
    placeholder_code = """
API_KEY = "YOUR_API_KEY_HERE"
SECRET_TOKEN = "changeme"
TEST_VAL = "test-secret"
"""
    findings = analyzer.analyze_file("src/example.py", placeholder_code)
    secret_findings = [f for f in findings if f.type == "hardcoded_secret"]
    assert len(secret_findings) == 0


def test_insecure_file_permissions():
    analyzer = StaticSecurityAnalyzer()
    perm_code = """
import os
os.chmod("/tmp/shared", 0o777)
"""
    findings = analyzer.analyze_file("src/setup.py", perm_code)
    perm_findings = [f for f in findings if f.type == "insecure_file_handling"]
    assert len(perm_findings) == 1
    assert perm_findings[0].cwe == "CWE-732"
