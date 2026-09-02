"""Stage orchestration for the complaint processing pipeline."""

import ast
import json
import os
from datetime import datetime

import pandas as pd

from config import RuntimePaths
from dedup_resolver import DedupResolver
from deduplicator import ComplaintDeduplicator
from fields import (
    ALL_ARTIFACTS,
    DEDUP_AUDIT_FILE,
    DEDUP_CANDIDATES_FILE,
    DEDUPLICATED_FILE,
    FILTER_AUDIT_FILE,
    FILTERED_FILE,
    INGESTED_FILE,
    ISSUE_REVIEW_FILE,
    METADATA_COLUMNS,
    NORMALIZED_FILE,
    PREPARED_FILE,
    REVIEW_DEDUP_FILE,
    REVIEW_ISSUE_FILE,
    REVIEW_NO_ISSUE_FILE,
    REVIEW_SPLIT_FILE,
    RUN_SUMMARY_FILE,
    SPLIT_AUDIT_FILE,
    SPLIT_COMPLAINTS_FILE,
    STRUCTURED_FILE,
    STRUCTURED_METADATA_COLUMNS,
)
from filter import filter_positive_audited
from ingestion import ComplaintAggregator, ComplaintExtractor
from llm_dedup import LLMDeduplicator
from redaction import resolve_mode
from review_reports import write_review_reports
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


def resolve_end_from(start_from: str) -> str:
    end_from = os.getenv("END_FROM", STAGES[-1])

    if end_from not in STAGES:
        raise ValueError(
            f"Invalid END_FROM: {end_from}"
        )

    if STAGES.index(end_from) < STAGES.index(start_from):
        raise ValueError(
            "END_FROM must not be earlier than START_FROM"
        )

    return end_from


def _load_stage(paths, stage_name, filename):
    path = paths.stage_file(filename)

    if not path.exists():
        raise FileNotFoundError(
            f"Missing upstream artifact for stage "
            f"'{stage_name}'.\n"
            f"Expected file: {path}\n"
            f"No upstream outputs exist in this run "
            f"directory. Run the full pipeline first to "
            f"generate them, for example:\n"
            f"  $env:START_FROM = 'extract'; "
            f"$env:END_FROM = 'structure'"
        )

    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
    )

    print(
        f"Loaded {stage_name}: "
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
        INGESTED_FILE,
        f"Ingested and aggregated: "
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
        PREPARED_FILE,
        f"Prepared: "
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

    details_list = splitter.split_batch_audited(
        contents,
        max_concurrency=50,
    )

    split_records = []
    audit_records = []

    for (_, record), details in zip(
        processed_df.iterrows(),
        details_list,
    ):

        parts = details["parts"]
        anchors = details["anchors"]

        if parts == [None]:
            parts = [record["raw_content"]]

        metadata = {
            column: record[column]
            for column in METADATA_COLUMNS
        }

        for j, content in enumerate(
            parts,
            start=1,
        ):

            split_records.append({
                **metadata,
                "source_complaint_id": record["complaint_id"],
                "complaint_id": (
                    f"{record['record_id']}-{j}"
                ),
                "record_id": record["record_id"],
                "content": content,
                "raw_content": record["raw_content"],
            })

        audit_records.append({
            "record_id": record["record_id"],
            "source_complaint_id": record["complaint_id"],
            "source_file": record["source_file"],
            "report_type": record["report_type"],
            "incident_date": record["incident_date"],
            "decision": (
                "split"
                if len(parts) > 1
                else "no_split"
            ),
            "part_count": len(parts),
            "anchors": json.dumps(
                anchors,
                ensure_ascii=False,
            ),
            "parts": json.dumps(
                parts,
                ensure_ascii=False,
            ),
            "raw_content": record["raw_content"],
        })

    split_df = pd.DataFrame(
        split_records
    )

    audit_df = pd.DataFrame(
        audit_records
    )

    _save_stage(
        split_df,
        paths,
        SPLIT_COMPLAINTS_FILE,
        f"Split: "
        f"{len(split_df)} complaints.",
    )

    _save_stage(
        audit_df,
        paths,
        SPLIT_AUDIT_FILE,
        f"Split audit: "
        f"{len(audit_df)} records.",
    )

    return split_df


def normalize_stage(paths, split_df):
    normalized_df = normalize_dataframe(
        split_df
    )

    return _save_stage(
        normalized_df,
        paths,
        NORMALIZED_FILE,
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

    else:

        same_events = []

    candidates_df = candidates_df.copy()
    candidates_df["same_event"] = same_events

    _save_stage(
        candidates_df,
        paths,
        DEDUP_CANDIDATES_FILE,
        f"Dedup candidates: "
        f"{len(candidates_df)} pairs.",
    )

    llm_results_df = (
        candidates_df[
            [
                "complaint_a",
                "complaint_b",
                "same_event",
            ]
        ].copy()
        if not candidates_df.empty
        else pd.DataFrame(
            columns=[
                "complaint_a",
                "complaint_b",
                "same_event",
            ]
        )
    )

    llm_yes = int(
        llm_results_df["same_event"].sum()
    )

    llm_no = int(
        (~llm_results_df["same_event"]).sum()
    )

    print(
        f"LLM dedup completed: "
        f"{len(llm_results_df)} pairs."
    )

    print(
        f"LLM YES: {llm_yes}"
    )

    print(
        f"LLM NO: {llm_no}"
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
        DEDUP_AUDIT_FILE,
        f"Dedup audit records: "
        f"{len(dedup_audit_df)}",
    )

    _save_stage(
        deduplicated_df,
        paths,
        DEDUPLICATED_FILE,
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

    stats = {
        "candidates": len(candidates_df),
        "llm_yes": llm_yes,
        "llm_no": llm_no,
    }

    return deduplicated_df, stats


def filter_stage(paths, deduplicated_df):
    filtered_df, audit_df = (
        filter_positive_audited(
            deduplicated_df
        )
    )

    _save_stage(
        filtered_df,
        paths,
        FILTERED_FILE,
        f"Filtered: "
        f"{len(filtered_df)} records.",
    )

    _save_stage(
        audit_df,
        paths,
        FILTER_AUDIT_FILE,
        f"Filter audit: "
        f"{len(audit_df)} records.",
    )

    return filtered_df


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
        STRUCTURED_FILE,
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


def _parse_issues(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return []

    return []


def issue_review_stage(paths, structured_df, filtered_df):
    content_by_id = dict(
        zip(
            filtered_df["complaint_id"],
            filtered_df["content"],
        )
    )

    review_records = []

    for _, row in structured_df.iterrows():

        issues = _parse_issues(
            row.get("issues")
        )

        issue_count = len(issues)

        for issue in issues:

            review_records.append({
                "complaint_id": row["complaint_id"],
                "record_id": row["record_id"],
                "source_complaint_id": (
                    row.get("source_complaint_id")
                ),
                "incident_date": row.get(
                    "incident_date"
                ),
                "source": row.get("source"),
                "source_file": row.get(
                    "source_file"
                ),
                "report_type": row.get(
                    "report_type"
                ),
                "platform": row.get("platform"),
                "score": row.get("score"),
                "room_type": row.get("room_type"),
                "category": issue.get("category"),
                "subcategory": issue.get(
                    "subcategory"
                ),
                "responsible_department": issue.get(
                    "responsible_department"
                ),
                "primary": issue.get("primary"),
                "issue_count": issue_count,
                "weight": (
                    1 / issue_count
                    if issue_count
                    else 0
                ),
                "content": content_by_id.get(
                    row["complaint_id"]
                ),
            })

    review_df = pd.DataFrame(
        review_records
    )

    _save_stage(
        review_df,
        paths,
        ISSUE_REVIEW_FILE,
        f"Issue review rows: "
        f"{len(review_df)}.",
    )

    return review_df


def write_run_summary(paths, start_from, end_from, counts):
    summary = {
        "run_id": paths.run_id,
        "input_dir": str(paths.input_dir),
        "start_from": start_from,
        "end_from": end_from,
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "llm_model": os.getenv(
            "LLM_MODEL",
            "unknown",
        ),
        "masking_mode": resolve_mode(),
        "counts": counts,
        "artifacts": sorted(
            name
            for name in ALL_ARTIFACTS
            if (
                paths.run_dir / name
            ).exists()
        ),
    }

    summary_path = (
        paths.run_dir / RUN_SUMMARY_FILE
    )

    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Run summary saved: "
        f"{summary_path}"
    )


# =========================================================
# Orchestration
# =========================================================

def run_pipeline(paths=None):
    paths = paths or RuntimePaths.from_environment()
    paths.ensure_run_dir()

    start_from = resolve_start_from()
    end_from = resolve_end_from(start_from)
    start_index = STAGES.index(start_from)
    end_index = STAGES.index(end_from)

    if start_index <= STAGES.index("extract") <= end_index:
        raw_df = extract_stage(paths)
    elif STAGES.index("extract") < start_index:
        raw_df = _load_stage(
            paths,
            "extract",
            INGESTED_FILE,
        )
    else:
        raw_df = None

    if start_index <= STAGES.index("process") <= end_index:
        processed_df = process_stage(paths, raw_df)
    elif STAGES.index("process") < start_index:
        processed_df = _load_stage(
            paths,
            "process",
            PREPARED_FILE,
        )
    else:
        processed_df = None

    if start_index <= STAGES.index("split") <= end_index:
        split_df = split_stage(paths, processed_df)
    elif STAGES.index("split") < start_index:
        split_df = _load_stage(
            paths,
            "split",
            SPLIT_COMPLAINTS_FILE,
        )
    else:
        split_df = None

    write_review_reports(
        paths,
        targets={REVIEW_SPLIT_FILE},
    )

    if start_index <= STAGES.index("normalize") <= end_index:
        normalized_df = normalize_stage(paths, split_df)
    elif STAGES.index("normalize") < start_index:
        normalized_df = _load_stage(
            paths,
            "normalize",
            NORMALIZED_FILE,
        )
    else:
        normalized_df = None

    if start_index <= STAGES.index("dedup") <= end_index:
        deduplicated_df, dedup_stats = (
            dedup_stage(paths, normalized_df)
        )
    elif STAGES.index("dedup") < start_index:
        deduplicated_df = _load_stage(
            paths,
            "dedup",
            DEDUPLICATED_FILE,
        )
        dedup_stats = {}
    else:
        deduplicated_df = None
        dedup_stats = {}

    write_review_reports(
        paths,
        targets={REVIEW_DEDUP_FILE},
    )

    if start_index <= STAGES.index("filter") <= end_index:
        filtered_df = filter_stage(
            paths,
            deduplicated_df,
        )
    elif STAGES.index("filter") < start_index:
        filtered_df = _load_stage(
            paths,
            "filter",
            FILTERED_FILE,
        )
    else:
        filtered_df = None

    if start_index <= STAGES.index("structure") <= end_index:
        structured_df = structure_stage(
            paths,
            filtered_df,
        )
    elif STAGES.index("structure") < start_index:
        structured_df = _load_stage(
            paths,
            "structure",
            STRUCTURED_FILE,
        )
    else:
        structured_df = None

    write_review_reports(
        paths,
        targets={REVIEW_NO_ISSUE_FILE},
    )

    if (
        structured_df is not None
        and filtered_df is not None
    ):
        issue_review_df = issue_review_stage(
            paths,
            structured_df,
            filtered_df,
        )
    else:
        issue_review_df = pd.DataFrame()

    write_review_reports(
        paths,
        targets={REVIEW_ISSUE_FILE},
    )

    counts = {}

    if raw_df is not None:
        counts["ingested"] = len(raw_df)

    if processed_df is not None:
        counts["prepared"] = len(processed_df)

    if split_df is not None:
        counts["split"] = len(split_df)

    if normalized_df is not None:
        counts["normalized"] = len(normalized_df)

    if deduplicated_df is not None:
        counts["deduplicated"] = len(deduplicated_df)

    if filtered_df is not None:
        counts["filtered"] = len(filtered_df)

    if structured_df is not None:
        counts["structured"] = len(structured_df)

    if not issue_review_df.empty:
        counts["issues"] = len(issue_review_df)

    counts.update(dedup_stats)

    write_run_summary(
        paths,
        start_from,
        end_from,
        counts,
    )

    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)

    if structured_df is not None:
        print(
            f"Final structured complaints: "
            f"{len(structured_df)}"
        )
    else:
        print(
            f"Completed stages through: "
            f"{STAGES[end_index]}"
        )

    print(
        f"Run output directory: "
        f"{paths.run_dir}"
    )

    return structured_df
