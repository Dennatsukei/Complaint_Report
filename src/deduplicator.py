import pandas as pd


class ComplaintDeduplicator:

    def __init__(self, df):
        self.df = df.copy()

    @staticmethod
    def get_rooms(value):
        if isinstance(value, list):
            return set(str(x) for x in value)

        if pd.isna(value):
            return set()

        text = str(value).strip()

        if not text:
            return set()

        text = (
            text
            .replace("[", "")
            .replace("]", "")
            .replace("'", "")
            .replace('"', "")
        )

        return {
            room.strip()
            for room in text.split(",")
            if room.strip()
        }

    @staticmethod
    def same_date(a, b):
        if pd.isna(a) or pd.isna(b):
            return False

        return a == b

    def exact_deduplicate(self):

        self.df["duplicate_of"] = None

        seen = {}

        for index, row in self.df.iterrows():

            key = (
                row["incident_date"],
                row["content"],
            )

            if key in seen:

                self.df.at[
                    index,
                    "duplicate_of"
                ] = seen[key]

            else:

                seen[key] = row["complaint_id"]

        return self.df

    def is_candidate(self, a, b):

        # Same source file cannot represent
        # the same external record.
        if a["source_file"] == b["source_file"]:
            return False

        if not self.same_date(
            a["incident_date"],
            b["incident_date"],
        ):
            return False

        source_a = a["source"]
        source_b = b["source"]

        # Platform reviews are never compared
        # with each other.
        if (
            source_a == "platform_review"
            and source_b == "platform_review"
        ):
            return False

        # Platform review ↔ internal report
        if (
            source_a == "platform_review"
            or source_b == "platform_review"
        ):
            return True

        rooms_a = self.get_rooms(a["room"])
        rooms_b = self.get_rooms(b["room"])

        # Internal ↔ internal:
        # same room is a strong candidate signal.
        if rooms_a and rooms_b:

            return bool(
                rooms_a.intersection(rooms_b)
            )

        # Missing room information:
        # let LLM decide.
        return True

    def generate_candidates(self):

        active = self.df[
            self.df["duplicate_of"].isna()
        ]

        records = list(active.iterrows())

        candidates = []

        for i in range(len(records)):

            _, a = records[i]

            for j in range(i + 1, len(records)):

                _, b = records[j]

                if not self.is_candidate(a, b):
                    continue

                candidates.append({
                    "complaint_a": a["complaint_id"],
                    "complaint_b": b["complaint_id"],
                    "date": a["incident_date"],
                    "source_a": a["source"],
                    "source_b": b["source"],
                    "source_file_a": a["source_file"],
                    "source_file_b": b["source_file"],
                    "room_a": a["room"],
                    "room_b": b["room"],
                })

        return pd.DataFrame(candidates)