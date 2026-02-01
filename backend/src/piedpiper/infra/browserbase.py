"""Browserbase validation pipeline.

Owner: Person 3 (Infrastructure)

Validates worker output by deploying and testing in a real browser
via Browserbase. Checks page loads, console errors, API calls,
and user flows.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from playwright.async_api import async_playwright

from piedpiper.config import settings
from piedpiper.models.validation import ValidationCheck, ValidationResult

logger = logging.getLogger(__name__)


class BrowserbaseClient:
    """Client for Browserbase API."""

    def __init__(self, api_key: str, project_id: str):
        self.api_key = api_key
        self.project_id = project_id
        self.base_url = "https://api.browserbase.com/v1"

    async def create_session(self) -> dict[str, Any]:
        """Create a new browser session."""
        import httpx

        headers = {
            "x-bb-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "projectId": self.project_id,
            "proxies": True,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/sessions",
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def delete_session(self, session_id: str) -> None:
        """Delete a browser session."""
        import httpx

        headers = {"x-bb-api-key": self.api_key}

        async with httpx.AsyncClient() as client:
            await client.delete(
                f"{self.base_url}/sessions/{session_id}",
                headers=headers,
                timeout=10.0,
            )


class BrowserbaseValidator:
    """Validates worker output in real browser sessions."""

    def __init__(self, api_key: str | None = None, project_id: str | None = None):
        self.api_key = api_key or settings.browserbase_api_key
        self.project_id = project_id or settings.browserbase_project_id
        self.client = BrowserbaseClient(self.api_key, self.project_id)

    async def validate_worker_output(
        self, worker_id: str, output: dict[str, Any]
    ) -> ValidationResult:
        """Full validation pipeline for a worker's output.

        1. Create Browserbase session
        2. Connect via Playwright CDP
        3. Run validation checks
        4. Capture screenshots and logs
        5. Clean up session
        """
        session = None
        session_id = None

        try:
            # Create Browserbase session
            logger.info(f"Creating Browserbase session for worker {worker_id}...")
            session = await self.client.create_session()
            session_id = session["id"]
            connect_url = session["connectUrl"]
            logger.info(f"Session created: {session_id}")

            # Get preview URL if available from worker output
            preview_urls = output.get("preview_urls", [])
            if not preview_urls:
                return ValidationResult(
                    worker_id=worker_id,
                    passed=False,
                    score=0.0,
                    checks=[ValidationCheck(
                        name="has_preview_url",
                        passed=False,
                        error="No preview URL found in worker output"
                    )],
                    screenshots=[],
                    logs={},
                    errors=["Worker did not produce a previewable output"],
                )

            app_url = preview_urls[0].get("url", "")
            if not app_url:
                return ValidationResult(
                    worker_id=worker_id,
                    passed=False,
                    score=0.0,
                    checks=[ValidationCheck(
                        name="valid_preview_url",
                        passed=False,
                        error="Preview URL is empty"
                    )],
                    screenshots=[],
                    logs={},
                    errors=["Empty preview URL"],
                )

            # Connect via Playwright CDP
            logger.info(f"Connecting to session via CDP...")
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(connect_url)
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()

                try:
                    # Run validation checks in parallel
                    checks = await self._run_checks(page, app_url, output)

                    # Take screenshot
                    screenshot = await self._take_screenshot(page)
                    screenshots = [screenshot] if screenshot else []

                    # Get console and network logs
                    logs = await self._get_logs(page)

                    # Calculate overall score
                    passed_checks = [c for c in checks if c.passed]
                    score = len(passed_checks) / len(checks) if checks else 0.0

                    errors = [c.error for c in checks if not c.passed and c.error]

                    return ValidationResult(
                        worker_id=worker_id,
                        passed=score >= 0.8,
                        score=score,
                        checks=checks,
                        screenshots=screenshots,
                        logs=logs,
                        errors=errors,
                    )

                finally:
                    await browser.close()

        except Exception as e:
            logger.error(f"Validation failed for worker {worker_id}: {e}")
            return ValidationResult(
                worker_id=worker_id,
                passed=False,
                score=0.0,
                checks=[],
                screenshots=[],
                logs={},
                errors=[str(e)],
            )

        finally:
            if session_id:
                try:
                    await self.client.delete_session(session_id)
                    logger.info(f"Session {session_id} deleted")
                except Exception as e:
                    logger.warning(f"Failed to delete session {session_id}: {e}")

    async def _run_checks(
        self, page: Any, app_url: str, output: dict[str, Any]
    ) -> list[ValidationCheck]:
        """Run all validation checks."""
        expected_apis = output.get("expected_apis", [])
        user_flows = output.get("user_flows", [])

        # Run checks in parallel where possible
        page_load_task = self.check_page_loads(page, app_url)
        console_error_task = self.check_no_console_errors(page, app_url)

        page_load, console_errors = await asyncio.gather(
            page_load_task, console_error_task
        )

        checks = [page_load, console_errors]

        # API endpoint check (only if expected APIs specified)
        if expected_apis:
            api_check = await self.check_api_endpoints(page, app_url, expected_apis)
            checks.append(api_check)

        # User flow check (only if flows specified)
        if user_flows:
            flow_check = await self.check_user_flows(page, user_flows)
            checks.append(flow_check)

        return checks

    async def check_page_loads(self, page: Any, url: str) -> ValidationCheck:
        """Verify the page loads without errors."""
        try:
            logger.debug(f"Checking page load for {url}...")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            if response is None:
                return ValidationCheck(
                    name="page_loads",
                    passed=False,
                    error="Page navigation failed - no response received",
                )

            status = response.status
            if status >= 400:
                return ValidationCheck(
                    name="page_loads",
                    passed=False,
                    error=f"Page returned HTTP {status}",
                )

            # Check if page has content
            content = await page.content()
            if len(content) < 100:
                return ValidationCheck(
                    name="page_loads",
                    passed=False,
                    error="Page content is too short (likely an error page)",
                )

            return ValidationCheck(name="page_loads", passed=True)

        except Exception as e:
            return ValidationCheck(
                name="page_loads",
                passed=False,
                error=f"Page load failed: {str(e)[:200]}",
            )

    async def check_no_console_errors(self, page: Any, url: str) -> ValidationCheck:
        """Verify no JavaScript console errors."""
        console_errors = []

        def handle_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)

        page.on("console", handle_console)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            # Wait a bit for any async errors
            await asyncio.sleep(2)

            if console_errors:
                # Filter out common benign errors
                critical_errors = [
                    e for e in console_errors
                    if "favicon" not in e.lower() and "analytics" not in e.lower()
                ]

                if critical_errors:
                    return ValidationCheck(
                        name="no_console_errors",
                        passed=False,
                        error=f"Console errors: {critical_errors[:3]}",
                    )

            return ValidationCheck(name="no_console_errors", passed=True)

        except Exception as e:
            return ValidationCheck(
                name="no_console_errors",
                passed=False,
                error=f"Console check failed: {str(e)[:200]}",
            )

    async def check_api_endpoints(
        self, page: Any, url: str, expected_apis: list[str]
    ) -> ValidationCheck:
        """Verify expected API calls are made."""
        api_calls = []

        def handle_route(route, request):
            api_calls.append(request.url)
            route.continue_()

        await page.route("**/*", handle_route)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # Wait for API calls

            missing = []
            for api in expected_apis:
                if not any(api in call for call in api_calls):
                    missing.append(api)

            if missing:
                return ValidationCheck(
                    name="api_endpoints",
                    passed=False,
                    error=f"Missing API calls: {missing}",
                )

            return ValidationCheck(name="api_endpoints", passed=True)

        except Exception as e:
            return ValidationCheck(
                name="api_endpoints",
                passed=False,
                error=f"API check failed: {str(e)[:200]}",
            )

    async def check_user_flows(self, page: Any, user_flows: list[dict]) -> ValidationCheck:
        """Run through expected user interaction flows."""
        flow_errors = []

        for i, flow in enumerate(user_flows):
            try:
                steps = flow.get("steps", [])
                for step in steps:
                    action = step.get("action")
                    selector = step.get("selector")
                    value = step.get("value")

                    if action == "click":
                        await page.click(selector, timeout=5000)
                    elif action == "fill":
                        await page.fill(selector, value, timeout=5000)
                    elif action == "wait":
                        await page.wait_for_selector(selector, timeout=value or 5000)
                    elif action == "goto":
                        await page.goto(value, wait_until="domcontentloaded")

                    await asyncio.sleep(0.5)  # Small delay between actions

            except Exception as e:
                flow_errors.append(f"Flow {i+1} failed: {str(e)[:100]}")

        if flow_errors:
            return ValidationCheck(
                name="user_flows",
                passed=False,
                error=f"; ".join(flow_errors[:3]),
            )

        return ValidationCheck(name="user_flows", passed=True)

    async def _take_screenshot(self, page: Any) -> str | None:
        """Take a screenshot and return base64 encoded."""
        try:
            import base64

            screenshot_bytes = await page.screenshot(type="png")
            return base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")
            return None

    async def _get_logs(self, page: Any) -> dict[str, list[str]]:
        """Get console and network logs from the page."""
        return {
            "console": [],
            "network": [],
        }
