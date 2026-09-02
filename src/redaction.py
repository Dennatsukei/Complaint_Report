"""Outbound redaction for third-party LLM requests.

The pipeline sends free-text complaint content to external chat models
in the split, dedup and structure stages.  This module masks direct
identifiers (phone numbers, ID numbers, e-mail addresses, ...) and the
room numbers that appear in that text before the request leaves the
machine, while leaving every locally stored artifact unchanged.

Masking is reversible only inside the running process: each unique
original value is mapped to a stable, type-labelled token, so:

* the same room number keeps the same token across messages of one run
  (dedup can still rely on a shared "same room" signal), and
* response text such as split anchors can be translated back to the
  original content before it is used or stored locally.
"""

from __future__ import annotations

import hashlib
import os
import re


MODE_OFF = "off"
MODE_PII = "pii"
MODE_STRICT = "strict"
DEFAULT_MODE = MODE_PII
VALID_MODES = (MODE_OFF, MODE_PII, MODE_STRICT)


# Common Chinese surnames used to recognise personal-name mentions that
# are followed by an honorific (先生/女士/小姐).
_SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏窦章苏潘葛奚范彭鲁韦昌马苗凤花方俞任袁柳鲍史唐费薛雷贺"
    "倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄穆萧尹姚邵湛汪"
    "祁毛禹狄米贝明臧计成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵季麻强贾路娄"
    "危江童颜郭梅盛林钟徐邱骆高夏蔡田樊胡凌霍虞万柯卢莫房裘缪解应宗丁宣"
    "邓郁单杭洪包诸左石崔吉龚程邢裴陆荣翁荀羊甄芮羿储靳汲邴糜松段富巫乌"
    "焦巴弓牧隗山谷车侯宓蓬郗班仰仲伊宫宁仇栾暴甘厉戎祖武符刘景詹束龙叶"
    "司韶郜黎薄印宿白怀蒲邰鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍闻莘党翟谭贡劳"
    "逄申扶堵冉宰郦桑桂牛寿通边扈燕冀浦尚农温庄晏柴瞿阎充慕连茹习宦艾鱼"
    "容向古易慎戈廖庚终暨居衡步都耿弘匡国文寇广禄阙沃利蔚越夔师巩厍聂晁"
    "勾敖融冷訾辛阚那简饶曾毋沙鞠须丰巢关蒯相查荆红游竺权盖益桓公"
)


def _compile_rules(mode: str) -> list[tuple[str, re.Pattern[str]]]:
    """Return the (kind, regex) rule set for a masking mode."""
    cn = "\u4e00-\u9fa5"

    rules: list[tuple[str, re.Pattern[str]]] = [
        # Room numbers such as "5052房" or "5052房间".
        ("房号", re.compile(r"(?<!\d)\d{4}房(?:间)?")),
        # China mobile numbers, with or without separators and +86 prefix.
        (
            "电话",
            re.compile(
                r"(?<!\d)(?:\+?86[ -]?)?"
                r"1[3-9]\d(?:[ -]?\d{4}){2}(?!\d)"
            ),
        ),
        # Landline numbers beginning with a 0 area code.
        ("电话", re.compile(r"(?<!\d)0\d{2,3}[ -]?\d{7,8}(?!\d)")),
        # 18-digit resident ID numbers (final digit may be X).
        ("证件", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
        # E-mail addresses.
        ("邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
        # Web addresses.
        (
            "网址",
            re.compile(
                r"(?:https?://|www\.)[^\s，。；、：\"'()（）【】]+"
            ),
        ),
        # Account-style identifiers following an explicit label.
        (
            "微信",
            re.compile(r"(?:微信号?|微信)[：:号\s]*([A-Za-z0-9_-]{5,24})"),
        ),
        (
            "QQ号",
            re.compile(r"(?:QQ|扣扣)\s*(?:号)?[：:\s]*(\d{5,11})"),
        ),
        (
            "订单",
            re.compile(
                r"(?:订单号|订单编号|预订号|预定号|确认号|预约号)"
                r"[：:号\s]*([A-Za-z0-9_-]{4,24})"
            ),
        ),
        (
            "账号",
            re.compile(r"(?:卡号|账号|银行卡号)[：:号\s]*(\d{8,20})"),
        ),
        # Personal names directly followed by an honorific, e.g. 王先生.
        # Only the name itself is replaced; the honorific stays in place.
        (
            "姓名",
            re.compile(
                rf"(?:[{_SURNAMES}])[{cn}]{{0,2}}"
                rf"(?=(?:先生|女士|小姐))"
            ),
        ),
    ]

    if mode == MODE_STRICT:
        # Monetary amounts; the value is masked, the unit stays in place.
        rules.append(
            (
                "金额",
                re.compile(
                    r"(?<!\d)(\d+(?:\.\d+)?)(?=\s*(?:元|块钱|块))"
                ),
            )
        )

    return rules


_RULES_CACHE: dict[str, list[tuple[str, re.Pattern[str]]]] = {}


def _rules(mode: str) -> list[tuple[str, re.Pattern[str]]]:
    if mode not in _RULES_CACHE:
        _RULES_CACHE[mode] = _compile_rules(mode)
    return _RULES_CACHE[mode]


class MaskingRegistry:
    """Stable value -> token mapping shared by all requests of one run.

    The mapping is deliberately deterministic within the process: the
    same original value always maps to the same token, which preserves
    cross-message signals such as "both complaints mention room 5052".
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], str] = {}
        self._by_token: dict[str, tuple[str, str]] = {}
        self._counts: dict[str, int] = {}

    def token_for(self, value: str, kind: str) -> str:
        key = (kind, value)

        cached = self._by_key.get(key)
        if cached is not None:
            return cached

        digest = hashlib.sha256(
            f"{kind}\x00{value}".encode("utf-8")
        ).hexdigest()

        for size in range(6, 13):
            token = f"[{kind}-{digest[:size]}]"
            if token not in self._by_token:
                break
        else:
            raise RuntimeError(
                "Could not allocate a unique masking token "
                f"for {kind!r}."
            )

        self._by_key[key] = token
        self._by_token[token] = key
        self._counts[kind] = self._counts.get(kind, 0) + 1
        return token

    def restore(self, text: str) -> str:
        """Replace every known masking token back with its original text."""
        for token in sorted(
            self._by_token,
            key=len,
            reverse=True,
        ):
            original = self._by_token[token][1]
            text = text.replace(token, original)
        return text

    def stats(self) -> dict[str, int]:
        return dict(self._counts)


def mask_text(
    text: str,
    registry: MaskingRegistry,
    mode: str,
) -> str:
    """Return ``text`` with recognised sensitive values replaced by tokens."""
    if not text:
        return text

    matches: list[tuple[int, int, str, str]] = []

    for kind, pattern in _rules(mode):
        for match in pattern.finditer(text):
            if pattern.groups and match.group(1) is not None:
                start = match.start(1)
                end = match.end(1)
            else:
                start = match.start()
                end = match.end()

            if end > start:
                matches.append(
                    (start, end, kind, text[start:end])
                )

    if not matches:
        return text

    # Earliest match first; for identical starts keep the longest one.
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    parts: list[str] = []
    cursor = 0
    covered_end = 0

    for start, end, kind, value in matches:
        if start < covered_end:
            continue

        parts.append(text[cursor:start])
        parts.append(registry.token_for(value, kind))
        cursor = end
        covered_end = end

    parts.append(text[cursor:])
    return "".join(parts)


def resolve_mode() -> str:
    """Resolve MASKING_MODE from the environment."""
    mode = os.getenv("MASKING_MODE", DEFAULT_MODE).strip().lower()

    if mode not in VALID_MODES:
        raise ValueError(
            "Invalid MASKING_MODE: "
            f"{mode!r}. Expected one of {', '.join(VALID_MODES)}."
        )

    return mode
