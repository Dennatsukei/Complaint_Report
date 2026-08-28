from datetime import datetime

from text_parser import extract_incident_date


def clean_text(text):
    if not isinstance(text, str):
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    return "\n".join(lines).strip()


def normalize_date(value):
    if isinstance(value, datetime):
        return value.date()

    return value


def process_record(record):
    record = record.copy()

    record["incident_date"] = normalize_date(
        record["incident_date"]
    )
    record["report_start_date"] = normalize_date(
        record["report_start_date"]
    )
    record["report_end_date"] = normalize_date(
        record["report_end_date"]
    )
    record["raw_content"] = clean_text(
        record["raw_content"]
    )

    if record["incident_date"] is None:
        record["incident_date"] = extract_incident_date(
            record["raw_content"],
            report_start_date=record["report_start_date"],
            report_end_date=record["report_end_date"],
        )

    return record