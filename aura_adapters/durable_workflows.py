"""
===================================================================================
AURA ADAPTER: DURABLE WORKFLOWS & JOB QUEUES
===================================================================================
Curated capabilities extracted from:
- temporalio/temporal (Replay State & Step Idempotency)
- PrefectHQ/prefect (Task Flows & Exponential Backoff Retries)
- inngest/inngest (Event-Driven Step Functions)
- celery/celery (Asynchronous Task Queue & Polling)
===================================================================================
"""
import time
from typing import Dict, Any, List, Optional, Callable


class PrefectDurableFlowRunner:
    """Prefect/Temporal-inspired durable step flow with automatic retries and state checkpoints."""
    def __init__(self, max_retries: int = 3, backoff_factor: float = 0.5):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.completed_steps: List[Dict[str, Any]] = []

    def execute_step(self, step_name: str, step_fn: Callable[[], Any]) -> Dict[str, Any]:
        attempts = 0
        last_error = None

        while attempts < self.max_retries:
            attempts += 1
            try:
                result = step_fn()
                record = {
                    "step_name": step_name,
                    "status": "COMPLETED",
                    "attempts": attempts,
                    "timestamp": time.time(),
                    "result": result
                }
                self.completed_steps.append(record)
                return record
            except Exception as e:
                last_error = str(e)
                time.sleep(self.backoff_factor * (2 ** (attempts - 1)))

        failed_record = {
            "step_name": step_name,
            "status": "FAILED",
            "attempts": attempts,
            "error": last_error
        }
        self.completed_steps.append(failed_record)
        return failed_record


class CeleryTaskQueue:
    """celery-inspired async in-memory job queue with task tracking."""
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._counter = 0

    def submit_task(self, name: str, payload: Dict[str, Any]) -> str:
        self._counter += 1
        task_id = f"task_{self._counter}"
        self.tasks[task_id] = {
            "id": task_id,
            "name": name,
            "payload": payload,
            "status": "PENDING",
            "submitted_at": time.time(),
            "result": None
        }
        return task_id

    def complete_task(self, task_id: str, result: Any):
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "SUCCESS"
            self.tasks[task_id]["result"] = result
            self.tasks[task_id]["completed_at"] = time.time()

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.tasks.get(task_id)
