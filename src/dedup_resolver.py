import pandas as pd


AUDIT_COLUMNS = [
    "complaint_a",
    "complaint_b",
    "source_a",
    "source_b",
    "source_file_a",
    "source_file_b",
    "incident_date",
    "content_a",
    "content_b",
    "same_event",
    "kept",
    "removed",
    "reason",
]


class DedupResolver:

    def __init__(
        self,
        complaints,
        results,
    ):

        self.complaints = complaints.copy()
        self.results = results.copy()

    def get_record(self, complaint_id):

        return self.complaints[
            self.complaints["complaint_id"]
            == complaint_id
        ].iloc[0]

    def add_resolved(
        self,
        a_id,
        b_id,
        kept,
        removed,
        reason,
    ):

        a = self.get_record(a_id)
        b = self.get_record(b_id)

        return {
            "complaint_a": a_id,
            "complaint_b": b_id,

            "source_a": a["source"],
            "source_b": b["source"],

            "source_file_a": a["source_file"],
            "source_file_b": b["source_file"],

            "incident_date": a["incident_date"],

            "content_a": a["content"],
            "content_b": b["content"],

            "same_event": True,

            "kept": kept,
            "removed": removed,

            "reason": reason,
        }

    def resolve(self):

        removed = set()
        resolved = []

        # =================================================
        # Exact duplicates
        # =================================================

        exact = self.complaints[
            self.complaints[
                "duplicate_of"
            ].notna()
        ]

        for _, row in exact.iterrows():

            removed_id = row["complaint_id"]
            kept_id = row["duplicate_of"]

            removed.add(removed_id)

            resolved.append(
                self.add_resolved(
                    removed_id,
                    kept_id,
                    kept_id,
                    removed_id,
                    "exact_duplicate",
                )
            )

        # =================================================
        # Semantic duplicates
        # =================================================

        true_results = self.results[
            self.results["same_event"] == True
        ]

        # =================================================
        # Split-record case
        # =================================================

        for complaint_id, group in (
            true_results.groupby("complaint_a")
        ):

            if len(group) < 2:
                continue

            b_ids = group[
                "complaint_b"
            ].tolist()

            b_records = self.complaints[
                self.complaints[
                    "complaint_id"
                ].isin(b_ids)
            ]

            if (
                len(
                    b_records[
                        "record_id"
                    ].unique()
                ) != 1
            ):
                continue

            if complaint_id in removed:
                continue

            removed.add(complaint_id)

            for b_id in b_ids:

                if b_id in removed:
                    continue

                resolved.append(
                    self.add_resolved(
                        complaint_id,
                        b_id,
                        b_id,
                        complaint_id,
                        "split_record",
                    )
                )

        # =================================================
        # Normal semantic duplicates
        # =================================================

        for _, row in true_results.iterrows():

            a_id = row["complaint_a"]
            b_id = row["complaint_b"]

            if (
                a_id in removed
                or b_id in removed
            ):
                continue

            a = self.get_record(a_id)
            b = self.get_record(b_id)

            # Platform → internal
            if (
                a["source"] == "platform_review"
                and b["source"] != "platform_review"
            ):

                keep = b_id
                remove = a_id

            elif (
                b["source"] == "platform_review"
                and a["source"] != "platform_review"
            ):

                keep = a_id
                remove = b_id

            # Internal ↔ internal
            else:

                keep = a_id
                remove = b_id

            removed.add(remove)

            resolved.append(
                self.add_resolved(
                    a_id,
                    b_id,
                    keep,
                    remove,
                    "semantic_duplicate",
                )
            )

        audit_df = pd.DataFrame(
            resolved,
            columns=AUDIT_COLUMNS,
        )

        return (
            audit_df,
            removed,
        )

    def get_unique(self, removed):

        return self.complaints[
            ~self.complaints[
                "complaint_id"
            ].isin(removed)
        ].copy()
