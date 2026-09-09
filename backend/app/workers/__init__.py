# app/workers/__init__.py
"""
Background worker system for repository analysis jobs.

Uses Redis + rq for job queuing. The AnalysisQueue is the single
integration point — swap this module's implementation to change backends.
"""
