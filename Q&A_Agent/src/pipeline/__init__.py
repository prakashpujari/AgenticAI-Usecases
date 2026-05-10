"""
src/pipeline/__init__.py
────────────────────────
Pipeline sub-package.

Contains the stage orchestration layer (stages.py) that:
  • Wraps each domain module call with observability (timing + metadata)
  • Provides individually testable stage functions
  • Is consumed by main.py for the end-to-end run
"""
