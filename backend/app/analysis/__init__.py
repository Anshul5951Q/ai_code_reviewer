# app/analysis/__init__.py
"""
Analysis pipeline for repository ingestion.

Modules:
    file_filter          — include/exclude files based on extension, path, size
    language_detector    — deterministic language detection from file extensions
    dependency_analyzer  — parse dependency manifests (package.json, requirements.txt, etc.)
    repository_intelligence — aggregate repository structure and metadata
    snapshot             — build structured RepositorySnapshot data
    ingestion            — orchestrate the full ingestion pipeline
"""
