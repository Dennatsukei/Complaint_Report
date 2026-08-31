import json

from langchain_core.prompts import ChatPromptTemplate
from llm_runtime import create_chat_model, load_system_prompt, process_batch


SYSTEM_PROMPT = load_system_prompt("split_prompt.md")


# ==================================================
# LLM Splitter
# ==================================================

class LLMSplit:
    def __init__(self):
        self.llm = create_chat_model()

        self.prompt = (
            ChatPromptTemplate.from_messages([
                (
                    "system",
                    SYSTEM_PROMPT,
                ),
                (
                    "human",
                    "{content}",
                ),
            ])
        )


    # ==================================================
    # Single
    # ==================================================

    def split(
        self,
        content,
    ):

        messages = (
            self.prompt
            .format_messages(
                content=content,
            )
        )

        response = self.llm.invoke(
            messages
        )

        split_points = (
            self.parse_response(
                response.content
            )
        )

        return self.split_content(
            content,
            split_points,
        )


    # ==================================================
    # Batch
    # ==================================================

    def split_batch(
        self,
        contents,
        max_concurrency=10,
    ):

        messages = [
            self.prompt.format_messages(
                content=content,
            )
            for content in contents
        ]

        return process_batch(
            self.llm,
            messages,
            lambda index, text: self.split_content(
                contents[index],
                self.parse_response(text),
            ),
            max_concurrency=max_concurrency,
            progress_label="Split progress",
            finish_with_newline=True,
        )


    # ==================================================
    # Parse LLM Response
    # ==================================================

    @staticmethod
    def parse_response(
        text,
    ):

        try:

            data = json.loads(
                text.strip()
            )

        except (
            json.JSONDecodeError,
            TypeError,
        ):

            return []


        if not isinstance(
            data,
            list,
        ):

            return []


        validated_points = []


        for item in data:

            if not isinstance(
                item,
                dict,
            ):
                continue


            anchor = item.get(
                "anchor"
            )

            occurrence = item.get(
                "occurrence",
                1,
            )


            if not isinstance(
                anchor,
                str,
            ):
                continue


            if not isinstance(
                occurrence,
                int,
            ):
                continue


            anchor = anchor.strip()


            if not anchor:
                continue


            if occurrence < 1:
                continue


            validated_points.append({
                "anchor": anchor,
                "occurrence": occurrence,
            })


        return validated_points


    # ==================================================
    # Find Anchor Position
    # ==================================================

    @staticmethod
    def find_nth_occurrence(
        text,
        substring,
        occurrence,
    ):

        start = 0

        position = -1


        for _ in range(
            occurrence
        ):

            position = text.find(
                substring,
                start,
            )

            if position == -1:

                return None


            start = (
                position
                + len(substring)
            )


        return position


    # ==================================================
    # Split Content
    # ==================================================

    def split_content(
        self,
        content,
        split_points,
    ):

        # No split requested
        if not split_points:

            return [content]


        positions = []


        for point in split_points:

            position = (
                self.find_nth_occurrence(
                    text=content,
                    substring=point[
                        "anchor"
                    ],
                    occurrence=point[
                        "occurrence"
                    ],
                )
            )


            # --------------------------------------------------
            # Safety:
            # If any anchor cannot be found,
            # abandon the entire split.
            # --------------------------------------------------

            if position is None:

                return [content]


            positions.append(
                position
            )


        # --------------------------------------------------
        # Safety validation
        # --------------------------------------------------

        positions = sorted(
            set(positions)
        )


        # All split points must be valid
        if not positions:

            return [content]


        if positions[0] <= 0:

            return [content]


        if positions[-1] >= len(content):

            return [content]


        # --------------------------------------------------
        # Build segments
        # --------------------------------------------------

        boundaries = [
            0,
            *positions,
            len(content),
        ]


        results = []


        for start, end in zip(
            boundaries,
            boundaries[1:],
        ):

            segment = (
                content[start:end]
                .strip()
            )


            if not segment:

                # Safety:
                # Empty segment means something is wrong.
                return [content]


            results.append(
                segment
            )


        return results
