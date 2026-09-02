"""Shared LLM setup and concurrent-response handling."""

import os
from collections.abc import Callable, Sequence
from typing import Any

from langchain_openai import ChatOpenAI

from config import RuntimePaths
from redaction import (
    MODE_OFF,
    MaskingRegistry,
    mask_text,
    resolve_mode,
)


_MASKING_ANNOUNCED = False
_SKIPPED_MESSAGE_ROLES = {"system", "tool", "function"}


def _announce_masking(mode: str) -> None:
    global _MASKING_ANNOUNCED

    if not _MASKING_ANNOUNCED:
        print(f"Outbound LLM masking enabled (mode={mode}).")
        _MASKING_ANNOUNCED = True


class MaskingChatModel:
    """Transparent ChatOpenAI wrapper that redacts outbound request text.

    Human/user messages are masked before the request is sent to the
    third-party model.  Masked tokens that appear in a response (for
    example split anchors) are translated back to the original values
    before the caller sees them, so downstream artifacts stay unchanged.

    The wrapper is duck-typed: callers only rely on ``invoke``,
    ``batch`` and ``batch_as_completed`` plus ``response.content``.
    """

    def __init__(self, inner: ChatOpenAI, mode: str) -> None:
        self._inner = inner
        self._mode = mode
        self._registry = MaskingRegistry()

    # ----------------------------------------------------------
    # Masking helpers
    # ----------------------------------------------------------

    def _mask_messages(self, messages: Sequence[Any]) -> list[Any]:
        result: list[Any] = []

        for message in messages:
            role = getattr(message, "type", None)
            content = getattr(message, "content", "")

            if (
                role in _SKIPPED_MESSAGE_ROLES
                or not isinstance(content, str)
                or not content
            ):
                result.append(message)
                continue

            masked = mask_text(
                content,
                self._registry,
                self._mode,
            )

            if masked == content:
                result.append(message)
            else:
                result.append(message.__class__(content=masked))

        return result

    def _restore_response(self, response: Any) -> Any:
        content = getattr(response, "content", "")

        if not isinstance(content, str) or not content:
            return response

        restored = self._registry.restore(content)

        if restored == content:
            return response

        try:
            return response.model_copy(
                update={"content": restored}
            )
        except (AttributeError, TypeError, ValueError):
            pass

        try:
            return response.__class__(content=restored)
        except (AttributeError, TypeError, ValueError):
            pass

        try:
            response.content = restored
            return response
        except (AttributeError, TypeError, ValueError):
            return response

    # ----------------------------------------------------------
    # ChatModel API surface used by the pipeline
    # ----------------------------------------------------------

    def invoke(
        self,
        messages,
        *,
        config=None,
        **kwargs,
    ):
        masked = self._mask_messages(messages)
        response = self._inner.invoke(
            masked,
            config=config,
            **kwargs,
        )
        return self._restore_response(response)

    def batch(
        self,
        inputs,
        *,
        config=None,
        **kwargs,
    ):
        masked_inputs = [
            self._mask_messages(messages)
            for messages in inputs
        ]
        responses = self._inner.batch(
            masked_inputs,
            config=config,
            **kwargs,
        )
        return [
            self._restore_response(response)
            for response in responses
        ]

    def batch_as_completed(
        self,
        inputs,
        *,
        config=None,
        **kwargs,
    ):
        masked_inputs = [
            self._mask_messages(messages)
            for messages in inputs
        ]

        def _generator():
            for index, response in self._inner.batch_as_completed(
                masked_inputs,
                config=config,
                **kwargs,
            ):
                yield index, self._restore_response(response)

        return _generator()


def load_system_prompt(filename: str) -> str:
    """Read a prompt file from the project's prompt directory."""
    paths = RuntimePaths.from_environment()
    prompt_path = paths.project_root / "prompts" / filename
    return prompt_path.read_text(encoding="utf-8")


def create_chat_model():
    """Create the project's deterministic DeepSeek-compatible chat client."""
    required_keys = (
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
    )
    missing_keys = [key for key in required_keys if not os.getenv(key)]

    if missing_keys:
        keys = ", ".join(missing_keys)
        raise RuntimeError(f"Missing required LLM configuration: {keys}")

    model = ChatOpenAI(
        model=os.environ["LLM_MODEL"],
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        temperature=0,
    )

    mode = resolve_mode()

    if mode == MODE_OFF:
        return model

    _announce_masking(mode)
    return MaskingChatModel(model, mode=mode)


def process_batch(
    llm: ChatOpenAI,
    messages: Sequence[Any],
    parse_response: Callable[[int, str], Any],
    *,
    max_concurrency: int,
    progress_label: str,
    finish_with_newline: bool = False,
) -> list[Any]:
    """Run an ordered batch while preserving each source item's index."""
    results: list[Any] = [None] * len(messages)
    total = len(messages)

    for completed, (index, response) in enumerate(
        llm.batch_as_completed(
            list(messages),
            config={"max_concurrency": max_concurrency},
        ),
        start=1,
    ):
        results[index] = parse_response(index, response.content)
        print(
            f"{progress_label}: {completed}/{total}",
            end="\r",
            flush=True,
        )

    if finish_with_newline:
        print()

    return results
