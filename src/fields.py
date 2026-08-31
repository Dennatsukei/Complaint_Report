"""Shared column names and metadata field lists."""


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
    *METADATA_COLUMNS,
]
