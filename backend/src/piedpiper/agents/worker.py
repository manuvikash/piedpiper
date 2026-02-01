"""Worker agent implementation.

Owner: Person 2 (Agents)

Each worker runs in an isolated Daytona sandbox with a specific
persona (junior/intermediate/senior) and model via W&B Inference.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from piedpiper.config import settings
from piedpiper.models.state import WorkerConfig, WorkerState


class WorkerAgent:
    """Manages a single worker's execution lifecycle."""

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.sandbox_id: str | None = None
        self._daytona = None  # Lazy load Daytona SDK
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client for W&B Inference."""
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=settings.wandb_base_url,
                api_key=settings.wandb_api_key,
            )
        return self._client

    async def initialize_sandbox(self) -> str:
        """Provision a Daytona sandbox for this worker.

        Returns the sandbox_id.
        """
        try:
            from daytona_sdk import Daytona, CreateSandboxFromSnapshotParams
        except ImportError:
            raise RuntimeError(
                "Daytona SDK not installed. Install it with: pip install daytona-sdk"
            )

        if not settings.daytona_api_key:
            raise RuntimeError(
                "DAYTONA_API_KEY not configured. Set it in .env file."
            )

        # Initialize Daytona client
        self._daytona = Daytona()

        # Create sandbox for this worker with Python runtime
        params = CreateSandboxFromSnapshotParams(
            language="python",
            name=f"piedpiper-worker-{self.config.id}",
            auto_stop_interval=0,  # Disable auto-stop
        )
        
        sandbox = self._daytona.create(params)
        self.sandbox_id = sandbox.id

        print(f"✓ Created Daytona sandbox {sandbox.id} for worker {self.config.id}")

        # TODO: Install SDK/API and dependencies in sandbox
        # sandbox.exec("pip install stripe")  # Example

        return self.sandbox_id

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
        if self._daytona and self.sandbox_id:
            try:
                sandbox = self._daytona.find_one(self.sandbox_id)
                if sandbox:
                    sandbox.delete()
                    print(f"✓ Deleted Daytona sandbox {self.sandbox_id}")
            except Exception as e:
                print(f"⚠️  Failed to cleanup sandbox {self.sandbox_id}: {e}")
                pass  # Best effort cleanup
