"""
Unit tests for FileSelector and token budgeting.
"""
from app.analysis.file_selector import FileSelector, estimate_tokens


def test_estimate_tokens():
    assert estimate_tokens("abc") >= 1
    assert estimate_tokens("a" * 400) == 100


def test_select_for_understanding_prioritizes_entry_points():
    selector = FileSelector()
    files = {
        "src/utils/math.py": "def add(a, b): return a + b\n" * 20,
        "main.py": "from app import create_app\napp = create_app()\n",
        "package.json": '{"name": "my-app", "version": "1.0.0"}\n',
        "tests/test_math.py": "def test_add(): assert add(1, 2) == 3\n" * 50,
    }

    selected = selector.select_for_understanding(files, entry_points=["main.py"], max_tokens=1000)
    assert "main.py" in selected
    assert "package.json" in selected


def test_select_for_security_prioritizes_auth_and_sql():
    selector = FileSelector()
    files = {
        "src/auth/login.py": "def login(user, password):\n    query = f'SELECT * FROM users WHERE u={user}'\n",
        "src/ui/colors.ts": "export const BLUE = '#0000ff';\n",
        "src/api/users.py": "def get_user(id):\n    return db.execute('SELECT * FROM users')\n",
        "README.md": "# Readme\n",
    }

    selected = selector.select_for_security(files, max_tokens=500)
    assert "src/auth/login.py" in selected
    assert "src/api/users.py" in selected


def test_select_for_code_review():
    selector = FileSelector()
    files = {
        "src/service.py": "class ComplexService:\n" + ("    def step(self): pass\n" * 40),
        "src/small.py": "x = 1\n",
    }

    selected = selector.select_for_code_review(files, max_tokens=500)
    assert "src/service.py" in selected


def test_token_budget_limit():
    selector = FileSelector()
    # Create 50 files each with ~500 tokens
    files = {
        f"file_{i}.py": ("# content line\n" * 100) for i in range(50)
    }

    # Set budget to ~1000 tokens
    selected = selector.select_for_code_review(files, max_tokens=1000)
    total_tokens = sum(estimate_tokens(c) for c in selected.values())
    assert total_tokens <= 1500  # Stays bounded
    assert len(selected) < len(files)
