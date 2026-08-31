"""Entry point for the complaint processing pipeline."""

from config import RuntimePaths
from pipeline import run_pipeline


def main() -> None:
    paths = RuntimePaths.from_environment()
    run_pipeline(paths)


if __name__ == "__main__":
    main()
