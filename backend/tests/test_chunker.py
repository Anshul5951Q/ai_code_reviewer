"""
Unit tests for source file chunking utility.
"""
from app.analysis.chunker import chunk_file, chunk_files


def test_chunk_empty_file():
    chunks = chunk_file("empty.py", "")
    assert len(chunks) == 1
    assert chunks[0].file_path == "empty.py"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 1
    assert chunks[0].content == ""


def test_chunk_small_file():
    content = "line1\nline2\nline3\n"
    chunks = chunk_file("small.py", content, max_lines=10)
    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 3
    assert chunks[0].total_lines == 3
    assert chunks[0].content == content


def test_chunk_large_file_preserves_lines():
    # Generate 100 lines
    lines = [f"print('line {i}')\n" for i in range(1, 101)]
    content = "".join(lines)

    chunks = chunk_file("large.py", content, max_lines=40, overlap=10)
    assert len(chunks) > 1

    # Chunk 0: 1 to 40
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 40
    assert chunks[0].chunk_index == 0
    assert chunks[0].total_lines == 100

    # Chunk 1: step is 40 - 10 = 30, so starts at 31
    assert chunks[1].start_line == 31
    assert chunks[1].end_line == 70
    assert chunks[1].chunk_index == 1

    # Last chunk covers up to line 100
    assert chunks[-1].end_line == 100


def test_chunk_files_multiple():
    files = {
        "a.py": "a = 1\nb = 2\n",
        "b.py": "c = 3\n",
    }
    chunks = chunk_files(files, max_lines=50)
    assert len(chunks) == 2
    paths = {c.file_path for c in chunks}
    assert paths == {"a.py", "b.py"}
