"""
Schedule Background Processing Package

This package contains all background task processing related to schedule generation,
academic calendar operations, and intelligent class session creation.

Modules:
- background: Main schedule generation tasks and worker configuration
- arq_worker: ARQ worker startup and management utilities
- worker_manager: Production worker management for scaling
"""

__all__ = ['background', 'arq_worker', 'worker_manager']