#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_INPUT_DIR = Path(r"C:\Users\ar.kartavtsev\Desktop\Chunking\my-git-repo\html_markdown")
DEFAULT_OUTPUT_DIR = Path(r"C:\Users\ar.kartavtsev\Desktop\Chunking\markdown_chunks")


def get_token_counter():
    """Инициализирует token counter (tiktoken, fallback по символам)."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return lambda text: len(enc.encode(text))
    except ImportError:
        print("WARNING: tiktoken не установлен, использую fallback (len(text)//4).")
        return lambda text: len(text) // 4


def get_splitters(token_counter, max_tokens: int, overlap_tokens: int):
    """Создает markdown и recursive splitters."""
    # Пользователь попросил именно этот импорт; оставляем, но добавляем fallback.
    try:
        from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
    except ImportError:
        from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

    headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)

    rec_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_tokens,
        chunk_overlap=overlap_tokens,
        length_function=token_counter,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ": ", " ", ""],
        keep_separator=True,
    )
    return md_splitter, rec_splitter


def iter_markdown_files(root_dir: Path):
    """Итерирует markdown-файлы, игнорируя служебные подпапки *_files."""
    for file_path in sorted(root_dir.rglob("*.md")):
        if any(part.endswith("_files") for part in file_path.parts):
            continue
        yield file_path


def merge_small_chunks(docs, token_counter, min_tokens: int, max_tokens: int):
    """Сливает короткие чанки с соседями в рамках одинаковых h1/h2/h3."""
    items = []
    for doc in docs:
        text = (doc.page_content or "").strip()
        if not text:
            continue
        items.append(
            {
                "text": text,
                "tokens": token_counter(text),
                "metadata": dict(doc.metadata or {}),
            }
        )

    idx = 0
    while idx < len(items):
        current = items[idx]
        if current["tokens"] >= min_tokens:
            idx += 1
            continue

        merged = False

        if idx + 1 < len(items):
            right = items[idx + 1]
            if current["metadata"] == right["metadata"]:
                merged_text = current["text"] + "\n\n" + right["text"]
                merged_tokens = token_counter(merged_text)
                if merged_tokens <= max_tokens:
                    items[idx + 1] = {
                        "text": merged_text,
                        "tokens": merged_tokens,
                        "metadata": right["metadata"],
                    }
                    del items[idx]
                    merged = True

        if not merged and idx > 0:
            left = items[idx - 1]
            if current["metadata"] == left["metadata"]:
                merged_text = left["text"] + "\n\n" + current["text"]
                merged_tokens = token_counter(merged_text)
                if merged_tokens <= max_tokens:
                    items[idx - 1] = {
                        "text": merged_text,
                        "tokens": merged_tokens,
                        "metadata": left["metadata"],
                    }
                    del items[idx]
                    idx -= 1
                    merged = True

        if not merged:
            idx += 1

    return items


def save_txt(output_path: Path, source_file: Path, chunks):
    """Сохраняет чанки в человекочитаемый txt."""
    token_counts = [item["tokens"] for item in chunks]
    avg_tokens = (sum(token_counts) / len(token_counts)) if token_counts else 0

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Source file: {source_file}\n")
        f.write(f"Total chunks: {len(chunks)}\n")
        f.write("Chunk size target: 500-800 tokens, overlap: 15%\n")
        f.write("=" * 80 + "\n\n")
        f.write(
            f"Statistics: Min={min(token_counts) if token_counts else 0} tokens, "
            f"Max={max(token_counts) if token_counts else 0} tokens, "
            f"Avg={avg_tokens:.0f} tokens\n"
        )
        f.write("=" * 80 + "\n\n")

        for i, item in enumerate(chunks, 1):
            document_title = item.get("document", "")
            h1 = item["metadata"].get("h1", "")
            h2 = item["metadata"].get("h2", "")
            h3 = item["metadata"].get("h3", "")
            text = item["text"]
            tokens = item["tokens"]

            f.write(f"--- CHUNK {i} ({tokens} tokens / {len(text)} chars) ---\n")
            f.write(f"Document: {document_title}\n")
            f.write(f"H1: {h1}\n")
            f.write(f"H2: {h2}\n")
            f.write(f"H3: {h3}\n\n")
            f.write(text + "\n\n")


def save_jsonl(output_path: Path, source_file: Path, chunks):
    """Сохраняет чанки в JSONL (одна строка = один JSON-объект)."""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, item in enumerate(chunks, 1):
            payload = {
                "chunk_index": i,
                "source_file": str(source_file),
                "document": item.get("document", ""),
                "h1": item["metadata"].get("h1", ""),
                "h2": item["metadata"].get("h2", ""),
                "h3": item["metadata"].get("h3", ""),
                "tokens": item["tokens"],
                "chars": len(item["text"]),
                "text": item["text"],
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def process_markdown_file(md_file: Path, output_dir: Path, token_counter):
    """Читает markdown, чанкует и сохраняет результаты."""
    text = md_file.read_text(encoding="utf-8", errors="ignore")
    document_title = md_file.stem

    min_tokens = 500
    max_tokens = 800
    overlap_tokens = int(max_tokens * 0.15)  # 15%

    md_splitter, rec_splitter = get_splitters(token_counter, max_tokens, overlap_tokens)

    # 1) Разделение по заголовкам
    sections = md_splitter.split_text(text)

    # 2) Рекурсивный fallback для длинных секций
    split_docs = rec_splitter.split_documents(sections)

    # 3) Пост-слияние слишком коротких чанков
    merged_chunks = merge_small_chunks(split_docs, token_counter, min_tokens=min_tokens, max_tokens=max_tokens)

    # Добавляем название документа в каждый чанк для последующей трассировки источника.
    for chunk in merged_chunks:
        chunk["document"] = document_title

    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = md_file.stem.replace(" ", "_")

    txt_path = output_dir / f"{base_name}_chunks.txt"
    jsonl_path = output_dir / f"{base_name}_chunks.jsonl"

    save_txt(txt_path, md_file, merged_chunks)
    save_jsonl(jsonl_path, md_file, merged_chunks)

    print(f"OK: {md_file}")
    print(f"   overlap (fallback): {overlap_tokens} tokens")
    print(f"   -> {txt_path}")
    print(f"   -> {jsonl_path}")


def main():
    parser = argparse.ArgumentParser(description="Chunk markdown files by headings with LangChain splitters")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {args.input_dir}")

    token_counter = get_token_counter()
    md_files = list(iter_markdown_files(args.input_dir))

    if not md_files:
        print("No markdown files found.")
        return

    print(f"Found {len(md_files)} markdown file(s).")
    for md_file in md_files:
        process_markdown_file(md_file, args.output_dir, token_counter)


if __name__ == "__main__":
    main()
