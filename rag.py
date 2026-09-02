"""Runtime side of the manual RAG pipeline: classify -> retrieve -> answer.

Knowledge base is built offline by scripts/build_knowledge_base.py into knowledge/.
"""
import json
from pathlib import Path

from openai import OpenAI

MODEL = "gpt-5.4"
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
MAX_CONTEXT_CHARS = 20000  # cap retrieved deck text sent to the answering call


def load_index():
    index_path = KNOWLEDGE_DIR / "index.json"
    if not index_path.exists():
        return []
    return json.loads(index_path.read_text(encoding="utf-8"))["files"]


def _catalog_text(index):
    lines = []
    for f in index:
        topics = ", ".join(f["topics"])
        lines.append(f'- {f["filename"]}\n  topics: {topics}\n  summary: {f["summary"]}')
    return "\n".join(lines)


def classify_question(client: OpenAI, question: str, index: list) -> str | None:
    """Return the filename most likely to contain the answer, or None."""
    if not index:
        return None

    prompt = (
        "A student asked a question about course lecture slides. Below is a catalog of "
        "available slide decks (filename, topics, summary). Pick the ONE deck most likely "
        "to contain the answer. Respond with ONLY the exact filename, or the word NONE if "
        "no deck is clearly relevant.\n\n"
        f"Catalog:\n{_catalog_text(index)}\n\n"
        f"Question: {question}"
    )
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = resp.choices[0].message.content.strip().strip('"')
    except Exception:
        return None

    valid_filenames = {f["filename"] for f in index}
    if answer in valid_filenames:
        return answer
    # tolerate minor formatting (e.g. leading "- " or trailing punctuation)
    for name in valid_filenames:
        if name in answer:
            return name
    return None


def load_deck(filename: str) -> dict | None:
    path = KNOWLEDGE_DIR / filename
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def deck_to_context(deck: dict) -> str:
    lines = [f"Source: {deck['source_file']}"]
    for s in deck["slides"]:
        header = f"[Slide {s['slide_number']}] {s['title']}".strip()
        lines.append(header)
        for c in s["content"]:
            lines.append(f"- {c}")
        if s["notes"]:
            lines.append(f"(notes) {s['notes']}")
    text = "\n".join(lines)
    return text[:MAX_CONTEXT_CHARS]


def answer_question(client: OpenAI, question: str, system_prompt: dict) -> tuple[str, str | None]:
    """Run the full pipeline. Returns (reply, source_filename_or_None)."""
    index = load_index()
    filename = classify_question(client, question, index)

    if filename is None:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[system_prompt, {"role": "user", "content": question}],
        )
        return resp.choices[0].message.content, None

    deck = load_deck(filename)
    context = deck_to_context(deck)

    augmented_prompt = {
        "role": "system",
        "content": (
            system_prompt["content"]
            + "\n\nAnswer using ONLY the following lecture material. If the material does "
            "not contain the answer, only then generate the answer by your self\n\n"
            + context
        ),
    }
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[augmented_prompt, {"role": "user", "content": question}],
    )
    return resp.choices[0].message.content, filename
