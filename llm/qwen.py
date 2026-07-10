"""Local HuggingFace Qwen integration with optional streaming."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import nullcontext
import gc
from threading import Thread
from typing import Any

from llm.base import BaseLLM
from utils.prompt_loader import PromptTemplateLoader


class QwenLLM(BaseLLM):
    """Local Qwen wrapper used for SQL and summary generation."""

    def __init__(
        self,
        model_name: str,
        *,
        temperature: float = 0.1,
        context_window: int = 8192,
        max_new_tokens: int = 512,
        device_map: str = "auto",
        gpu_memory_limit: str | None = "16GiB",
        tokenizer: Any | None = None,
        model: Any | None = None,
        prompt_loader: PromptTemplateLoader | None = None,
    ) -> None:
        self.model_name = model_name
        self.temperature = temperature
        self.context_window = context_window
        self.max_new_tokens = max_new_tokens
        self.device_map = device_map
        self.gpu_memory_limit = gpu_memory_limit
        self._tokenizer = tokenizer
        self._model = model
        self.prompt_loader = prompt_loader

    @property
    def tokenizer(self) -> Any:
        """Lazily load the HuggingFace tokenizer only when generation is requested."""
        if self._tokenizer is None:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
            )
            if self._tokenizer.pad_token_id is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token
        return self._tokenizer

    @property
    def model(self) -> Any:
        """Lazily load the local HuggingFace causal language model."""
        if self._model is None:
            from transformers import AutoModelForCausalLM

            load_kwargs = {
                "torch_dtype": "auto",
                "device_map": self.device_map,
                "low_cpu_mem_usage": True,
                "trust_remote_code": True,
            }
            if self.gpu_memory_limit and self.device_map != "cpu":
                load_kwargs["max_memory"] = self._build_max_memory()

            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                **load_kwargs,
            )
            self._model.eval()
        return self._model

    def generate(self, prompt: str) -> str:
        """Generate a full completion for a prompt using local HuggingFace inference."""
        import torch

        tokenized_inputs = self._prepare_inputs(prompt)
        inference_context = (
            torch.inference_mode()
            if hasattr(torch, "inference_mode")
            else torch.no_grad()
        )
        with inference_context:
            generated_ids = self.model.generate(
                **tokenized_inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                do_sample=self.temperature > 0,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        new_token_ids = generated_ids[0][tokenized_inputs["input_ids"].shape[-1] :]
        return self.tokenizer.decode(new_token_ids, skip_special_tokens=True).strip()

    def stream_generate(self, prompt: str) -> Iterator[str]:
        """Stream completion chunks using a HuggingFace text streamer."""
        from transformers import TextIteratorStreamer

        tokenized_inputs = self._prepare_inputs(prompt)
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        generation_kwargs = {
            **tokenized_inputs,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "do_sample": self.temperature > 0,
            "pad_token_id": self.tokenizer.pad_token_id,
            "streamer": streamer,
        }
        thread = Thread(
            target=self._generate_with_inference_mode,
            kwargs=generation_kwargs,
            daemon=True,
        )
        thread.start()
        for chunk in streamer:
            if chunk:
                yield chunk
        thread.join()

    def generate_from_template(self, template: Any, **kwargs: Any) -> str:
        """Render a prompt template and run standard generation on the result."""
        prompt_value = template.format(**kwargs)
        return self.generate(prompt_value)

    def generate_from_prompt_file(self, template_name: str, **kwargs: Any) -> str:
        """Load a named prompt template from disk, render it, and generate text."""
        if self.prompt_loader is None:
            raise ValueError("Prompt loader is not configured for QwenLLM.")
        template = self.prompt_loader.load(template_name)
        return self.generate_from_template(template, **kwargs)

    def _prepare_inputs(self, prompt: str) -> dict[str, Any]:
        """Tokenize the prompt and trim it so generation stays inside the context window."""
        import torch

        encoded = self.tokenizer(prompt, return_tensors="pt", truncation=False)
        max_prompt_tokens = max(1, self.context_window - self.max_new_tokens)
        input_ids = encoded["input_ids"][:, -max_prompt_tokens:]
        attention_mask = encoded["attention_mask"][:, -max_prompt_tokens:]

        model_device = getattr(self.model, "device", torch.device("cpu"))
        return {
            "input_ids": input_ids.to(model_device),
            "attention_mask": attention_mask.to(model_device),
        }

    def close(self) -> None:
        """Release model/tokenizer references and ask CUDA to free cached memory."""
        self._model = None
        self._tokenizer = None
        gc.collect()
        self._clear_cuda_cache()

    def _build_max_memory(self) -> dict[Any, str]:
        """Build a per-device Transformers max_memory map."""
        import torch

        if not torch.cuda.is_available():
            return {"cpu": "64GiB"}
        max_memory: dict[Any, str] = {"cpu": "64GiB"}
        for device_index in range(torch.cuda.device_count()):
            max_memory[device_index] = self.gpu_memory_limit
        return max_memory

    def _generate_with_inference_mode(self, **generation_kwargs: Any) -> None:
        """Run generation without autograd inside the streaming worker."""
        import torch

        inference_context = (
            torch.inference_mode()
            if hasattr(torch, "inference_mode")
            else torch.no_grad()
        )
        with inference_context:
            self.model.generate(**generation_kwargs)

    def _clear_cuda_cache(self) -> None:
        """Best-effort CUDA cache cleanup after the model is released."""
        try:
            import torch
        except ImportError:
            return
        if torch.cuda.is_available():
            with nullcontext():
                torch.cuda.empty_cache()
                if hasattr(torch.cuda, "ipc_collect"):
                    torch.cuda.ipc_collect()
