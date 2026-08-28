import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate



PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = (PROJECT_ROOT / "prompts" / "dedup_prompt.md")

load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.environ["DEEPSEEK_API_KEY"]
BASE_URL = os.environ["DEEPSEEK_BASE_URL"]
MODEL = os.environ["DEEPSEEK_MODEL"]

SYSTEM_PROMPT = PROMPT_PATH.read_text(
    encoding="utf-8"
)



class LLMDeduplicator:
    def __init__(self):

        self.llm = ChatOpenAI(
            model=MODEL,
            api_key=API_KEY,
            base_url=BASE_URL,
            temperature=0,
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            (
                "human",
                "投诉 A：\n{content_a}\n\n"
                "投诉 B：\n{content_b}",
            ),
        ])

    def is_duplicate(
        self,
        complaint_a,
        complaint_b,
    ):

        messages = self.prompt.format_messages(
            content_a=complaint_a["content"],
            content_b=complaint_b["content"],
        )

        response = self.llm.invoke(messages)

        result = (
            response.content
            .strip()
            .upper()
        )

        return result == "YES"

    def is_duplicate_batch(
        self,
        pairs,
        max_concurrency=10,
    ):
        messages = [
            self.prompt.format_messages(
                content_a=complaint_a["content"],
                content_b=complaint_b["content"],
            )
            for complaint_a, complaint_b in pairs
        ]

        results = [None] * len(messages)

        total = len(messages)
        completed = 0

        for index, response in self.llm.batch_as_completed(
            messages,
            config={"max_concurrency": max_concurrency},
        ):
            result = (
                response.content
                .strip()
                .upper()
            )

            results[index] = (
                result == "YES"
            )

            completed += 1

            print(
                f"LLM dedup progress: "
                f"{completed}/{total}",
                end="\r",
                flush=True,
            )

        return results