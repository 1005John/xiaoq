"""Common mapping contracts for expression inputs."""

from __future__ import annotations

from typing import Protocol

from .models import ExpressionIntent


class ExpressionIntentMapper(Protocol):
    """Map a product input to a canonical expression intent."""

    def resolve_intent(self, value: object) -> ExpressionIntent:
        ...
