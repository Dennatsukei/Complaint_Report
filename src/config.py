"""Shared runtime configuration for pipeline and reporting scripts."""

from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_INPUT_DIR = "inputs/samples"
DEFAULT_RUN_ID = "sample"


def _resolve_path(project_root: Path, value: str) -> Path:
    """Resolve a project-relative or absolute path from configuration."""
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _validate_run_id(run_id: str) -> str:
    """Keep generated artifacts inside ``outputs/runs``."""
    candidate = Path(run_id)

    if not run_id or candidate.name != run_id or run_id in {".", ".."}:
        raise ValueError("RUN_ID must be a single, non-empty directory name.")

    return run_id


@dataclass(frozen=True)
class RuntimePaths:
    """Filesystem locations for one pipeline execution."""

    project_root: Path
    input_dir: Path
    run_id: str

    @classmethod
    def from_environment(cls) -> "RuntimePaths":
        project_root = Path(__file__).resolve().parent.parent
        input_dir = _resolve_path(
            project_root,
            os.getenv("INPUT_DIR", DEFAULT_INPUT_DIR),
        )
        run_id = _validate_run_id(os.getenv("RUN_ID", DEFAULT_RUN_ID))

        return cls(
            project_root=project_root,
            input_dir=input_dir,
            run_id=run_id,
        )

    @property
    def run_dir(self) -> Path:
        return self.project_root / "outputs" / "runs" / self.run_id

    @property
    def dashboard_file(self) -> Path:
        return self.project_root / "outputs" / "dashboard" / "dashboard.html"

    def stage_file(self, filename: str) -> Path:
        return self.run_dir / filename

    def ensure_run_dir(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def ensure_dashboard_dir(self) -> None:
        self.dashboard_file.parent.mkdir(parents=True, exist_ok=True)
