"""Prompt template loading helpers."""

from __future__ import annotations

from pathlib import Path

from langchain_core.prompts import PromptTemplate


class PromptTemplateLoader:
    """Loads prompt files and converts them into LangChain prompt templates."""

    def __init__(self, prompt_dir: Path) -> None:
        self.prompt_dir = prompt_dir

    def load(self, template_name: str) -> PromptTemplate:
        """Load a prompt file by name and return it as a LangChain template."""
        template_path = self.prompt_dir / template_name
        template_text = template_path.read_text(encoding="utf-8")
        return PromptTemplate.from_template(template_text)
