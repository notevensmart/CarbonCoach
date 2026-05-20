import ast
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI


_classify_chain = None

prompt = PromptTemplate(
    input_variables=["journal_entry"],
    template="""
You are a carbon activity classifier.

Given a personal journal entry, extract a list of activity labels along with their category. Each item must be a tuple of the form (label, category).

Categories must be one of:
- "transport"
- "waste"
- "energy"
- "goods_services"

Journal entry:
"{journal_entry}"

Respond with ONLY a valid Python list of (label, category) tuples.
No explanations. No markdown. No code blocks. No extra text.

Example:
[("bus ride", "transport"), ("recycle plastic", "waste")]
""",
)


def classify_activities(journal_entry: str) -> list[tuple[str, str]]:
    try:
        response = _get_classify_chain().invoke({"journal_entry": journal_entry})
        activity_pairs = ast.literal_eval(response.content.strip())
        if isinstance(activity_pairs, list):
            return activity_pairs
    except Exception:
        pass
    return heuristic_classify_activities(journal_entry)


def heuristic_classify_activities(journal_entry: str) -> list[tuple[str, str]]:
    text = journal_entry.lower()
    rules = [
        ("bus ride", "transport", ("bus",)),
        ("train ride", "transport", ("train", "rail")),
        ("flight", "transport", ("flight", "flew", "plane")),
        ("car trip", "transport", ("drive", "drove", "car", "uber", "taxi")),
        ("electricity use", "energy", ("electricity", "kwh", "power")),
        ("natural gas use", "energy", ("natural gas", "gas bill")),
        ("waste disposal", "waste", ("trash", "landfill", "waste", "garbage")),
        ("recycling", "waste", ("recycle", "recycled", "recycling")),
        ("food or goods purchase", "goods_services", ("bought", "purchase", "meal", "coffee")),
    ]
    matches = [
        (label, category)
        for label, category, keywords in rules
        if any(keyword in text for keyword in keywords)
    ]
    return matches or [("daily activity", "goods_services")]


def _get_classify_chain():
    global _classify_chain
    if _classify_chain is None:
        _load_env_file("key.env")
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("Missing OPENROUTER_API_KEY.")
        llm = ChatOpenAI(
            model="anthropic/claude-3-haiku",
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            temperature=0,
        )
        _classify_chain = prompt | llm
    return _classify_chain


def _load_env_file(filename: str) -> None:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / filename
        if candidate.exists():
            load_dotenv(dotenv_path=candidate)
            return
