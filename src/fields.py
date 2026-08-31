"""Shared column names, metadata lists, and artifact file names."""


AGGREGATED_COLUMNS = [
    "incident_date",
    "report_start_date",
    "report_end_date",
    "raw_content",
    "source",
    "source_file",
    "report_type",
    "complaint_id",
    "platform",
    "score",
    "room_type",
]


METADATA_COLUMNS = [
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


STRUCTURED_METADATA_COLUMNS = [
    "complaint_id",
    "record_id",
    "source_complaint_id",
    *METADATA_COLUMNS,
]


INGESTED_FILE = "01_ingested_records.csv"
PREPARED_FILE = "02_prepared_complaints.csv"
SPLIT_COMPLAINTS_FILE = "03_split_complaints.csv"
SPLIT_AUDIT_FILE = "03_split_audit.csv"
NORMALIZED_FILE = "04_normalized_complaints.csv"
DEDUP_CANDIDATES_FILE = "04_dedup_candidates.csv"
DEDUP_AUDIT_FILE = "05_dedup_audit.csv"
DEDUPLICATED_FILE = "05_deduplicated_complaints.csv"
FILTER_AUDIT_FILE = "06_filter_audit.csv"
FILTERED_FILE = "06_filtered_complaints.csv"
STRUCTURED_FILE = "07_structured_complaints.csv"
ISSUE_REVIEW_FILE = "08_issue_review.csv"
RUN_SUMMARY_FILE = "run_summary.json"


ALL_ARTIFACTS = [
    INGESTED_FILE,
    PREPARED_FILE,
    SPLIT_COMPLAINTS_FILE,
    SPLIT_AUDIT_FILE,
    NORMALIZED_FILE,
    DEDUP_CANDIDATES_FILE,
    DEDUP_AUDIT_FILE,
    DEDUPLICATED_FILE,
    FILTER_AUDIT_FILE,
    FILTERED_FILE,
    STRUCTURED_FILE,
    ISSUE_REVIEW_FILE,
    RUN_SUMMARY_FILE,
]
