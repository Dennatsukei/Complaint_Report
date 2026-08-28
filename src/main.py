import os
import pandas as pd

from aggregator import ComplaintAggregator
from extractor import ComplaintExtractor
from processor import process_record
from split import LLMSplit
from normalizer import normalize_dataframe
from deduplicator import ComplaintDeduplicator
from llm_dedup import LLMDeduplicator
from dedup_resolver import DedupResolver
from positive_drop import filter_positive
from structurer import LLMStructurer


# =========================================================
# Configuration
# =========================================================

START_FROM = "structure"

STAGES = [
    "extract",
    "process",
    "split",
    "normalize",
    "dedup",
    "filter",
    "structure",
]

if START_FROM not in STAGES:
    raise ValueError(
        f"Invalid START_FROM: {START_FROM}"
    )

START_INDEX = STAGES.index(START_FROM)

OUTPUT_DIR = "Output"

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True,
)


def output_path(filename):
    return os.path.join(
        OUTPUT_DIR,
        filename,
    )


# =========================================================
# Extract + Aggregate
# =========================================================

if START_INDEX <= STAGES.index("extract"):

    aggregator = ComplaintAggregator()

    # -----------------------------------------------------
    # Daily Reports
    # -----------------------------------------------------

    daily_path = "Daily Reports"

    for item in os.listdir(daily_path):

        path = os.path.join(
            daily_path,
            item,
        )

        if not os.path.isfile(path):
            continue

        extractor = ComplaintExtractor(path)

        report = extractor.extract_daily()

        aggregator.add_report(report)

    # -----------------------------------------------------
    # Weekly Reports
    # -----------------------------------------------------

    weekly_path = "Weekly Reports"

    for item in os.listdir(weekly_path):

        path = os.path.join(
            weekly_path,
            item,
        )

        if not os.path.isfile(path):
            continue

        extractor = ComplaintExtractor(path)

        report = extractor.extract_weekly()

        aggregator.add_report(report)

    # -----------------------------------------------------
    # Monthly Reports
    # -----------------------------------------------------

    monthly_path = "Monthly Reports"

    for item in os.listdir(monthly_path):

        path = os.path.join(
            monthly_path,
            item,
        )

        if not os.path.isfile(path):
            continue

        extractor = ComplaintExtractor(path)

        report = extractor.extract_monthly()

        aggregator.add_report(report)

    # -----------------------------------------------------
    # Platform Reviews
    # -----------------------------------------------------

    platform_path = "Platform Reviews"

    for item in os.listdir(platform_path):

        path = os.path.join(
            platform_path,
            item,
        )

        if not os.path.isfile(path):
            continue

        extractor = ComplaintExtractor(path)

        reviews = extractor.extract_reviews()

        aggregator.add_platform_reviews(
            reviews
        )

    raw_df = aggregator.to_dataframe()

    raw_df.to_csv(
        output_path("complaints.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"Extracted and aggregated: "
        f"{len(raw_df)} records."
    )

else:

    raw_df = pd.read_csv(
        output_path("complaints.csv"),
        encoding="utf-8-sig",
    )

    print(
        f"Loaded complaints.csv: "
        f"{len(raw_df)} records."
    )


# =========================================================
# Process
# =========================================================

if START_INDEX <= STAGES.index("process"):

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

    processed_df.to_csv(
        output_path("processed.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"Processed: "
        f"{len(processed_df)} records."
    )

else:

    processed_df = pd.read_csv(
        output_path("processed.csv"),
        encoding="utf-8-sig",
    )

    print(
        f"Loaded processed.csv: "
        f"{len(processed_df)} records."
    )


# =========================================================
# Split
# =========================================================

if START_INDEX <= STAGES.index("split"):

    metadata_columns = [
        "incident_date",
        "report_start_date",
        "report_end_date",
        "source",
        "source_file",
        "report_type",
        "platform",
        "score",
        "room_type",
    ]

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
            for column in metadata_columns
        }

        # -------------------------------------------------
        # No split
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Split into multiple complaints
        # -------------------------------------------------

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

    split_df.to_csv(
        output_path("split.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"Split: "
        f"{len(split_df)} complaints."
    )

else:

    split_df = pd.read_csv(
        output_path("split.csv"),
        encoding="utf-8-sig",
    )

    print(
        f"Loaded split.csv: "
        f"{len(split_df)} records."
    )


# =========================================================
# Normalize
# =========================================================

if START_INDEX <= STAGES.index("normalize"):

    normalized_df = normalize_dataframe(
        split_df
    )

    normalized_df.to_csv(
        output_path("normalized.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"Normalized: "
        f"{len(normalized_df)} complaints."
    )

else:

    normalized_df = pd.read_csv(
        output_path("normalized.csv"),
        encoding="utf-8-sig",
    )

    print(
        f"Loaded normalized.csv: "
        f"{len(normalized_df)} records."
    )


# =========================================================
# Deduplication
# =========================================================

if START_INDEX <= STAGES.index("dedup"):

    # -----------------------------------------------------
    # Exact deduplication
    # -----------------------------------------------------

    deduplicator = ComplaintDeduplicator(
        normalized_df
    )

    dedup_df = (
        deduplicator.exact_deduplicate()
    )

    candidates_df = (
        deduplicator.generate_candidates()
    )

    candidates_df.to_csv(
        output_path(
            "dedup_candidates.csv"
        ),
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"Complaints after exact dedup: "
        f"{len(dedup_df)}"
    )

    print(
        f"Dedup candidates: "
        f"{len(candidates_df)} pairs."
    )

    # -----------------------------------------------------
    # LLM semantic deduplication
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Handle zero candidates
    # -----------------------------------------------------

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

    llm_results_df.to_csv(
        output_path(
            "llm_dedup_results.csv"
        ),
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"LLM dedup completed: "
        f"{len(llm_results_df)} pairs."
    )

    print(
        f"LLM YES: "
        f"{llm_results_df['same_event'].sum()}"
    )

    print(
        f"LLM NO: "
        f"{(~llm_results_df['same_event']).sum()}"
    )

    # -----------------------------------------------------
    # Resolve duplicates
    # -----------------------------------------------------

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

    dedup_audit_df.to_csv(
        output_path("dedup_audit.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    deduplicated_df.to_csv(
        output_path("deduplicated.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"Duplicates resolved: "
        f"{len(removed_ids)}"
    )

    print(
        f"Dedup audit records: "
        f"{len(dedup_audit_df)}"
    )

    print(
        f"Final complaints: "
        f"{len(deduplicated_df)}"
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

    # -----------------------------------------------------
    # Integrity check
    # -----------------------------------------------------

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

else:

    deduplicated_df = pd.read_csv(
        output_path(
            "deduplicated.csv"
        ),
        encoding="utf-8-sig",
    )

    print(
        f"Loaded deduplicated.csv: "
        f"{len(deduplicated_df)} records."
    )


# =========================================================
# Positive Filter
# =========================================================

if START_INDEX <= STAGES.index("filter"):

    filtered_df = filter_positive(
        deduplicated_df
    )

    filtered_df.to_csv(
        output_path("filtered.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    dropped = (
        len(deduplicated_df)
        - len(filtered_df)
    )

else:

    filtered_df = pd.read_csv(
        output_path("filtered.csv"),
        encoding="utf-8-sig",
    )

    print(
        f"Loaded filtered.csv: "
        f"{len(filtered_df)} records."
    )


# =========================================================
# Structuring
# =========================================================

if START_INDEX <= STAGES.index("structure"):

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

    metadata_columns = [
        "complaint_id",
        "record_id",
        "incident_date",
        "report_start_date",
        "report_end_date",
        "source",
        "source_file",
        "report_type",
        "platform",
        "score",
        "room_type",
    ]

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
                for column in metadata_columns
            },
            **result,
        })

    structured_df = pd.DataFrame(
        structured_records
    )

    structured_df.to_csv(
        output_path("structured.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    structured_issue_count = sum(
        len(result.get("issues", []))
        for result in results
        if isinstance(result, dict)
    )

    print(
        f"Structured complaints: "
        f"{len(structured_df)}"
    )

    print(
        f"Structured issues: "
        f"{structured_issue_count}"
    )

else:

    structured_df = pd.read_csv(
        output_path("structured.csv"),
        encoding="utf-8-sig",
    )

    print(
        f"Loaded structured.csv: "
        f"{len(structured_df)} records."
    )


# =========================================================
# Pipeline Complete
# =========================================================

print("\n" + "=" * 80)
print("PIPELINE COMPLETE")
print("=" * 80)

print(
    f"Final structured complaints: "
    f"{len(structured_df)}"
)

print(
    f"Output directory: "
    f"{OUTPUT_DIR}"
)