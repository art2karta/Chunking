#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chunking script for Word documents using LangChain splitters.

Input modes:
1. Explicit list of files in input_files
2. All .docx files from input_dir

Chunking flow:
- Clean paragraphs
- Split by markdown headers with MarkdownHeaderTextSplitter
- Split oversized sections with RecursiveCharacterTextSplitter
- Build final chunks with min/max token limits
- Add adaptive overlap between neighboring chunks
"""

import re
from pathlib import Path


def get_token_counter():
    """Initialize token counter for GPT-style tokenization."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return lambda text: len(enc.encode(text))
    except ImportError:
        print("WARNING: tiktoken not installed. Using character-based counting as fallback.")
        print("Install tiktoken: pip install tiktoken")
        # Simple fallback: around 4 chars ~= 1 token
        return lambda text: len(text) // 4


def extract_document_title(paragraphs) -> str:
    """Extract document title from the first non-empty paragraph."""
    for para in paragraphs[:5]:
        text = para.text.strip()
        if text:
            return text.split("\n")[0][:100]
    return "Unknown Document"


def extract_sidebar_value(paragraphs, re_module) -> str:
    """Extract value from line matching 'sidebar: value'."""
    sidebar_re = re_module.compile(r"^\s*sidebar\s*:\s*(.+?)\s*$", re_module.IGNORECASE)
    for para in paragraphs:
        text = para.text.strip()
        if not text:
            continue
        match = sidebar_re.match(text)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return ""


def clean_paragraphs(paragraphs, re_module):
    """Return cleaned non-empty paragraphs excluding sidebar line."""
    cleaned = []
    sidebar_re = re_module.compile(r"^\s*sidebar\s*:\s*.+$", re_module.IGNORECASE)

    for paragraph in paragraphs:
        text = paragraph.text.strip()
        if text and not sidebar_re.match(text):
            text = re_module.sub(r" +", " ", text)
            cleaned.append(text)

    return cleaned


def prepare_units_with_langchain(cleaned_paragraphs, token_counter, max_chunk_tokens):
    """Build intermediate units using LangChain markdown + recursive splitters."""
    from langchain_text_splitters import (
        MarkdownHeaderTextSplitter,
        RecursiveCharacterTextSplitter,
    )

    markdown_text = "\n\n".join(cleaned_paragraphs).strip()
    if not markdown_text:
        return []

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "header_1"),
            ("##", "header_2"),
            ("###", "header_3"),
        ],
        strip_headers=False,
    )

    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chunk_tokens,
        chunk_overlap=0,
        length_function=token_counter,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", " ", ""],
        keep_separator=True,
    )

    header_docs = header_splitter.split_text(markdown_text)
    prepared_units = []

    for doc in header_docs:
        section = doc.page_content.strip()
        if not section:
            continue

        for part in recursive_splitter.split_text(section):
            chunk = part.strip()
            if chunk:
                prepared_units.append(chunk)

    return prepared_units


def merge_small_chunks(chunk_info, token_counter, min_merge_tokens, max_chunk_tokens):
    """Merge too-small chunks with neighbors if merged text still fits the limit."""
    items = [{"text": text, "tokens": tokens} for text, tokens in chunk_info]
    index = 0

    while index < len(items):
        current = items[index]
        if current["tokens"] >= min_merge_tokens:
            index += 1
            continue

        merged = False

        if index + 1 < len(items):
            merged_text = current["text"] + "\n" + items[index + 1]["text"]
            merged_tokens = token_counter(merged_text)
            if merged_tokens <= max_chunk_tokens:
                items[index + 1] = {"text": merged_text, "tokens": merged_tokens}
                del items[index]
                merged = True

        if not merged and index > 0:
            merged_text = items[index - 1]["text"] + "\n" + current["text"]
            merged_tokens = token_counter(merged_text)
            if merged_tokens <= max_chunk_tokens:
                items[index - 1] = {"text": merged_text, "tokens": merged_tokens}
                del items[index]
                index -= 1
                merged = True

        if not merged:
            index += 1

    return [(item["text"], item["tokens"]) for item in items]


def build_chunks(
    prepared_units,
    token_counter,
    min_chunk_tokens,
    max_chunk_tokens,
    max_chunk_tokens_with_overlap,
    min_merge_tokens,
):
    """Build chunks with adaptive overlap from prepared text units."""
    current_chunk = []
    current_tokens = 0
    chunk_info = []

    def chunk_text_and_tokens(parts):
        text = "\n".join(parts)
        return text, token_counter(text)

    for unit in prepared_units:
        unit_tokens = token_counter(unit)
        _, prospective_tokens = chunk_text_and_tokens(current_chunk + [unit])

        if prospective_tokens > max_chunk_tokens:
            if current_chunk and current_tokens >= min_chunk_tokens:
                chunk_text, chunk_tokens = chunk_text_and_tokens(current_chunk)
                chunk_info.append((chunk_text, chunk_tokens))
                current_chunk = [unit]
                current_tokens = unit_tokens
            elif (not current_chunk) or (current_tokens < min_chunk_tokens and unit_tokens <= 200):
                current_chunk.append(unit)
                _, current_tokens = chunk_text_and_tokens(current_chunk)
            elif current_chunk:
                chunk_text, chunk_tokens = chunk_text_and_tokens(current_chunk)
                chunk_info.append((chunk_text, chunk_tokens))
                current_chunk = [unit]
                current_tokens = unit_tokens
        else:
            current_chunk.append(unit)
            current_tokens = prospective_tokens

    if current_chunk:
        chunk_text, chunk_tokens = chunk_text_and_tokens(current_chunk)
        chunk_info.append((chunk_text, chunk_tokens))

    chunk_info = merge_small_chunks(chunk_info, token_counter, min_merge_tokens, max_chunk_tokens)

    chunks_with_overlap = []
    for i, (chunk_text, tokens) in enumerate(chunk_info):
        if i > 0:
            prev_tokens = chunk_info[i - 1][1]
            overlap_percent = 0.40 if prev_tokens < min_chunk_tokens else 0.15
            ideal_overlap_tokens = int(prev_tokens * overlap_percent)
            max_possible_overlap = max(0, max_chunk_tokens_with_overlap - tokens)
            overlap_tokens = min(ideal_overlap_tokens, max_possible_overlap)

            prev_lines = chunk_info[i - 1][0].split("\n")
            overlap_text = ""
            overlap_count = 0

            for line in reversed(prev_lines):
                line_tokens = token_counter(line)
                if overlap_count + line_tokens <= overlap_tokens:
                    overlap_text = line + "\n" + overlap_text
                    overlap_count += line_tokens
                else:
                    break

            if overlap_text:
                chunk_text = overlap_text + chunk_text

        chunks_with_overlap.append(chunk_text)

    return chunks_with_overlap


def collect_input_files(input_files, input_dir):
    """Return unique existing .docx files to process."""
    resolved_files = []

    if input_files:
        for file_path in input_files:
            path_obj = Path(file_path)
            if path_obj.exists() and path_obj.suffix.lower() == ".docx":
                resolved_files.append(path_obj)
            else:
                print(f"WARNING: skipped invalid file: {file_path}")

    if input_dir:
        dir_path = Path(input_dir)
        if not dir_path.exists():
            print(f"WARNING: input directory not found: {input_dir}")
        else:
            resolved_files.extend(sorted(dir_path.rglob("*.docx")))

    unique_files = []
    seen = set()
    for file_path in resolved_files:
        normalized = str(file_path.resolve()).lower()
        if normalized not in seen:
            seen.add(normalized)
            unique_files.append(file_path)

    return unique_files


def sanitize_filename_part(value):
    """Prepare filename part for Windows-safe filenames."""
    sanitized = re.sub(r'[<>:"/\\|?*]+', "_", value).strip()
    sanitized = re.sub(r"\s+", "_", sanitized)
    return sanitized or "unknown"


def build_output_filename(file_path):
    """Build output filename with source parent folder prefix."""
    parent_name = sanitize_filename_part(file_path.parent.name)
    stem_name = sanitize_filename_part(file_path.stem)
    return f"{parent_name}_{stem_name}_chunks_langchain.txt"


def save_chunks(
    output_path,
    document_label,
    source_file,
    chunks_with_overlap,
    token_counter,
    min_chunk_tokens,
    max_chunk_tokens,
    max_chunk_tokens_with_overlap,
):
    """Save chunks of one document into a dedicated txt file."""
    chunk_token_counts = [token_counter(chunk) for chunk in chunks_with_overlap]
    avg_tokens = sum(chunk_token_counts) / len(chunks_with_overlap) if chunks_with_overlap else 0

    with open(output_path, "w", encoding="utf-8") as file_obj:
        file_obj.write(f"Source file: {source_file}\n")
        file_obj.write(f"Document: {document_label}\n")
        file_obj.write(f"Total chunks: {len(chunks_with_overlap)}\n")
        file_obj.write(
            f"Chunk size before overlap: {min_chunk_tokens}-{max_chunk_tokens} tokens "
            "(LangChain: MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter)\n"
        )
        file_obj.write(
            f"Overlap: 15% (or 40% if previous chunk < {min_chunk_tokens} tokens), "
            f"target max with overlap: {max_chunk_tokens_with_overlap} tokens\n"
        )
        file_obj.write("=" * 80 + "\n\n")

        file_obj.write(f"Statistics: Min={min(chunk_token_counts) if chunks_with_overlap else 0} tokens, ")
        file_obj.write(f"Max={max(chunk_token_counts) if chunks_with_overlap else 0} tokens, ")
        file_obj.write(f"Avg={avg_tokens:.0f} tokens\n")
        file_obj.write("=" * 80 + "\n\n")

        for index, chunk in enumerate(chunks_with_overlap, 1):
            chunk_tokens = chunk_token_counts[index - 1]
            file_obj.write(f"--- CHUNK {index} ({chunk_tokens} tokens / {len(chunk)} chars) ---\n")
            file_obj.write(f"Document: {document_label}\n\n")
            file_obj.write(f"{chunk}\n\n")


def process_document(file_path, output_dir, token_counter, min_chunk_tokens, max_chunk_tokens, re_module, document_factory):
    """Process one document and save chunking result."""
    print(f"Reading: {file_path}")
    doc = document_factory(file_path)

    doc_title = extract_document_title(doc.paragraphs)
    print(f"Document title: {doc_title}")

    sidebar_value = extract_sidebar_value(doc.paragraphs, re_module)
    document_label = sidebar_value if sidebar_value else doc_title
    if sidebar_value:
        print(f"Sidebar label: {sidebar_value}")

    cleaned_paragraphs = clean_paragraphs(doc.paragraphs, re_module)
    print(f"Extracted: {len(cleaned_paragraphs)} paragraphs")

    prepared_units = prepare_units_with_langchain(
        cleaned_paragraphs,
        token_counter,
        max_chunk_tokens,
    )
    print(
        "Prepared: "
        f"{len(prepared_units)} units using MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter"
    )

    chunks_with_overlap = build_chunks(
        prepared_units,
        token_counter,
        min_chunk_tokens,
        max_chunk_tokens,
        max_chunk_tokens + 105,
        350,
    )
    print(f"Created {len(chunks_with_overlap)} chunks with adaptive overlap")

    output_path = output_dir / build_output_filename(file_path)
    save_chunks(
        output_path,
        document_label,
        str(file_path),
        chunks_with_overlap,
        token_counter,
        min_chunk_tokens,
        max_chunk_tokens,
        max_chunk_tokens + 105,
    )

    print(f"Saved to: {output_path}")
    if chunks_with_overlap:
        chunk_token_counts = [token_counter(chunk) for chunk in chunks_with_overlap]
        print(
            "Chunk tokens: "
            f"min={min(chunk_token_counts)}, "
            f"max={max(chunk_token_counts)}, "
            f"avg={sum(chunk_token_counts) / len(chunk_token_counts):.0f}"
        )


def main():
    import re

    try:
        from docx import Document
    except ImportError:
        print("ERROR: python-docx not installed. Install: pip install python-docx")
        return

    try:
        import langchain_text_splitters  # noqa: F401
    except ImportError:
        print("ERROR: langchain-text-splitters not installed. Install: pip install langchain-text-splitters")
        return

    token_counter = get_token_counter()

    min_chunk_tokens = 600
    max_chunk_tokens = 700

    input_files = [
        # r"c:\Users\ar.kartavtsev\Desktop\Chunking\Test2.docx",
        # r"c:\Users\ar.kartavtsev\Desktop\Chunking\Test3.docx",
    ]
    input_dir = r"c:\Users\ar.kartavtsev\Desktop\Chunking\my-git-repo\input_docs"
    output_dir = Path(r"c:\Users\ar.kartavtsev\Desktop\Chunking\my-git-repo\chunks_output")

    files_to_process = collect_input_files(input_files, input_dir)
    if not files_to_process:
        print("ERROR: no .docx files found for processing.")
        print("Add files to input_files or place .docx files into input_dir.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Found {len(files_to_process)} file(s) for processing")

    for file_path in files_to_process:
        process_document(
            file_path,
            output_dir,
            token_counter,
            min_chunk_tokens,
            max_chunk_tokens,
            re,
            Document,
        )
        print("-" * 80)


if __name__ == "__main__":
    main()
