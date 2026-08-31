from langchain_core.prompts import ChatPromptTemplate
from llm_runtime import create_chat_model, load_system_prompt, process_batch


SYSTEM_PROMPT = load_system_prompt("dedup_prompt.md")



class LLMDeduplicator:
    def __init__(self):

        self.llm = create_chat_model()

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

        return process_batch(
            self.llm,
            messages,
            lambda _, text: text.strip().upper() == "YES",
            max_concurrency=max_concurrency,
            progress_label="LLM dedup progress",
        )
