"""Executable bounded runtime demonstration for MIND-Lite."""

from __future__ import annotations

from src.core.observation import Observation
from src.core.runtime import RuntimeController


def main() -> None:
    """Run a small bounded demonstration and display its final state."""

    initial_state = RuntimeController.initialize()
    initial_observation = Observation(
        source="demo",
        content={"message": "Start bounded MIND-Lite runtime demonstration"},
    )
    final_state = RuntimeController.run(
        initial_state,
        initial_observation,
        max_cycles=3,
    )
    print(final_state.to_dict())


if __name__ == "__main__":
    main()
