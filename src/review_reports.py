"""Human-readable Markdown reports for manual review of pipeline outputs."""

import ast
from datetime import datetime

import pandas as pd

from fields import (
    CATEGORY_MAP,
    DEDUP_CANDIDATES_FILE,
    DEDUP_AUDIT_FILE,
    FILTERED_FILE,
    ISSUE_REVIEW_FILE,
    REVIEW_DEDUP_FILE,
    REVIEW_ISSUE_FILE,
    REVIEW_NO_ISSUE_FILE,
    REVIEW_SPLIT_FILE,
    SPLIT_AUDIT_FILE,
    STRUCTURED_FILE,
    SUBCATEGORY_MAP,
)


def _read_csv(path):
    if not path.exists():
        return None

    return pd.read_csv(path, encoding="utf-8-sig")


def _parse_list(value):
    if value is None:
        return []

    if isinstance(value, float) and pd.isna(value):
        return []

    if isinstance(value, list):
        return value

    try:
        parsed = ast.literal_eval(str(value))
    except (ValueError, SyntaxError):
        return []

    return parsed if isinstance(parsed, list) else []


def _text(value):
    if value is None:
        return ""

    if isinstance(value, float) and pd.isna(value):
        return ""

    text = str(value).strip()
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\n", " ")

    return text


def _yes_no(value):
    if value in (True, "True", "true", "是", "1", 1):
        return "是"

    return "否"


def _write_md(paths, filename, content):
    paths.ensure_report_dir()
    path = paths.report_file(filename)
    path.write_text(content, encoding="utf-8")
    print(f"Review saved: {path}")


def _write_split_review(paths):
    source_df = _read_csv(paths.stage_file(SPLIT_AUDIT_FILE))

    if source_df is None or source_df.empty:
        return

    if "decision" in source_df.columns:
        df = source_df[
            source_df["decision"]
            .fillna("")
            .astype(str)
            .str.strip()
            == "split"
        ]
    else:
        df = source_df[
            source_df["part_count"]
            .fillna(1)
            .astype(int)
            > 1
        ]

    df = df.reset_index(drop=True)

    lines = [
        "# Split 人工审核",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 被拆分投诉数：{len(df)}",
        "",
    ]

    for index, row in df.iterrows():
        parts = _parse_list(row.get("parts"))

        if not parts:
            parts = [_text(row.get("raw_content"))]

        lines.append(
            f"## {index + 1}. "
            f"原始投诉：{_text(row.get('source_complaint_id'))}"
        )
        lines.append("")
        lines.append(
            f"- 来源：{_text(row.get('source_file'))}"
            f"（{_text(row.get('report_type'))}）"
        )
        lines.append(f"- 日期：{_text(row.get('incident_date'))}")
        lines.append(
            f"- 拆分判断：{_text(row.get('decision'))}"
            f"（{_text(row.get('part_count'))} 段）"
        )
        lines.append(f"- 原始内容：{_text(row.get('raw_content'))}")
        lines.append("")
        lines.append("**拆分结果**：")

        for part_index, part in enumerate(parts, start=1):
            lines.append(f"{part_index}. {_text(part)}")

        lines.append("")

    _write_md(
        paths,
        REVIEW_SPLIT_FILE,
        "\n".join(lines),
    )


def _write_dedup_review(paths):
    df = _read_csv(paths.stage_file(DEDUP_AUDIT_FILE))

    if df is None or df.empty:
        return

    candidate_reasons = {}
    candidates_df = _read_csv(
        paths.stage_file(DEDUP_CANDIDATES_FILE)
    )

    if (
        candidates_df is not None
        and not candidates_df.empty
        and "complaint_a" in candidates_df.columns
        and "complaint_b" in candidates_df.columns
        and "candidate_reason" in candidates_df.columns
    ):
        candidate_reasons = {
            (str(complaint_a), str(complaint_b)): reason
            for complaint_a, complaint_b, reason in zip(
                candidates_df["complaint_a"],
                candidates_df["complaint_b"],
                candidates_df["candidate_reason"],
            )
        }

    lines = [
        "# Dedup 人工审核",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 重复对照组数：{len(df)}",
        "",
    ]

    for index, row in df.iterrows():
        same_event = _yes_no(row.get("same_event"))

        lines.append(
            f"## {index + 1}. "
            f"{_text(row.get('complaint_a'))} vs "
            f"{_text(row.get('complaint_b'))}"
        )
        lines.append("")
        lines.append(
            f"- 判定：{'重复' if same_event == '是' else '不重复'}"
            f"（same_event={same_event}）"
        )
        lines.append(
            f"- 保留：{_text(row.get('kept'))}；"
            f"移除：{_text(row.get('removed'))}"
        )
        lines.append(f"- 原因：{_text(row.get('reason'))}")
        pair_key = (
            str(row.get("complaint_a")),
            str(row.get("complaint_b")),
        )
        candidate_reason = candidate_reasons.get(pair_key)

        if candidate_reason is None:
            candidate_reason = candidate_reasons.get(
                (pair_key[1], pair_key[0])
            )

        if candidate_reason:
            lines.append(
                f"- 候选原因：{_text(candidate_reason)}"
            )

        lines.append(f"- 日期：{_text(row.get('incident_date'))}")
        lines.append(
            f"- 投诉 A（{_text(row.get('source_file_a'))}）："
            f"{_text(row.get('content_a'))}"
        )
        lines.append(
            f"- 投诉 B（{_text(row.get('source_file_b'))}）："
            f"{_text(row.get('content_b'))}"
        )
        lines.append("")

    _write_md(
        paths,
        REVIEW_DEDUP_FILE,
        "\n".join(lines),
    )


def _write_no_issue_review(paths):
    structured_df = _read_csv(paths.stage_file(STRUCTURED_FILE))

    if structured_df is None or structured_df.empty:
        return

    content_by_id = {}
    filtered_df = _read_csv(paths.stage_file(FILTERED_FILE))

    if (
        filtered_df is not None
        and not filtered_df.empty
        and "complaint_id" in filtered_df.columns
        and "content" in filtered_df.columns
    ):
        content_by_id = {
            str(complaint_id): content
            for complaint_id, content in zip(
                filtered_df["complaint_id"],
                filtered_df["content"],
            )
        }

    no_issue_rows = []

    for _, row in structured_df.iterrows():
        if not _parse_list(row.get("issues")):
            no_issue_rows.append(row)

    lines = [
        "# Structurer 判定无问题条目",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 无问题条目数：{len(no_issue_rows)}",
        "",
    ]

    for index, row in enumerate(no_issue_rows, start=1):
        complaint_id = _text(row.get("complaint_id"))
        platform = _text(row.get("platform"))
        score = _text(row.get("score"))
        platform_part = (
            f"；平台：{platform}"
            if platform
            else ""
        )
        score_part = (
            f"；评分：{score}"
            if score
            else ""
        )

        lines.append(f"## {index}. {complaint_id}")
        lines.append("")
        lines.append(f"- 日期：{_text(row.get('incident_date'))}")
        lines.append(
            f"- 来源：{_text(row.get('source_file'))}"
            f"（{_text(row.get('report_type'))}）"
            f"{platform_part}{score_part}"
        )
        lines.append(
            f"- 投诉内容："
            f"{content_by_id.get(complaint_id, '')}"
        )
        lines.append(
            "- Structurer 结论：未识别到明确酒店问题"
        )
        lines.append("")

    _write_md(
        paths,
        REVIEW_NO_ISSUE_FILE,
        "\n".join(lines),
    )


def _write_issue_review(paths):
    df = _read_csv(paths.stage_file(ISSUE_REVIEW_FILE))

    if df is None or df.empty:
        return

    lines = [
        "# Issue 人工审核",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- Issue 行数：{len(df)}",
        "",
    ]

    grouped = df.groupby("complaint_id", sort=False)

    for index, (complaint_id, group) in enumerate(
        grouped,
        start=1,
    ):
        first = group.iloc[0]
        platform = _text(first.get("platform"))
        score = _text(first.get("score"))
        platform_part = (
            f"；平台：{platform}"
            if platform
            else ""
        )
        score_part = (
            f"；评分：{score}"
            if score
            else ""
        )

        lines.append(f"## {index}. {complaint_id}")
        lines.append("")
        lines.append(f"- 日期：{_text(first.get('incident_date'))}")
        lines.append(
            f"- 来源：{_text(first.get('source_file'))}"
            f"（{_text(first.get('report_type'))}）"
            f"{platform_part}{score_part}"
        )
        lines.append(
            f"- 投诉内容：{_text(first.get('content'))}"
        )
        lines.append("")
        lines.append("**识别到的 Issue**：")

        for issue_index, (_, issue) in enumerate(
            group.iterrows(),
            start=1,
        ):
            category = CATEGORY_MAP.get(
                str(issue.get("category")),
                _text(issue.get("category")),
            )
            subcategory = SUBCATEGORY_MAP.get(
                str(issue.get("subcategory")),
                _text(issue.get("subcategory")),
            )
            primary = _yes_no(issue.get("primary"))

            lines.append(
                f"{issue_index}. {category} / {subcategory}；"
                f"责任部门：{_text(issue.get('responsible_department'))}；"
                f"主问题：{primary}"
            )

        lines.append("")

    _write_md(
        paths,
        REVIEW_ISSUE_FILE,
        "\n".join(lines),
    )


def write_review_reports(paths, targets=None):
    """Write human-readable review reports for one run directory.

    ``targets`` limits the run to a subset of report filenames; when omitted,
    every report whose upstream artifact exists is written.
    """
    writers = (
        (REVIEW_SPLIT_FILE, _write_split_review),
        (REVIEW_DEDUP_FILE, _write_dedup_review),
        (REVIEW_NO_ISSUE_FILE, _write_no_issue_review),
        (REVIEW_ISSUE_FILE, _write_issue_review),
    )

    for filename, writer in writers:
        if targets is None or filename in targets:
            writer(paths)
