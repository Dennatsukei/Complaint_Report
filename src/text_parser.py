import re
from datetime import date



def extract_incident_date(
    raw_content,
    report_start_date=None,
    report_end_date=None
):
    """
    Extract incident date from complaint content.

    Priority:
    1. Date at the beginning of the content
    2. Date appearing near the beginning
    3. "今日 / 今天" -> use report date when report period is one day
    4. If report period is a single month and the content contains
       an unambiguous month/day, return that date
    5. Otherwise return None

    The function deliberately avoids guessing when ambiguity exists.
    """

    if not isinstance(raw_content, str):
        return None

    text = raw_content.strip()

    if not text:
        return None

    # ---------------------------------------------------------
    # Helper
    # ---------------------------------------------------------

    def make_date(year, month, day):
        try:
            result = date(
                int(year),
                int(month),
                int(day)
            )
        except ValueError:
            return None

        # If report period is known, reject dates outside it.
        if (
            report_start_date is not None
            and report_end_date is not None
        ):
            if not (
                report_start_date
                <= result
                <= report_end_date
            ):
                return None

        return result

    # ---------------------------------------------------------
    # 1. Full date at the beginning
    #
    # 2026-08-11
    # 2026.08.11
    # 2026/08/11
    # ---------------------------------------------------------

    match = re.match(
        r"^\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})",
        text
    )

    if match:
        return make_date(
            *match.groups()
        )

    # ---------------------------------------------------------
    # 2. Chinese month/day at the beginning
    #
    # 8月11日
    # 8月5日晚上
    # ---------------------------------------------------------

    match = re.match(
        r"^\s*(\d{1,2})月(\d{1,2})日",
        text
    )

    if match:

        month, day = map(
            int,
            match.groups()
        )

        if report_start_date is not None:
            return make_date(
                report_start_date.year,
                month,
                day
            )

    # ---------------------------------------------------------
    # 3. Numeric month/day at the beginning
    #
    # 8.6日
    # 8.6
    # 8/6
    # ---------------------------------------------------------

    match = re.match(
        r"^\s*(\d{1,2})[./-](\d{1,2})日?",
        text
    )

    if match:

        month, day = map(
            int,
            match.groups()
        )

        if report_start_date is not None:
            return make_date(
                report_start_date.year,
                month,
                day
            )

    # ---------------------------------------------------------
    # 4. "今日 / 今天"
    #
    # This is only safe when report_start_date == report_end_date.
    # ---------------------------------------------------------

    if re.search(
        r"(?:^|[，。；,;：:\s])(?:今日|今天)",
        text
    ):

        if (
            report_start_date is not None
            and report_end_date is not None
            and report_start_date == report_end_date
        ):
            return report_start_date

    # ---------------------------------------------------------
    # 5. Search for a Chinese month/day in the first part
    #
    # Example:
    # "投诉时间：8月11日晚上..."
    #
    # Limit the search to the first 50 characters so that
    # historical dates mentioned later in the narrative are
    # less likely to be mistaken for the incident date.
    # ---------------------------------------------------------

    prefix = text[:50]

    matches = re.findall(
        r"(\d{1,2})月(\d{1,2})日",
        prefix
    )

    if matches and report_start_date is not None:

        candidates = []

        for month, day in matches:

            result = make_date(
                report_start_date.year,
                int(month),
                int(day)
            )

            if result is not None:
                candidates.append(result)

        if len(candidates) == 1:
            return candidates[0]

    # ---------------------------------------------------------
    # Unable to determine safely
    # ---------------------------------------------------------

    return None



def extract_room_numbers(content):
    """
    Extract four-digit room numbers from complaint content.

    Supported date formats:
    2026-08-10
    2026.08.10
    2026/08/10

    Returns:
        list[str]
    """
    if not isinstance(content, str):
        return []

    text = re.sub(
        r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}",
        "",
        content
    )

    rooms = re.findall(
        r"(?<!\d)(\d{4})(?!\d)",
        text
    )

    # Remove duplicates while preserving order
    return list(dict.fromkeys(rooms))