import asyncio
from enum import Enum
from typing import Any, Callable, Awaitable
from pydantic import BaseModel


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkflowStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class Task(BaseModel):
    task_id: str
    name: str
    dependencies: list[str] = []
    requires_approval: bool = False
    max_retries: int = 3
    retry_backoff: float = 2.0
    condition: str | None = None


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    output: Any = None
    error: str | None = None
    attempt: int = 1


class PipelineEngine:
    async def run(
        self,
        tasks: list[Task],
        executor: Callable[[Task, dict], Awaitable[Any]],
        inputs: dict,
    ) -> dict[str, TaskResult]:
        results: dict[str, TaskResult] = {}
        pending = {t.task_id: t for t in tasks}

        while pending:
            ready = [
                t for t in pending.values()
                if all(
                    results.get(dep, TaskResult(task_id=dep, status=TaskStatus.PENDING)).status
                    == TaskStatus.COMPLETED
                    for dep in t.dependencies
                )
            ]
            if not ready:
                break

            coros = [self._run_task(t, executor, inputs, results) for t in ready]
            await asyncio.gather(*coros)
            for t in ready:
                pending.pop(t.task_id)

        return results

    async def _run_task(
        self,
        task: Task,
        executor: Callable,
        inputs: dict,
        results: dict[str, TaskResult],
    ) -> None:
        for attempt in range(1, task.max_retries + 1):
            try:
                output = await executor(task, inputs)
                results[task.task_id] = TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.COMPLETED,
                    output=output,
                    attempt=attempt,
                )
                return
            except Exception as exc:
                if attempt == task.max_retries:
                    results[task.task_id] = TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.FAILED,
                        error=str(exc),
                        attempt=attempt,
                    )
                else:
                    await asyncio.sleep(task.retry_backoff ** attempt)
