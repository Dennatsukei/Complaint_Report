import re
import pandas as pd


ISSUE_PATTERNS = [
    r"不满意",
    r"不舒服",
    r"不好",
    r"很差",
    r"太差",
    r"不太干净",
    r"不干净",
    r"隔音.*差",
    r"太慢",
    r"有点慢",
    r"不方便",
    r"不合理",
    r"不够",
    r"不足",
    r"美中不足",
    r"遗憾",
    r"脏",
    r"异味",
    r"头发",
    r"虫子",
    r"污渍",
    r"噪音",
    r"吵",
    r"漏水",
    r"堵",
    r"跳闸",
    r"故障",
    r"安全隐患",
    r"房卡.*打不开",
    r"无法",
    r"不能",
    r"没空调",
    r"没有空调",
    r"没纱窗",
    r"没有纱窗",
    r"收费",
    r"扣费",
    r"退费",
    r"退款",
    r"水流.*小",
    r"忽冷忽热",
    r"不会再住",
]


POSITIVE_PATTERNS = [
    # 明确正面评价
    r"好评",
    r"五星好评",
    r"五分",
    r"非常满意",
    r"很满意",
    r"满意",
    r"非常好",
    r"很好",
    r"不错",
    r"非常棒",
    r"很棒",
    r"优秀",

    # 明确正面服务评价
    r"服务.*好",
    r"服务.*棒",
    r"服务.*热情",
    r"服务.*周到",
    r"服务.*贴心",
    r"态度.*好",
    r"热情周到",

    # 明确正面体验评价
    r"干净整洁",
    r"体验.*好",
    r"体验.*棒",
    r"值得推荐",
    r"强烈推荐",
    r"点赞",
    r"感谢",
    r"下次.*还.*住",
    r"下次.*还.*选择",

    # 明确的弱正面 / 接受性表达
    r"感觉能接受",
    r"整体能接受",
    r"基本能接受",
    r"可以接受",
]


def contains_pattern(text: str, patterns: list[str]) -> bool:
    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in patterns
    )


def first_match(text: str, patterns: list[str]):
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return pattern
    return None


def is_pure_positive(text: str) -> bool:
    """
    判断一条记录是否可以安全过滤。

    True:
        明显纯正面，无明显 issue。

    False:
        存在 issue，或者无法确定。
    """
    if not isinstance(text, str) or not text.strip():
        return False

    text = text.strip()

    # Issue 优先。
    # 只要存在明显问题，就绝不因为正面内容而删除。
    if contains_pattern(text, ISSUE_PATTERNS):
        return False

    return contains_pattern(text, POSITIVE_PATTERNS)


def analyze_record(text):
    """Classify a record as kept or dropped, with the matched patterns."""
    if not isinstance(text, str) or not text.strip():
        return {
            "decision": "kept",
            "reason": "empty",
            "matched_issue_pattern": None,
            "matched_positive_pattern": None,
        }

    text = text.strip()

    issue_pattern = first_match(text, ISSUE_PATTERNS)
    positive_pattern = first_match(text, POSITIVE_PATTERNS)

    if issue_pattern is not None:
        decision = "kept"
        reason = "has_issue"
    elif positive_pattern is not None:
        decision = "dropped"
        reason = "pure_positive"
    else:
        decision = "kept"
        reason = "no_signal"

    return {
        "decision": decision,
        "reason": reason,
        "matched_issue_pattern": issue_pattern,
        "matched_positive_pattern": positive_pattern,
    }


def filter_positive_audited(df: pd.DataFrame):
    """
    Remove pure positive reviews and return both the kept records
    and a per-record audit table.
    """
    analyses = [
        analyze_record(text)
        for text in df["raw_content"]
    ]

    dropped = [
        analysis["decision"] == "dropped"
        for analysis in analyses
    ]

    audit_records = []

    for (_, row), analysis in zip(
        df.iterrows(),
        analyses,
    ):
        audit_records.append({
            "complaint_id": row["complaint_id"],
            "record_id": row["record_id"],
            "incident_date": row.get("incident_date"),
            "source": row.get("source"),
            "source_file": row.get("source_file"),
            "raw_content": row["raw_content"],
            **analysis,
        })

    audit_df = pd.DataFrame(audit_records)
    filtered_df = df.loc[[not d for d in dropped]].copy()

    print(
        f"Positive filter: "
        f"{sum(dropped)} dropped, "
        f"{len(filtered_df)} remaining."
    )

    return filtered_df, audit_df


def filter_positive(df: pd.DataFrame) -> pd.DataFrame:
    """
    删除纯正面评价，返回剩余记录。
    """
    filtered_df, _ = filter_positive_audited(df)
    return filtered_df
