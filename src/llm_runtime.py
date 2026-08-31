"""Shared LLM setup and concurrent-response handling."""

import os
from collections.abc import Callable, Sequence
from typing import Any

from langchain_openai import ChatOpenAI

from config import RuntimePaths


def load_system_prompt(filename: str) -> str:
    """Read a prompt file from the project's prompt directory."""
    paths = RuntimePaths.from_environment()
    prompt_path = paths.project_root / "prompts" / filename
    return prompt_path.read_text(encoding="utf-8")


def create_chat_model() -> ChatOpenAI:
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

    return ChatOpenAI(
        model=os.environ["LLM_MODEL"],
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        temperature=0,
    )


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
