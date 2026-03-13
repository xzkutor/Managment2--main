"""pricewatch.scrape.registry — Runner dispatch registry.

Separate from pricewatch.core.registry (which handles shop/store plugins).
This registry is only concerned with mapping runner_type strings to
BaseRunner classes for scheduler dispatch.
"""
from __future__ import annotations

from typing import Type

from pricewatch.scrape.contracts import BaseRunner

_REGISTRY: dict[str, Type[BaseRunner]] = {}


def register_runner(runner_cls: Type[BaseRunner]) -> Type[BaseRunner]:
    """Register a runner class by its runner_type.

    Can be used as a class decorator::

        @register_runner
        class MyRunner(BaseRunner):
            runner_type = "my_runner"
    """
    if not runner_cls.runner_type:
        raise ValueError(
            f"Runner {runner_cls.__name__} must define a non-empty runner_type"
        )
    _REGISTRY[runner_cls.runner_type] = runner_cls
    return runner_cls


def get_runner(runner_type: str) -> Type[BaseRunner]:
    """Return the runner class for *runner_type*.

    Raises KeyError if the type is not registered.
    """
    try:
        return _REGISTRY[runner_type]
    except KeyError:
        raise KeyError(
            f"No runner registered for runner_type={runner_type!r}. "
            f"Registered types: {sorted(_REGISTRY.keys())}"
        )


def list_runner_types() -> list[str]:
    """Return sorted list of all registered runner_type strings."""
    return sorted(_REGISTRY.keys())

