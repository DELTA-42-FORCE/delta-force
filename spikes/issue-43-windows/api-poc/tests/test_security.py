import base64

import pytest

from spike_runtime.security import (
    RuntimeAccessDenied,
    RuntimeConfigurationError,
    RuntimeGate,
    validate_urlsafe_token,
)


def token_for(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class ManualClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_token_must_decode_to_at_least_256_bits() -> None:
    assert validate_urlsafe_token(token_for(b"s" * 32))
    with pytest.raises(RuntimeConfigurationError):
        validate_urlsafe_token(token_for(b"s" * 31))


def test_bootstrap_is_one_shot_and_capability_is_execution_scoped() -> None:
    bootstrap = token_for(b"bootstrap" * 4)
    first_capability = token_for(b"capability-one" * 3)
    second_capability = token_for(b"capability-two" * 3)
    first_gate = RuntimeGate(
        bootstrap,
        clock=lambda: 100.0,
        capability_factory=lambda: first_capability,
    )
    second_gate = RuntimeGate(
        bootstrap,
        clock=lambda: 100.0,
        capability_factory=lambda: second_capability,
    )

    assert first_gate.exchange(bootstrap) == first_capability
    assert first_gate.authorizes(first_capability)
    assert second_gate.exchange(bootstrap) == second_capability
    assert second_gate.authorizes(second_capability)
    assert not second_gate.authorizes(first_capability)

    with pytest.raises(RuntimeAccessDenied):
        first_gate.exchange(bootstrap)


def test_wrong_bootstrap_does_not_consume_the_valid_one() -> None:
    bootstrap = token_for(b"bootstrap" * 4)
    capability = token_for(b"capability" * 4)
    gate = RuntimeGate(
        bootstrap,
        clock=lambda: 100.0,
        capability_factory=lambda: capability,
    )

    with pytest.raises(RuntimeAccessDenied):
        gate.exchange(token_for(b"incorrect" * 4))

    assert gate.exchange(bootstrap) == capability


def test_bootstrap_expiration_uses_an_injected_clock() -> None:
    clock = ManualClock()
    bootstrap = token_for(b"bootstrap" * 4)
    gate = RuntimeGate(bootstrap, clock=clock, ttl_seconds=5.0)
    clock.now = 105.0

    with pytest.raises(RuntimeAccessDenied):
        gate.exchange(bootstrap)


@pytest.mark.parametrize("ttl_seconds", [float("nan"), float("inf"), 0.0, -1.0])
def test_bootstrap_ttl_must_be_finite_and_positive(ttl_seconds: float) -> None:
    with pytest.raises(RuntimeConfigurationError):
        RuntimeGate(token_for(b"bootstrap" * 4), ttl_seconds=ttl_seconds)
