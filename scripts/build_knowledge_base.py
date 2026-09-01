"""
Offline ingestion: data/*.pptx -> knowledge/*.json + knowledge/index.json

Run once (and again whenever data/ changes):
    py scripts/build_knowledge_base.py [--force]

Slide text is extracted verbatim (no LLM rewriting, no hallucination risk).
The LLM is only used to produce a topic list / summary / descriptive filename
for each deck, which the runtime router uses to pick the right file.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from extract_pptx import extract_slides

load_dotenv()

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = ROOT / "knowledge"
MODEL = "gpt-5.4"
MAX_RAW_CHARS_FOR_LLM = 20000  # cap what we send the LLM for topic/summary extraction
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 3

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def slugify(text, max_words=None):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = re.sub(r"-+", "-", text)
    if max_words:
        text = "-".join(text.split("-")[:max_words])
    return text


def slides_to_text(slides):
    lines = []
    for s in slides:
        if s["title"]:
            lines.append(f"[Slide {s['slide_number']}] {s['title']}")
        else:
            lines.append(f"[Slide {s['slide_number']}]")
        for c in s["content"]:
            lines.append(f"- {c}")
        if s["notes"]:
            lines.append(f"(notes) {s['notes']}")
    return "\n".join(lines)


def classify_deck(source_name, raw_text):
    """Ask the LLM for topics/summary/filename_slug describing this deck.
    Retries transient failures a couple of times before falling back to a
    heuristic (used_llm=False) if no API key / all attempts fail."""
    prompt = (
        "You are cataloging a university lecture slide deck for a retrieval system. "
        "Given the slide content below, respond with ONLY a JSON object (no markdown fences) "
        "with keys:\n"
        '  "topics": a list of 8-15 short, specific keyword phrases covering every distinct '
        "concept/term/case-study/framework/name mentioned (these are used to match student "
        "questions to this deck, so be specific and exhaustive rather than generic),\n"
        '  "summary": a 2-3 sentence summary of what the deck covers,\n'
        '  "filename_slug": a descriptive kebab-case slug (8-14 words) summarizing the deck\'s '
        "content, suitable for a filename.\n\n"
        f"Deck source file: {source_name}\n\n"
        f"Slide content:\n{raw_text[:MAX_RAW_CHARS_FOR_LLM]}"
    )

    for attempt in range(1, MAX_RETRIES + 2):  # initial attempt + retries
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            topics = [str(t).strip() for t in data.get("topics", []) if str(t).strip()]
            summary = str(data.get("summary", "")).strip()
            filename_slug = slugify(str(data.get("filename_slug", "")), max_words=14)
            if topics and summary and filename_slug:
                return topics, summary, filename_slug, True
            raise ValueError(f"incomplete LLM response: {data}")
        except Exception as e:
            is_last = attempt == MAX_RETRIES + 1
            print(f"  ! LLM cataloging failed for {source_name} "
                  f"(attempt {attempt}/{MAX_RETRIES + 1}): {e}", file=sys.stderr)
            if not is_last:
                time.sleep(RETRY_DELAY_SECONDS)

    # Heuristic fallback: use slide titles as topics, no LLM required.
    stem = Path(source_name).stem
    return [stem], f"Slide deck: {stem}", slugify(stem, max_words=14), False


def build_filename(source_stem, filename_slug, topics):
    topic_slugs = [slugify(t, max_words=4) for t in topics]
    topic_part = "_".join(topic_slugs)
    name = f"{slugify(source_stem)}__{filename_slug}__topics_{topic_part}"
    return name[:180] + ".json"


def process_pptx(pptx_path, existing_sources, force):
    source_name = pptx_path.name
    if not force and source_name in existing_sources:
        print(f"= skip (already built): {source_name}")
        return None

    print(f"> processing: {source_name}")
    slides = extract_slides(pptx_path)
    raw_text = slides_to_text(slides)
    topics, summary, filename_slug, used_llm = classify_deck(source_name, raw_text)
    filename = build_filename(pptx_path.stem, filename_slug, topics)

    entry = {
        "source_file": source_name,
        "topics": topics,
        "summary": summary,
        "slides": slides,
    }
    (KNOWLEDGE_DIR / filename).write_text(
        json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  -> knowledge/{filename}  ({len(slides)} slides)")

    return {
        "filename": filename,
        "source_file": source_name,
        "topics": topics,
        "summary": summary,
    }, used_llm


def main():
    force = "--force" in sys.argv
    KNOWLEDGE_DIR.mkdir(exist_ok=True)

    index_path = KNOWLEDGE_DIR / "index.json"
    index = {"files": []}
    if index_path.exists() and not force:
        index = json.loads(index_path.read_text(encoding="utf-8"))

    existing_sources = {f["source_file"] for f in index["files"]}
    if force:
        existing_sources = set()
        index = {"files": []}

    pptx_files = sorted(DATA_DIR.glob("*.pptx"))
    if not pptx_files:
        print(f"No .pptx files found in {DATA_DIR}")
        return

    llm_classified = 0
    heuristic_fallback = 0
    failed = []

    for pptx_path in pptx_files:
        try:
            outcome = process_pptx(pptx_path, existing_sources, force)
        except Exception as e:
            print(f"  ! failed to process {pptx_path.name}, skipping: {e}", file=sys.stderr)
            failed.append(pptx_path.name)
            continue

        if outcome:
            entry, used_llm = outcome
            index["files"] = [f for f in index["files"] if f["source_file"] != entry["source_file"]]
            index["files"].append(entry)
            if used_llm:
                llm_classified += 1
            else:
                heuristic_fallback += 1

    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nIndex written: knowledge/index.json ({len(index['files'])} decks)")
    print(f"Classified this run: {llm_classified} via LLM, {heuristic_fallback} via heuristic fallback"
          + (f", {len(failed)} failed ({', '.join(failed)})" if failed else ""))


if __name__ == "__main__":
    main()
