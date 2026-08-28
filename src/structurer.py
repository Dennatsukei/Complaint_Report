import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate



PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = (PROJECT_ROOT / "prompts" / "structurer_prompt.md")

load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.environ["DEEPSEEK_API_KEY"]
BASE_URL = os.environ["DEEPSEEK_BASE_URL"]
MODEL = os.environ["DEEPSEEK_MODEL"]

SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")



class LLMStructurer:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=MODEL,
            api_key=API_KEY, # type: ignore
            base_url=BASE_URL,
            temperature=0,
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "{content}"),
        ])

    def structure(self, content):
        messages = self.prompt.format_messages(
            content=content
        )

        response = self.llm.invoke(messages)

        return self.parse_response(response.content)

    def structure_batch(
        self,
        contents,
        max_concurrency=10,
    ):
        messages = [
            self.prompt.format_messages(content=content)
            for content in contents
        ]

        results = [None] * len(messages)

        completed = 0
        total = len(messages)

        for index, response in self.llm.batch_as_completed(
            messages,
            config={"max_concurrency": max_concurrency},
        ):
            results[index] = self.parse_response(
                response.content
            )

            completed += 1

            print(
                f"Structuring progress: "
                f"{completed}/{total}",
                end="\r",
                flush=True,
            )

        print()

        return results

    @staticmethod
    def parse_response(text):
        text = text.strip()

        try:
            return json.loads(text)

        except json.JSONDecodeError:
            raise ValueError(
                f"Invalid JSON response:\n{text}"
            )