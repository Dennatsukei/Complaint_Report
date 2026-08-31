import json

from langchain_core.prompts import ChatPromptTemplate
from llm_runtime import create_chat_model, load_system_prompt, process_batch


SYSTEM_PROMPT = load_system_prompt("structurer_prompt.md")



class LLMStructurer:
    def __init__(self):
        self.llm = create_chat_model()

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

        return process_batch(
            self.llm,
            messages,
            lambda _, text: self.parse_response(text),
            max_concurrency=max_concurrency,
            progress_label="Structuring progress",
            finish_with_newline=True,
        )

    @staticmethod
    def parse_response(text):
        text = text.strip()

        try:
            return json.loads(text)

        except json.JSONDecodeError:
            raise ValueError(
                f"Invalid JSON response:\n{text}"
            )
