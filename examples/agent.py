"""A small example of the kind of code promptlint is meant to read."""

SYSTEM_PROMPT = """You are a research assistant.
Use the OpenAI key sk-proj-A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8 when calling tools.
Answer the user's question: {question}
Keep it under {max_words} words."""


def build(question: str) -> str:
    return SYSTEM_PROMPT.format(question=question, tone="formal")
