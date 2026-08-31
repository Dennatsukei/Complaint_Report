"""Entry point for the complaint processing pipeline with interactive setup."""

import getpass
import os
import subprocess
import sys
from pathlib import Path

from config import PROJECT_ROOT, RuntimePaths
from fields import STRUCTURED_FILE
from pipeline import (
    STAGES,
    resolve_end_from,
    resolve_start_from,
    run_pipeline,
)


DEFAULT_INPUT_DIR = "inputs/samples"
DEFAULT_RUN_ID = "sample"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

LLM_ENV_KEYS = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
)

ENV_FILE = PROJECT_ROOT / ".env"


def _read_input(prompt: str) -> str:
    """Read one line without crashing when no terminal is attached."""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def _choice(prompt: str, default: str) -> str:
    value = _read_input(prompt).lower()
    return value or default


def _current(key: str, default: str = "") -> str:
    return (os.getenv(key) or "").strip() or default


def _llm_keys_missing() -> list[str]:
    return [key for key in LLM_ENV_KEYS if not os.getenv(key)]


def _print_runtime_status() -> None:
    llm_ready = not _llm_keys_missing()

    print("\nComplaint Analysis Pipeline")
    print("=" * 72)

    try:
        paths = RuntimePaths.from_environment()
    except ValueError as exc:
        print(f"  当前环境配置有误：{exc}")
    else:
        print(f"  输入数据目录 (INPUT_DIR)  : {paths.input_dir}")
        print(f"  运行标识     (RUN_ID)     : {paths.run_id}")

    print(f"  起始阶段     (START_FROM) : {_current('START_FROM', 'extract')}")
    print(f"  结束阶段     (END_FROM)   : {_current('END_FROM', 'structure')}")
    print(f"  LLM 配置                  : {'已配置' if llm_ready else '未配置'}")
    print("=" * 72)


def _save_env_file(overrides: dict[str, str]) -> None:
    if not overrides:
        return

    lines = []
    existing: dict[str, str] = {}

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if (
                stripped
                and "=" in stripped
                and not stripped.startswith("#")
            ):
                key, _, _ = stripped.partition("=")
                existing[key.strip()] = line
            else:
                lines.append(line)

    for key, value in overrides.items():
        existing[key] = f"{key}={value}"

    lines.extend(existing.values())

    ENV_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(f"\n  配置已保存到 {ENV_FILE}")


def _prompt_llm_keys(overrides: dict[str, str]) -> None:
    missing = _llm_keys_missing()

    if not missing:
        return

    print("\n  以下 LLM 配置缺失（拆分、去重、结构化阶段需要）：")

    for key in missing:
        print(f"    - {key}")

    answer = _choice("  是否现在设置？[y/N]: ", "n")

    if answer != "y":
        return

    for key in missing:
        if key == "LLM_API_KEY":
            value = getpass.getpass("  LLM_API_KEY: ").strip()
        else:
            default = (
                DEFAULT_BASE_URL
                if key == "LLM_BASE_URL"
                else DEFAULT_MODEL
            )
            value = _read_input(f"  {key} [{default}]: ").strip()

        if value:
            os.environ[key] = value
            overrides[key] = value


def _prompt_config(overrides: dict[str, str]) -> None:
    print("\n请输入运行配置（直接回车保留当前值或默认值）：")

    input_dir = _read_input(
        f"  INPUT_DIR [{_current('INPUT_DIR', DEFAULT_INPUT_DIR)}]: "
    )

    if input_dir:
        os.environ["INPUT_DIR"] = input_dir
        overrides["INPUT_DIR"] = input_dir

    run_id = _read_input(
        f"  RUN_ID [{_current('RUN_ID', DEFAULT_RUN_ID)}]: "
    )

    if run_id:
        os.environ["RUN_ID"] = run_id
        overrides["RUN_ID"] = run_id

    start_from = _read_input(
        f"  START_FROM [{_current('START_FROM', 'extract')}]: "
    )

    if start_from:
        os.environ["START_FROM"] = start_from
        overrides["START_FROM"] = start_from

    end_from = _read_input(
        f"  END_FROM [{_current('END_FROM', 'structure')}]: "
    )

    if end_from:
        os.environ["END_FROM"] = end_from
        overrides["END_FROM"] = end_from


def _use_sample_defaults() -> None:
    os.environ["INPUT_DIR"] = DEFAULT_INPUT_DIR
    os.environ["RUN_ID"] = DEFAULT_RUN_ID
    os.environ["START_FROM"] = "extract"
    os.environ["END_FROM"] = "structure"


def _ensure_llm_configuration() -> bool:
    missing = _llm_keys_missing()

    if not missing:
        return True

    print("\n当前运行需要 LLM 配置：")

    for key in missing:
        print(f"  - {key}")

    answer = _choice(
        "是否现在设置？[y/N，直接回车则退出]: ",
        "n",
    )

    if answer == "y":
        overrides: dict[str, str] = {}
        _prompt_llm_keys(overrides)
        _save_env_file(overrides)
        return not _llm_keys_missing()

    print(
        "\n未配置 LLM，无法完成拆分、去重、结构化阶段。\n"
        "请重新运行并选择“设置环境变量后再运行”，\n"
        "或在 .env 中配置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL。"
    )

    return False


def _generate_dashboard(paths: RuntimePaths) -> None:
    structured_path = paths.stage_file(STRUCTURED_FILE)

    if not structured_path.exists():
        print(
            "\nDashboard 未生成：当前运行没有包含 structure 阶段，"
            "缺少结构化结果文件。"
        )
        return

    print("\n正在生成 Dashboard...")

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "src" / "analysis.py"),
        ],
        check=False,
    )

    if result.returncode != 0:
        print(
            "\nDashboard 生成失败，请检查结构化结果后重试。"
        )
        raise SystemExit(result.returncode)


def main() -> None:
    _print_runtime_status()

    choice = _choice(
        "\n运行方式：\n"
        "  1) 使用 sample data 跑全流程（默认）\n"
        "  2) 设置环境变量（写入 .env）后再运行\n"
        "  3) 退出\n"
        "请选择 [1/2/3]: ",
        "1",
    )

    if choice == "3":
        print("已退出。")
        return

    overrides: dict[str, str] = {}

    if choice == "2":
        _prompt_config(overrides)

        try:
            configured_start = resolve_start_from()
            resolve_end_from(configured_start)
            RuntimePaths.from_environment()
        except ValueError as exc:
            print(f"\n配置错误：{exc}")
            return

        _save_env_file(overrides)
    else:
        if choice not in {"1", "2", "3"}:
            print("\n无效选择，使用 sample data 跑全流程。")
        _use_sample_defaults()
        print("\n已选择 sample data 全流程。")

    _print_runtime_status()

    try:
        start_from = resolve_start_from()
        end_from = resolve_end_from(start_from)
    except ValueError as exc:
        print(f"\n配置错误：{exc}")
        return

    start_index = STAGES.index(start_from)
    end_index = STAGES.index(end_from)
    needs_llm = any(
        start_index <= STAGES.index(stage) <= end_index
        for stage in ("split", "dedup", "structure")
    )

    if needs_llm and not _ensure_llm_configuration():
        return

    paths = RuntimePaths.from_environment()
    run_pipeline(paths)
    _generate_dashboard(paths)


if __name__ == "__main__":
    main()
