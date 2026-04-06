"""
observability/
--------------
Lightweight operational instrumentation for the pipeline.

Public API:
    record_step   — context manager for recording a PipelineStepRun
    StepRecorder  — class-based alternative for imperative usage
"""
from observability.step_recorder import StepRecorder, record_step

__all__ = ["record_step", "StepRecorder"]
