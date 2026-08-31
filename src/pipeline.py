"""Stage orchestration for the complaint processing pipeline."""

import os

import pandas as pd

from config import RuntimePaths
from dedup_resolver import DedupResolver
from deduplicator import ComplaintDeduplicator
from fields import METADATA_COLUMNS, STRUCTURED_METADATA_COLUMNS
from filter import filter_positive
from ingestion import ComplaintAggregator, ComplaintExtractor
from llm_dedup import LLMDeduplicator
from split import LLMSplit
from structurer import LLMStructurer
from transforms import normalize_dataframe, process_record


STAGES = [
    "extract",
    "process",
    "split",
    "normalize",
    "dedup",
    "filter",
    "structure",
]


def resolve_start_from() -> str:
    start_from = os.getenv("START_FROM", "extract")

    if start_from not in STAGES:
        raise ValueError(
            f"Invalid START_FROM: {start_from}"
        )

    return start_from


def _load_stage(paths, filename, label):
    df = pd.read_csv(
        paths.stage_file(filename),
        encoding="utf-8-sig",
    )

    print(
        f"Loaded {label}: "
        f"{len(df)} records."
    )

    return df


def _save_stage(df, paths, filename, message):
    df.to_csv(
        paths.stage_file(filename),
        index=False,
        encoding="utf-8-sig",
    )

    print(message)

    return df


# =========================================================
# Stages
# =========================================================

def extract_stage(paths):
    aggregator = ComplaintAggregator()

    for folder_name, extract_method in (
        ("daily_reports", "extract_daily"),
        ("weekly_reports", "extract_weekly"),
        ("monthly_reports", "extract_monthly"),
    ):
        folder = paths.input_dir / folder_name

        for item in os.listdir(folder):

            path = folder / item

            if not path.is_file():
                continue

            extractor = ComplaintExtractor(path)

            report = getattr(extractor, extract_method)()

            aggregator.add_report(report)

    platform_path = paths.input_dir / "platform_reviews"

    for item in os.listdir(platform_path):

        path = platform_path / item

        if not path.is_file():
            continue

        extractor = ComplaintExtractor(path)

        reviews = extractor.extract_reviews()

        aggregator.add_platform_reviews(reviews)

    raw_df = aggregator.to_dataframe()

    return _save_stage(
        raw_df,
        paths,
        "aggregated.csv",
        f"Extracted and aggregated: "
        f"{len(raw_df)} records.",
    )


def process_stage(paths, raw_df):
    processed_df = raw_df.apply(
        process_record,
        axis=1,
        result_type="expand",
    )

    processed_df.insert(
        0,
        "record_id",
        range(
            1,
            len(processed_df) + 1,
        ),
    )

    return _save_stage(
        processed_df,
        paths,
        "processed.csv",
        f"Processed: "
        f"{len(processed_df)} records.",
    )


def split_stage(paths, processed_df):
    splitter = LLMSplit()

    contents = processed_df[
        "raw_content"
    ].tolist()

    print(
        f"Splitting "
        f"{len(contents)} complaints..."
    )

    parts_list = splitter.split_batch(
        contents,
        max_concurrency=50,
    )

    split_records = []

    for (_, record), parts in zip(
        processed_df.iterrows(),
        parts_list,
    ):

        metadata = {
            column: record[column]
            for column in METADATA_COLUMNS
        }

        if parts == [None]:

            split_records.append({
                **metadata,
                "complaint_id": (
                    f"{record['record_id']}-1"
                ),
                "record_id": record["record_id"],
                "content": record["raw_content"],
                "raw_content": record["raw_content"],
            })

        else:

            for j, content in enumerate(
                parts,
                start=1,
            ):

                split_records.append({
                    **metadata,
                    "complaint_id": (
                        f"{record['record_id']}-{j}"
                    ),
                    "record_id": record["record_id"],
                    "content": content,
                    "raw_content": record["raw_content"],
                })

    split_df = pd.DataFrame(
        split_records
    )

    return _save_stage(
        split_df,
        paths,
        "split.csv",
        f"Split: "
        f"{len(split_df)} complaints.",
    )


def normalize_stage(paths, split_df):
    normalized_df = normalize_dataframe(
        split_df
    )

    return _save_stage(
        normalized_df,
        paths,
        "normalized.csv",
        f"Normalized: "
        f"{len(normalized_df)} complaints.",
    )


def dedup_stage(paths, normalized_df):
    deduplicator = ComplaintDeduplicator(
        normalized_df
    )

    dedup_df = (
        deduplicator.exact_deduplicate()
    )

    candidates_df = (
        deduplicator.generate_candidates()
    )

    _save_stage(
        candidates_df,
        paths,
        "dedup_candidates.csv",
        f"Dedup candidates: "
        f"{len(candidates_df)} pairs.",
    )

    print(
        f"Complaints after exact dedup: "
        f"{len(dedup_df)}"
    )

    llm_deduplicator = LLMDeduplicator()

    pairs = []

    for _, candidate in (
        candidates_df.iterrows()
    ):

        complaint_a = dedup_df[
            dedup_df["complaint_id"]
            == candidate["complaint_a"]
        ].iloc[0]

        complaint_b = dedup_df[
            dedup_df["complaint_id"]
            == candidate["complaint_b"]
        ].iloc[0]

        pairs.append(
            (
                complaint_a,
                complaint_b,
            )
        )

    print(
        f"Starting LLM dedup: "
        f"{len(pairs)} pairs..."
    )

    if pairs:

        same_events = (
            llm_deduplicator
            .is_duplicate_batch(
                pairs,
                max_concurrency=50,
            )
        )

        llm_results_df = pd.DataFrame({
            "complaint_a": candidates_df[
                "complaint_a"
            ].values,

            "complaint_b": candidates_df[
                "complaint_b"
            ].values,

            "same_event": same_events,
        })

    else:

        llm_results_df = pd.DataFrame(
            columns=[
                "complaint_a",
                "complaint_b",
                "same_event",
            ]
        )

    _save_stage(
        llm_results_df,
        paths,
        "llm_dedup_results.csv",
        f"LLM dedup completed: "
        f"{len(llm_results_df)} pairs.",
    )

    print(
        f"LLM YES: "
        f"{llm_results_df['same_event'].sum()}"
    )

    print(
        f"LLM NO: "
        f"{(~llm_results_df['same_event']).sum()}"
    )

    resolver = DedupResolver(
        dedup_df,
        llm_results_df,
    )

    dedup_audit_df, removed_ids = (
        resolver.resolve()
    )

    deduplicated_df = (
        resolver.get_unique(
            removed_ids
        )
    )

    _save_stage(
        dedup_audit_df,
        paths,
        "dedup_audit.csv",
        f"Dedup audit records: "
        f"{len(dedup_audit_df)}",
    )

    _save_stage(
        deduplicated_df,
        paths,
        "deduplicated.csv",
        f"Final complaints: "
        f"{len(deduplicated_df)}",
    )

    print(
        f"Duplicates resolved: "
        f"{len(removed_ids)}"
    )

    if not dedup_audit_df.empty:

        print(
            "\nDedup reasons:"
        )

        print(
            dedup_audit_df[
                "reason"
            ]
            .value_counts()
            .to_string()
        )

    # Integrity check
    assert (
        len(deduplicated_df)
        + len(removed_ids)
        == len(dedup_df)
    )

    assert set(
        deduplicated_df["complaint_id"]
    ).isdisjoint(
        removed_ids
    )

    if not dedup_audit_df.empty:

        assert set(
            dedup_audit_df["removed"]
        ) == removed_ids

    print(
        "Dedup integrity check: OK"
    )

    return deduplicated_df


def filter_stage(paths, deduplicated_df):
    filtered_df = filter_positive(
        deduplicated_df
    )

    return _save_stage(
        filtered_df,
        paths,
        "filtered.csv",
        f"Filtered: "
        f"{len(filtered_df)} records.",
    )


def structure_stage(paths, filtered_df):
    structurer = LLMStructurer()

    contents = filtered_df[
        "content"
    ].tolist()

    print(
        f"Starting Structuring: "
        f"{len(contents)} complaints..."
    )

    results = structurer.structure_batch(
        contents,
        max_concurrency=50,
    )

    structured_records = []

    for (_, record), result in zip(
        filtered_df.iterrows(),
        results,
    ):

        if result is None:

            print(
                "\n"
                + "=" * 80
            )

            print(
                "STRUCTURER RETURNED NONE: "
                f"{record['complaint_id']}"
            )

            print(
                "=" * 80
            )

            print(
                record["content"]
            )

            continue

        structured_records.append({
            **{
                column: record[column]
                for column in STRUCTURED_METADATA_COLUMNS
            },
            **result,
        })

    structured_df = pd.DataFrame(
        structured_records
    )

    _save_stage(
        structured_df,
        paths,
        "structured.csv",
        f"Structured complaints: "
        f"{len(structured_df)}",
    )

    structured_issue_count = sum(
        len(result.get("issues", []))
        for result in results
        if isinstance(result, dict)
    )

    print(
        f"Structured issues: "
        f"{structured_issue_count}"
    )

    return structured_df


# =========================================================
# Orchestration
# =========================================================

def run_pipeline(paths=None):
    paths = paths or RuntimePaths.from_environment()
    paths.ensure_run_dir()

    start_from = resolve_start_from()
    start_index = STAGES.index(start_from)

    if start_index <= STAGES.index("extract"):
        raw_df = extract_stage(paths)
    else:
        raw_df = _load_stage(
            paths,
            "aggregated.csv",
            "aggregated.csv",
        )

    if start_index <= STAGES.index("process"):
        processed_df = process_stage(paths, raw_df)
    else:
        processed_df = _load_stage(
            paths,
            "processed.csv",
            "processed.csv",
        )

    if start_index <= STAGES.index("split"):
        split_df = split_stage(paths, processed_df)
    else:
        split_df = _load_stage(
            paths,
            "split.csv",
            "split.csv",
        )

    if start_index <= STAGES.index("normalize"):
        normalized_df = normalize_stage(paths, split_df)
    else:
        normalized_df = _load_stage(
            paths,
            "normalized.csv",
            "normalized.csv",
        )

    if start_index <= STAGES.index("dedup"):
        deduplicated_df = dedup_stage(paths, normalized_df)
    else:
        deduplicated_df = _load_stage(
            paths,
            "deduplicated.csv",
            "deduplicated.csv",
        )

    if start_index <= STAGES.index("filter"):
        filtered_df = filter_stage(paths, deduplicated_df)
    else:
        filtered_df = _load_stage(
            paths,
            "filtered.csv",
            "filtered.csv",
        )

    if start_index <= STAGES.index("structure"):
        structured_df = structure_stage(paths, filtered_df)
    else:
        structured_df = _load_stage(
            paths,
            "structured.csv",
            "structured.csv",
        )

    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)

    print(
        f"Final structured complaints: "
        f"{len(structured_df)}"
    )

    print(
        f"Run output directory: "
        f"{paths.run_dir}"
    )

    return structured_df
