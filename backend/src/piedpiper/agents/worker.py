"""Worker agent implementation.

Owner: Person 2 (Agents)

Each worker runs in an isolated Daytona sandbox with a specific
persona (junior/intermediate/senior) and model. Workers execute
SDK/API tasks and report progress.
"""

from __future__ import annotations

from piedpiper.models.state import WorkerConfig, WorkerState


class WorkerAgent:
    """Manages a single worker's execution lifecycle."""

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.sandbox_id: str | None = None

    async def initialize_sandbox(self) -> str:
        """Provision a Daytona sandbox for this worker.

        Returns the sandbox_id.
        """
        # TODO: call Daytona SDK to create sandbox
        # TODO: install SDK/API and dependencies
        raise NotImplementedError

    async def execute_subtask(self, state: WorkerState, subtask: str) -> WorkerState:
        """Execute a subtask in the worker's sandbox.

        This is the main execution loop. The worker:
        1. Reads the subtask
        2. Plans an approach
        3. Writes and executes code
        4. Reports results

        Returns updated WorkerState.
        """
        # TODO: build messages from persona + subtask + conversation history
        # TODO: call LLM with worker's model
        # TODO: execute code in Daytona sandbox
        # TODO: update action_history, recent_errors, confidence
        raise NotImplementedError

    async def apply_expert_answer(self, state: WorkerState, answer: str) -> WorkerState:
        """Inject expert answer into worker's context and resume."""
        # TODO: add answer to conversation history
        # TODO: re-attempt the stuck task
        raise NotImplementedError

    async def cleanup(self):
        """Tear down the worker's sandbox."""
        # TODO: delete Daytona sandbox
        raise NotImplementedError
