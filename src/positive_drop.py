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


def filter_positive(df: pd.DataFrame) -> pd.DataFrame:
    """
    删除纯正面评价，返回剩余记录。
    """
    mask = df["raw_content"].apply(is_pure_positive)

    dropped_count = int(mask.sum())
    remaining_count = len(df) - dropped_count

    print(
        f"Positive filter: "
        f"{dropped_count} dropped, "
        f"{remaining_count} remaining."
    )

    return df.loc[~mask].copy()