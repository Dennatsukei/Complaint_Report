import pandas as pd

from text_parser import extract_room_numbers


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


def normalize_record(record):
    """
    Normalize one complaint record.

    Keeps all metadata and original content.
    Adds normalized room information.
    """

    result = {
        "complaint_id": record["complaint_id"],
        "record_id": record["record_id"],
    }

    for column in METADATA_COLUMNS:
        result[column] = record[column]

    result.update({
        "room": extract_room_numbers(
            record["content"]
        ),
        "content": record["content"],
        "raw_content": record["raw_content"],
    })

    return result


def normalize_dataframe(df):
    """
    Normalize the complete complaint DataFrame.
    """

    records = [
        normalize_record(record)
        for record in df.to_dict("records")
    ]

    return pd.DataFrame(records)