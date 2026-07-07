"""Base abstractions for local language model integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any


class BaseLLM(ABC):
    """Contract for local language model adapters."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""

    @abstractmethod
    def stream_generate(self, prompt: str) -> Iterator[str]:
        """Stream generated text chunks from a prompt."""

    @abstractmethod
    def generate_from_template(self, template: Any, **kwargs: Any) -> str:
        """Render a prompt template and generate text from it."""
