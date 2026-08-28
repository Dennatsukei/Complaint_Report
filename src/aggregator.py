import pandas as pd


BASE_COLUMNS = [
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


class ComplaintAggregator:

    def __init__(self):
        self.records = []

    def add_report(self, result):
        """
        Add a daily, weekly, or monthly report.
        """

        report_type = result["report_type"]
        source_file = result["source_file"]

        for complaint in result["complaints"]:

            self.records.append({
                "incident_date": complaint["incident_date"],
                "report_start_date": complaint[
                    "report_start_date"
                ],
                "report_end_date": complaint[
                    "report_end_date"
                ],
                "raw_content": complaint["raw_content"],
                "source": "internal_report",
                "source_file": source_file,
                "report_type": report_type,
                "complaint_id": complaint["complaint_id"],

                # Not applicable to internal reports
                "platform": None,
                "score": None,
                "room_type": None,
            })

    def add_platform_reviews(self, reviews):
        """
        Add platform review records.
        """

        for review in reviews:

            self.records.append({
                "incident_date": review["incident_date"],
                "report_start_date": review["incident_date"],
                "report_end_date": review["incident_date"],
                "raw_content": review["raw_content"],
                "source": "platform_review",
                "source_file": review["source_path"],
                "report_type": "platform_review",
                "complaint_id": review["review_id"],

                "platform": review["platform"],
                "score": review["score"],
                "room_type": review["room_type"],
            })

    def to_dataframe(self):
        """
        Convert all records into a DataFrame
        with a stable column order.
        """

        return pd.DataFrame(
            self.records,
            columns=BASE_COLUMNS
        )

    def save(self, output_path):
        """
        Save aggregated records.
        """

        df = self.to_dataframe()

        df.to_csv(
            output_path,
            index=False,
            encoding="utf-8-sig"
        )

        return df