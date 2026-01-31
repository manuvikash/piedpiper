"""Circuit breaker system.

Owner: Person 3 (Infrastructure)

Protects against runaway costs, stuck loops, and systematic failures.
Each breaker has a threshold and triggers an action when tripped.
"""

from __future__ import annotations


class CircuitBreakerTripped(Exception):
    """Raised when a circuit breaker is tripped."""

    def __init__(self, message: str, action: str):
        super().__init__(message)
        self.action = action


class ConsecutiveFailureBreaker:
    """Trips after N consecutive expert answer failures."""

    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self.consecutive_failures = 0

    def record_outcome(self, worker_succeeded: bool):
        if not worker_succeeded:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0

        if self.consecutive_failures >= self.threshold:
            raise CircuitBreakerTripped(
                "Expert answers not resolving issues - possible systematic problem",
                action="PAUSE_AND_ALERT",
            )


class RepetitionBreaker:
    """Detects if workers are stuck in action loops."""

    def __init__(self, threshold: int = 3):
        self.threshold = threshold

    def detect(self, action_signatures: list[str]) -> bool:
        recent = action_signatures[-10:]
        if len(set(recent)) < self.threshold:
            raise CircuitBreakerTripped(
                f"Worker stuck in repetition loop ({len(set(recent))} unique actions in last 10)",
                action="RESET_WORKER",
            )
        return False


class CostSpikeBreaker:
    """Detects unusual cost rate spikes."""

    def __init__(self, max_multiplier: float = 2.0):
        self.max_multiplier = max_multiplier
        self.baseline: float | None = None

    def check(self, current_cost_rate: float):
        if self.baseline is None:
            self.baseline = current_cost_rate
            return

        if current_cost_rate > self.baseline * self.max_multiplier:
            raise CircuitBreakerTripped(
                f"Cost spike detected: {current_cost_rate:.2f}x baseline",
                action="THROTTLE",
            )


class TimeoutBreaker:
    """Trips if total session exceeds max duration."""

    def __init__(self, max_minutes: int = 60):
        self.max_minutes = max_minutes

    def check(self, elapsed_minutes: float):
        if elapsed_minutes > self.max_minutes:
            raise CircuitBreakerTripped(
                f"Session exceeded {self.max_minutes} minute limit",
                action="SKIP_TO_REPORT",
            )


class NoProgressBreaker:
    """Trips if no progress across all workers for N minutes."""

    def __init__(self, minutes: int = 15):
        self.minutes = minutes

    def check(self, minutes_without_any_progress: float):
        if minutes_without_any_progress > self.minutes:
            raise CircuitBreakerTripped(
                f"No progress for {self.minutes} minutes",
                action="ESCALATE_TO_HUMAN",
            )


class CircuitBreakerSystem:
    """Aggregates all circuit breakers."""

    def __init__(self):
        self.expert_loop = ConsecutiveFailureBreaker(threshold=5)
        self.repetition = RepetitionBreaker(threshold=3)
        self.cost_spike = CostSpikeBreaker(max_multiplier=2.0)
        self.timeout = TimeoutBreaker(max_minutes=60)
        self.no_progress = NoProgressBreaker(minutes=15)
