"""Worker agent implementation.

Each worker runs in an isolated Daytona sandbox and executes tasks
via W&B Inference. All workers use the same model and prompt.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable, Coroutine

from openai import AsyncOpenAI

from piedpiper.config import settings
from piedpiper.models.state import WorkerAction, WorkerConfig, WorkerState

# Type alias for the event emitter callback
EventEmitter = Callable[[str, str, dict[str, Any]], Coroutine[Any, Any, None]]

SYSTEM_PROMPT = """You are a capable software developer working on a task.
You write clean, working code and debug issues effectively.

Your task is to write and execute Python code to solve the given problem.
You have access to a sandbox where you can execute code.

If you are building a web application, start the server on port 8080 in the background
(e.g. using subprocess or threading) so it can be previewed. Make sure the server binds
to 0.0.0.0 so it is accessible externally.

Respond in this format:
THOUGHT: <your thinking and reasoning>
CODE: <the Python code to execute (wrapped in ```python ```)>
CONFIDENCE: <float between 0.0 and 1.0 representing your confidence>
"""


class WorkerAgent:
    """Manages a single worker's execution lifecycle."""

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.sandbox_id: str | None = None
        self._daytona = None
        self._client: AsyncOpenAI | None = None
        self._emit: EventEmitter | None = None

    def set_emitter(self, emit: EventEmitter) -> None:
        """Set the event emitter for real-time streaming."""
        self._emit = emit

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event if emitter is set."""
        if self._emit:
            await self._emit(self.config.id, event_type, data)

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=settings.wandb_base_url,
                api_key=settings.wandb_api_key,
            )
        return self._client

    async def initialize_sandbox(self) -> str:
        """Provision a Daytona sandbox for this worker."""
        try:
            from daytona_sdk import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams
        except ImportError:
            raise RuntimeError(
                "Daytona SDK not installed. Install it with: pip install daytona-sdk"
            )

        if not settings.daytona_api_key:
            raise RuntimeError("DAYTONA_API_KEY not configured. Set it in .env file.")

        config = DaytonaConfig(
            api_key=settings.daytona_api_key,
            api_url=settings.daytona_base_url,
            target="us",
        )
        self._daytona = Daytona(config)

        sandbox_name = f"piedpiper-{self.config.id}"

        # Delete existing sandbox with the same name if it exists
        try:
            existing = self._daytona.find_one(sandbox_name)
            if existing:
                self._daytona.delete(existing)
        except Exception:
            pass  # Doesn't exist, that's fine

        params = CreateSandboxFromSnapshotParams(
            language="python",
            name=sandbox_name,
            auto_stop_interval=0,
        )

        sandbox = self._daytona.create(params)
        self.sandbox_id = sandbox.id

        await self._emit_event("sandbox_ready", {"sandbox_id": sandbox.id})
        return self.sandbox_id

    def _build_messages(self, subtask: str, state: WorkerState) -> list[dict[str, Any]]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        for msg in state.conversation_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        messages.append({
            "role": "user",
            "content": f"Your task:\n{subtask}\n\nExecute this task step by step. Write code to accomplish it.",
        })

        return messages

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        result = {"thought": "", "code": "", "confidence": 0.5}

        thought_match = re.search(
            r"THOUGHT:\s*(.+?)(?=\nCODE:|\nCONFIDENCE:|$)", response, re.DOTALL | re.IGNORECASE
        )
        if thought_match:
            result["thought"] = thought_match.group(1).strip()

        code_match = re.search(r"```python\n(.*?)```", response, re.DOTALL)
        if code_match:
            result["code"] = code_match.group(1).strip()
        else:
            code_match = re.search(
                r"CODE:\s*(.+?)(?=\nCONFIDENCE:|$)", response, re.DOTALL | re.IGNORECASE
            )
            if code_match:
                result["code"] = code_match.group(1).strip()

        confidence_match = re.search(r"CONFIDENCE:\s*(0?\.\d+|1\.0|[01])", response, re.IGNORECASE)
        if confidence_match:
            result["confidence"] = float(confidence_match.group(1))

        return result

    def _ensure_daytona(self) -> None:
        """Ensure Daytona client is initialized for an existing sandbox."""
        if self._daytona is not None:
            return
        if not self.sandbox_id:
            return

        from daytona_sdk import Daytona, DaytonaConfig

        config = DaytonaConfig(
            api_key=settings.daytona_api_key,
            api_url=settings.daytona_base_url,
            target="us",
        )
        self._daytona = Daytona(config)

    async def _execute_code_in_sandbox(self, code: str) -> tuple[str, bool]:
        if not self.sandbox_id:
            return "Error: Sandbox not initialized", False

        self._ensure_daytona()
        if not self._daytona:
            return "Error: Daytona client not available", False

        try:
            # Look up by stable name, not UUID (which can go stale across runs)
            sandbox_name = f"piedpiper-{self.config.id}"
            sandbox = self._daytona.find_one(sandbox_name)
            file_name = f"/tmp/worker_{self.config.id}_{datetime.utcnow().timestamp()}.py"
            sandbox.fs.upload_file(code.encode(), file_name)
            exec_result = sandbox.process.exec(f"python {file_name}")
            output = exec_result.result
            success = exec_result.exit_code == 0
            return output, success
        except Exception as e:
            return f"Error executing code: {str(e)}", False

    async def _get_preview_urls(self) -> list[dict[str, Any]]:
        """Try to get preview URLs for common web server ports."""
        if not self.sandbox_id:
            return []

        self._ensure_daytona()
        if not self._daytona:
            return []

        common_ports = [8080, 3000, 5000, 8000, 4000, 5173, 8888]
        urls = []

        try:
            sandbox_name = f"piedpiper-{self.config.id}"
            sandbox = self._daytona.find_one(sandbox_name)

            for port in common_ports:
                try:
                    url = sandbox.get_preview_link(port).url
                    urls.append({"port": port, "url": url})
                except Exception:
                    continue
        except Exception:
            pass

        return urls

    async def execute_subtask(self, state: WorkerState, subtask: str) -> WorkerState:
        """Execute a subtask. Emits real-time events as work progresses."""
        client = self._get_client()
        messages = self._build_messages(subtask, state)

        await self._emit_event("thinking", {"status": "calling LLM..."})

        try:
            response = await client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
            )

            llm_response = response.choices[0].message.content
            parsed = self._parse_llm_response(llm_response)

            # Emit thought
            await self._emit_event("thought", {
                "thought": parsed["thought"],
                "confidence": parsed["confidence"],
                "has_code": bool(parsed["code"]),
            })

            state.conversation_history.append({
                "role": "assistant",
                "content": llm_response,
            })

            action = WorkerAction(
                action_type="llm_plan",
                description=parsed["thought"][:200],
            )
            state.action_history.append(action)

            if parsed["code"]:
                await self._emit_event("code_running", {
                    "code": parsed["code"][:500],
                    "lines": len(parsed["code"].splitlines()),
                })

                output, success = await self._execute_code_in_sandbox(parsed["code"])

                await self._emit_event("code_result", {
                    "success": success,
                    "output": output[:500],
                })

                code_action = WorkerAction(
                    action_type="code_execution",
                    description=f"Executed {len(parsed['code'])} chars of code",
                    result=output[:500] if success else None,
                    error=None if success else output[:500],
                )
                state.action_history.append(code_action)

                if not success:
                    state.recent_errors.append(output[:500])
                    state.recent_errors = state.recent_errors[-5:]

                state.conversation_history.append({
                    "role": "user",
                    "content": f"Code execution {'succeeded' if success else 'failed'}:\n{output[:1000]}",
                })

                if success and len(state.action_history) >= 1:
                    state.completed = True
                    state.output = {
                        "code": parsed["code"],
                        "output": output,
                        "thought": parsed["thought"],
                    }
                    await self._emit_event("completed", {
                        "output": output[:500],
                    })

                    # Try to get preview URLs for common web server ports
                    preview_urls = await self._get_preview_urls()
                    if preview_urls:
                        state.output["preview_urls"] = preview_urls
                        await self._emit_event("preview_url", {
                            "urls": preview_urls,
                        })

            state.llm_confidence = parsed["confidence"]
            state.minutes_without_progress += 0.5

        except Exception as e:
            error_msg = str(e)
            state.recent_errors.append(error_msg)
            state.recent_errors = state.recent_errors[-5:]

            await self._emit_event("error", {"error": error_msg[:300]})

            action = WorkerAction(
                action_type="llm_error",
                description="Failed to get LLM response",
                error=error_msg,
            )
            state.action_history.append(action)

        return state

    async def apply_expert_answer(self, state: WorkerState, answer: str) -> WorkerState:
        state.conversation_history.append({
            "role": "user",
            "content": f"Expert guidance: {answer}\n\nPlease continue with your task using this guidance.",
        })
        state.stuck = False

        action = WorkerAction(
            action_type="expert_guidance",
            description="Received guidance from expert agent",
        )
        state.action_history.append(action)

        if state.subtask:
            state = await self.execute_subtask(state, state.subtask)

        return state

    async def cleanup(self):
        if self.sandbox_id:
            self._ensure_daytona()
            if self._daytona:
                try:
                    sandbox = self._daytona.find_one(self.sandbox_id)
                    if sandbox:
                        self._daytona.delete(sandbox)
                except Exception:
                    pass
