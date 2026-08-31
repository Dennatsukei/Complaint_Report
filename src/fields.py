"""Shared column names, metadata lists, and artifact file names."""


CATEGORY_MAP = {
    "A": "客房卫生与房态",
    "B": "客房设施与工程",
    "C": "服务与响应",
    "D": "噪音与公共环境",
    "E": "预订、房型与费用",
    "F": "物品、安全与其他",
}


SUBCATEGORY_MAP = {
    "A1": "房间清洁不到位",
    "A2": "布草问题",
    "A3": "虫害",
    "A4": "客用品/备品",
    "A5": "遗留物",
    "A6": "房态/查房问题",

    "B1": "功能故障",
    "B2": "水电与温控",
    "B3": "房间结构与装修",
    "B4": "设施体验问题",
    "B5": "其他设施",

    "C1": "响应延迟",
    "C2": "服务执行不到位",
    "C3": "服务态度",
    "C4": "沟通/信息错误",

    "D1": "客房/楼层噪音",
    "D2": "公共区域活动噪音",
    "D3": "团队/客人行为噪音",
    "D4": "隔音问题",

    "E1": "预订/渠道信息",
    "E2": "房型不符",
    "E3": "价格争议",
    "E4": "退款/取消",
    "E5": "延时退房",

    "F1": "客遗物品",
    "F2": "人身安全",
    "F3": "特殊需求",
    "F4": "其他",
}


AGGREGATED_COLUMNS = [
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


STRUCTURED_METADATA_COLUMNS = [
    "complaint_id",
    "record_id",
    "source_complaint_id",
    *METADATA_COLUMNS,
]


INGESTED_FILE = "01_ingested_records.csv"
PREPARED_FILE = "02_prepared_complaints.csv"
SPLIT_COMPLAINTS_FILE = "03_split_complaints.csv"
SPLIT_AUDIT_FILE = "03_split_audit.csv"
NORMALIZED_FILE = "04_normalized_complaints.csv"
DEDUP_CANDIDATES_FILE = "04_dedup_candidates.csv"
DEDUP_AUDIT_FILE = "05_dedup_audit.csv"
DEDUPLICATED_FILE = "05_deduplicated_complaints.csv"
FILTER_AUDIT_FILE = "06_filter_audit.csv"
FILTERED_FILE = "06_filtered_complaints.csv"
STRUCTURED_FILE = "07_structured_complaints.csv"
ISSUE_REVIEW_FILE = "08_issue_review.csv"
RUN_SUMMARY_FILE = "run_summary.json"
REVIEW_SPLIT_FILE = "review_split.md"
REVIEW_DEDUP_FILE = "review_dedup.md"
REVIEW_NO_ISSUE_FILE = "review_no_issue.md"
REVIEW_ISSUE_FILE = "review_issue_review.md"


ALL_ARTIFACTS = [
    INGESTED_FILE,
    PREPARED_FILE,
    SPLIT_COMPLAINTS_FILE,
    SPLIT_AUDIT_FILE,
    NORMALIZED_FILE,
    DEDUP_CANDIDATES_FILE,
    DEDUP_AUDIT_FILE,
    DEDUPLICATED_FILE,
    FILTER_AUDIT_FILE,
    FILTERED_FILE,
    STRUCTURED_FILE,
    ISSUE_REVIEW_FILE,
    RUN_SUMMARY_FILE,
]
