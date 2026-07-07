"""Prompt version tracking helpers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PromptVersion:
    """Represents one prompt template version."""

    name: str
    sha256: str


class PromptVersionManager:
    """Resolves stable prompt versions from prompt files."""

    def __init__(self, prompt_dir: Path) -> None:
        self.prompt_dir = prompt_dir

    def resolve(self, template_name: str) -> PromptVersion:
        """Compute a hash-based version for one prompt template file."""
        template_path = self.prompt_dir / template_name
        content = template_path.read_text(encoding="utf-8")
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return PromptVersion(name=template_name, sha256=sha256)
