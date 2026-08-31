# 酒店客诉分析流水线

将日/周/月报表和平台评价整理成统一的投诉记录，经过拆分、归一化、去重、过滤和结构化，最后自动生成可视化 Dashboard。

## 功能流程

1. `extract`：读取输入目录下的 Excel 报表与平台评价，聚合成统一记录
2. `process`：清洗文本，补充事件日期等基础字段
3. `split`：由 LLM 把一条记录拆成多个独立投诉
4. `normalize`：抽取房间号等字段并标准化
5. `dedup`：精确去重后，再用 LLM 判断语义重复
6. `filter`：按审核结果过滤，保留有效投诉
7. `structure`：由 LLM 结构化投诉内容并抽取 issue
8. `issue review`：生成逐条 issue 分析表
9. `dashboard`：自动生成 Plotly Dashboard HTML

## 目录结构

```text
inputs/
  samples/          # sample data
  local/            # 本地真实数据（不入库）
prompts/            # LLM prompt
src/                # 源码
outputs/
  runs/<RUN_ID>/    # 每轮运行的中间产物与摘要
  reports/<RUN_ID>/ # 人工审核报告与 Dashboard
```

## 环境准备

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 运行方式

直接运行入口：

```bash
python src/main.py
```

启动后会显示当前运行配置，并提供三个选项：

1. 使用 sample data 跑全流程（默认，直接回车即可）
2. 设置环境变量后再运行（配置会写入 `.env`）
3. 退出

如果运行范围包含拆分、去重或结构化阶段，但缺少 LLM 配置，程序会提示补填；选择跳过时会给出指引并退出，不会跑到一半才报错。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `INPUT_DIR` | `inputs/samples` | 输入目录，需包含 `daily_reports`、`weekly_reports`、`monthly_reports`、`platform_reviews` |
| `RUN_ID` | `sample` | 运行目录名，中间产物输出到 `outputs/runs/<RUN_ID>`，报告输出到 `outputs/reports/<RUN_ID>` |
| `START_FROM` | `extract` | 起始阶段 |
| `END_FROM` | `structure` | 结束阶段 |
| `LLM_API_KEY` | 无 | LLM API Key |
| `LLM_BASE_URL` | 无 | LLM Base URL，例如 `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 无 | LLM 模型名，例如 `deepseek-chat` |

`.env` 示例：

```dotenv
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
INPUT_DIR=inputs/samples
RUN_ID=sample
```

`.env` 已被 `.gitignore` 忽略，请勿把真实密钥提交到版本库。

## 自定义运行范围

只跑到 `process` 阶段（PowerShell）：

```powershell
$env:START_FROM = "extract"
$env:END_FROM = "process"
python src/main.py
```

从已有产物继续（Windows CMD）：

```bat
set START_FROM=structure
set END_FROM=structure
python src/main.py
```

从中间阶段开始时，程序会从同一个运行目录加载上游产物；如果上游文件不存在，会给出提示并要求先跑全流程。

## 输出

- `outputs/runs/<RUN_ID>/01_ingested_records.csv` 至 `08_issue_review.csv`：各阶段产物
- `outputs/runs/<RUN_ID>/run_summary.json`：运行摘要，包含起止阶段、计数和产物列表
- `outputs/reports/<RUN_ID>/review_split.md`：Split 实际拆分条目的人工审核报告
- `outputs/reports/<RUN_ID>/review_dedup.md`：去重条目对照的人工审核报告
- `outputs/reports/<RUN_ID>/review_no_issue.md`：Structurer 判定无问题条目的人工审核报告
- `outputs/reports/<RUN_ID>/review_issue_review.md`：面向人工阅读的 Issue 审核报告
- `outputs/reports/<RUN_ID>/dashboard.html`：自动生成的 Dashboard

带 `review_` 前缀的报告只包含人工检验需要的字段，仅用于阅读，不会被后续流程读取。

如果当前运行没有包含 `structure` 阶段，Dashboard 会自动跳过；也可以单独运行 `python src/analysis.py` 重新生成当前 `RUN_ID` 对应的看板。

## 常见问题

**提示 LLM 配置缺失**

选择启动菜单中的“设置环境变量”，或编辑 `.env` 补齐 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。

**提示缺少上游产物**

当前 `RUN_ID` 下还没有对应阶段的中间文件。先用 sample data 跑一次全流程，或把 `START_FROM` 改回 `extract`。

**Dashboard 没有生成**

检查当前运行是否包含 `structure` 阶段，并确认 `outputs/runs/<RUN_ID>/07_structured_complaints.csv` 存在。
