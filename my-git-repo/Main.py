import argparse
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    HAS_LANGCHAIN = True
except Exception:
    HAS_LANGCHAIN = False

try:
    from unstructured.partition.md import partition_md

    HAS_UNSTRUCTURED = True
except Exception:
    HAS_UNSTRUCTURED = False

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True
except Exception:
    HAS_SENTENCE_TRANSFORMERS = False

try:
    from llama_index.core import Document
    from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes

    HAS_LLAMAINDEX = True
except Exception:
    HAS_LLAMAINDEX = False


FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"^\s*```")
INLINE_ENDPOINT_RE = re.compile(r"(/(?:routing|public_transport)/[^\s`'\")]+)")
HTTP_ENDPOINT_RE = re.compile(
    r"https?://routing\.api\.2gis\.com(/(?:routing|public_transport)/[^\s'\")]+)"
)
MD_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")


@dataclass
class HeadingBlock:
    title: str
    level: int
    path: list[str]
    body: str


def estimate_tokens(text: str) -> int:
    words = len(re.findall(r"\S+", text))
    punct = len(re.findall(r"[.,:;!?()\[\]{}]", text))
    return max(1, int(words * 1.18 + punct * 0.08))


def token_to_char_budget(tokens: int) -> int:
    # Russian API docs are usually between 3.5 and 4.5 chars/token.
    return max(256, int(tokens * 4))


def normalize_spaces(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def strip_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub("", text, count=1)


def clean_mdx_with_unstructured(text: str) -> str:
    raw = strip_frontmatter(text)

    if HAS_UNSTRUCTURED:
        try:
            elems = partition_md(text=raw)
            chunks: list[str] = []
            for elem in elems:
                elem_text = getattr(elem, "text", "")
                if elem_text:
                    chunks.append(elem_text.strip())
            joined = "\n\n".join(item for item in chunks if item)
            if joined.strip():
                return joined
        except Exception:
            pass

    # Fallback: keep headings and text, drop obvious HTML tags.
    raw = re.sub(r"<[^>]+>", "", raw)
    return raw


def extract_article_title(text: str, source_path: Path) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return normalize_spaces(m.group(1))
    return source_path.stem


def split_by_heading_level(text: str, level: int, base_path: list[str]) -> list[HeadingBlock]:
    pattern = re.compile(rf"^(#{{{level}}})\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    blocks: list[HeadingBlock] = []

    if not matches:
        return blocks

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = normalize_spaces(match.group(2))
        block_text = text[start:end].strip()
        lines = block_text.splitlines()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        blocks.append(
            HeadingBlock(
                title=title,
                level=level,
                path=[*base_path, title],
                body=body,
            )
        )

    return blocks


def find_endpoints(text: str) -> list[str]:
    endpoints = set()
    for endpoint in INLINE_ENDPOINT_RE.findall(text):
        endpoints.add(endpoint.rstrip(".,"))
    for endpoint in HTTP_ENDPOINT_RE.findall(text):
        endpoints.add(endpoint.rstrip(".,"))
    return sorted(endpoints)


def find_urls(text: str) -> list[str]:
    urls = set(MD_LINK_RE.findall(text))
    return sorted(urls)


def split_to_paragraphs(text: str) -> list[str]:
    lines = text.splitlines()
    paras: list[str] = []
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        nonlocal buf
        candidate = "\n".join(buf).strip()
        if candidate:
            paras.append(candidate)
        buf = []

    for line in lines:
        if FENCE_RE.match(line):
            if not in_fence:
                flush()
            in_fence = not in_fence
            buf.append(line)
            if not in_fence:
                flush()
            continue

        if in_fence:
            buf.append(line)
            continue

        if not line.strip():
            flush()
        else:
            buf.append(line)

    flush()
    return paras


def semantic_group_paragraphs(paragraphs: list[str], similarity_threshold: float = 0.62) -> list[str]:
    if not paragraphs:
        return []
    if len(paragraphs) == 1:
        return paragraphs

    if not HAS_SENTENCE_TRANSFORMERS:
        return paragraphs

    try:
        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        embeddings = model.encode(paragraphs, normalize_embeddings=True)
        vectors = np.array(embeddings)
    except Exception:
        return paragraphs

    merged: list[str] = [paragraphs[0]]
    for idx in range(1, len(paragraphs)):
        sim = float(np.dot(vectors[idx - 1], vectors[idx]))
        if sim < similarity_threshold:
            merged.append(paragraphs[idx])
        else:
            merged[-1] = merged[-1].rstrip() + "\n\n" + paragraphs[idx].lstrip()

    return merged


def langchain_paragraph_chunking(
    units: list[str],
    target_tokens: int,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    text = "\n\n".join(units).strip()
    if not text:
        return []

    if HAS_LANGCHAIN:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=token_to_char_budget(target_tokens),
            chunk_overlap=token_to_char_budget(overlap_tokens),
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=False,
        )
        pieces = [item.strip() for item in splitter.split_text(text) if item.strip()]
    else:
        pieces = [text]

    capped: list[str] = []
    for piece in pieces:
        if estimate_tokens(piece) <= max_tokens:
            capped.append(piece)
            continue

        # Fallback if character splitter still produced an oversized chunk.
        words = piece.split()
        current: list[str] = []
        current_tokens = 0
        for word in words:
            wt = estimate_tokens(word)
            if current and current_tokens + wt > max_tokens:
                capped.append(" ".join(current).strip())
                current = [word]
                current_tokens = wt
            else:
                current.append(word)
                current_tokens += wt
        if current:
            capped.append(" ".join(current).strip())

    return capped


def recursive_split_h1_h2_h3_then_paragraphs(
    source_text: str,
    article_title: str,
    source_name: str,
    target_tokens: int,
    max_tokens: int,
    overlap_tokens: int,
    semantic_chunking: bool,
) -> list[dict[str, Any]]:
    h1_blocks = split_by_heading_level(source_text, level=1, base_path=[article_title])
    if not h1_blocks:
        h1_blocks = [HeadingBlock(title=article_title, level=1, path=[article_title], body=source_text)]

    raw_chunks: list[dict[str, Any]] = []

    def split_level(block_text: str, path: list[str], next_level: int) -> list[dict[str, Any]]:
        token_count = estimate_tokens(block_text)
        if token_count <= max_tokens:
            return [
                {
                    "path": path,
                    "text": block_text.strip(),
                    "heading_level": min(next_level - 1, 6),
                }
            ]

        if next_level <= 3:
            sub_blocks = split_by_heading_level(block_text, level=next_level, base_path=path)
            if sub_blocks:
                out: list[dict[str, Any]] = []
                for sb in sub_blocks:
                    out.extend(split_level(sb.body, sb.path, next_level + 1))
                return out

        paras = split_to_paragraphs(block_text)
        if semantic_chunking:
            paras = semantic_group_paragraphs(paras)

        pieces = langchain_paragraph_chunking(
            units=paras,
            target_tokens=target_tokens,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )

        return [
            {
                "path": path,
                "text": p,
                "heading_level": min(next_level - 1, 6),
            }
            for p in pieces
            if p.strip()
        ]

    for h1 in h1_blocks:
        raw_chunks.extend(split_level(h1.body, h1.path, next_level=2))

    prepared: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_chunks, start=1):
        content = item["text"].strip()
        if not content:
            continue

        endpoints = find_endpoints(content)
        method_id = endpoints[0] if endpoints else "unknown-method"
        links = find_urls(content)
        section_path = " > ".join(item["path"])
        header = f"[ARTICLE] {article_title}\n[SECTION] {section_path}\n[METHOD] {method_id}"
        final_text = f"{header}\n\n{content}".strip()

        prepared.append(
            {
                "id": f"{Path(source_name).stem}-c{idx}",
                "source": source_name,
                "article_title": article_title,
                "section_path": section_path,
                "section_level": item["heading_level"],
                "method_id": method_id,
                "endpoints": endpoints,
                "source_links": links,
                "tokens_estimate": estimate_tokens(final_text),
                "text": final_text,
            }
        )

    return prepared


def try_build_llamaindex_parent_child(chunks: list[dict[str, Any]], max_tokens: int) -> list[dict[str, Any]]:
    if not HAS_LLAMAINDEX or not chunks:
        for ch in chunks:
            ch["hierarchy_level"] = "child"
            ch["parent_id"] = ch["method_id"]
        return chunks

    out: list[dict[str, Any]] = []

    by_source: dict[str, list[dict[str, Any]]] = {}
    for ch in chunks:
        by_source.setdefault(ch["source"], []).append(ch)

    max_chars = token_to_char_budget(max_tokens)
    child_chars = token_to_char_budget(max(220, int(max_tokens * 0.6)))

    for source, items in by_source.items():
        full_text = "\n\n".join(it["text"] for it in items)
        try:
            parser = HierarchicalNodeParser.from_defaults(chunk_sizes=[max_chars, child_chars])
            doc = Document(text=full_text, metadata={"source": source})
            nodes = parser.get_nodes_from_documents([doc])
            leaf_nodes = get_leaf_nodes(nodes)

            parent_id = f"{Path(source).stem}-parent-{uuid.uuid4().hex[:8]}"
            for i, leaf in enumerate(leaf_nodes, start=1):
                txt = (leaf.get_content() or "").strip()
                if not txt:
                    continue
                out.append(
                    {
                        "id": f"{Path(source).stem}-llama-child-{i}",
                        "source": source,
                        "article_title": items[0].get("article_title", Path(source).stem),
                        "section_path": items[0].get("section_path", ""),
                        "section_level": items[0].get("section_level", 1),
                        "method_id": items[0].get("method_id", "unknown-method"),
                        "endpoints": items[0].get("endpoints", []),
                        "source_links": items[0].get("source_links", []),
                        "tokens_estimate": estimate_tokens(txt),
                        "text": txt,
                        "hierarchy_level": "child",
                        "parent_id": parent_id,
                    }
                )
        except Exception:
            for ch in items:
                ch["hierarchy_level"] = "child"
                ch["parent_id"] = ch["method_id"]
                out.append(ch)

    return out


def apply_min_max_rules(chunks: list[dict[str, Any]], min_tokens: int, max_tokens: int) -> list[dict[str, Any]]:
    if not chunks:
        return chunks

    merged: list[dict[str, Any]] = [chunks[0].copy()]
    for ch in chunks[1:]:
        current = ch.copy()
        prev = merged[-1]

        can_merge = (
            current["tokens_estimate"] < min_tokens
            and prev["source"] == current["source"]
            and prev["method_id"] == current["method_id"]
            and prev["parent_id"] == current["parent_id"]
        )

        if can_merge:
            candidate = (prev["text"].rstrip() + "\n\n" + current["text"].lstrip()).strip()
            candidate_tokens = estimate_tokens(candidate)
            if candidate_tokens <= max_tokens:
                prev["text"] = candidate
                prev["tokens_estimate"] = candidate_tokens
                prev["endpoints"] = sorted(set(prev["endpoints"]) | set(current["endpoints"]))
                prev["source_links"] = sorted(
                    set(prev.get("source_links", [])) | set(current.get("source_links", []))
                )
                continue

        merged.append(current)

    # Regenerate sequential ids after merge.
    by_source_counter: dict[str, int] = {}
    for item in merged:
        source_stem = Path(item["source"]).stem
        by_source_counter[source_stem] = by_source_counter.get(source_stem, 0) + 1
        item["id"] = f"{source_stem}-c{by_source_counter[source_stem]}"

    return merged


def chunk_files(
    input_paths: list[Path],
    output_path: Path,
    target_tokens: int,
    min_tokens: int,
    max_tokens: int,
    overlap_ratio: float,
    semantic_chunking: bool,
) -> list[dict[str, Any]]:
    all_chunks: list[dict[str, Any]] = []
    overlap_tokens = max(1, int(target_tokens * overlap_ratio))

    for path in input_paths:
        raw = path.read_text(encoding="utf-8")
        cleaned = clean_mdx_with_unstructured(raw)
        article_title = extract_article_title(raw, path)

        chunks = recursive_split_h1_h2_h3_then_paragraphs(
            source_text=cleaned,
            article_title=article_title,
            source_name=path.name,
            target_tokens=target_tokens,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            semantic_chunking=semantic_chunking,
        )
        all_chunks.extend(chunks)

    all_chunks = try_build_llamaindex_parent_child(all_chunks, max_tokens=max_tokens)
    all_chunks = apply_min_max_rules(all_chunks, min_tokens=min_tokens, max_tokens=max_tokens)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for item in all_chunks:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return all_chunks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Chunk MDX API docs for RAG with recursive heading strategy: "
            "h1 -> h2 -> h3 -> paragraphs."
        )
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=["../overview.mdx", "../start.mdx", "../examples.mdx"],
        help="List of MDX files to chunk.",
    )
    parser.add_argument("--output", default="./out/rag_chunks.jsonl", help="Output JSONL path.")
    parser.add_argument("--target-tokens", type=int, default=650, help="Recommended: 500-800")
    parser.add_argument("--min-tokens", type=int, default=500)
    parser.add_argument("--max-tokens", type=int, default=800)
    parser.add_argument("--overlap", type=float, default=0.12, help="Recommended: 0.10-0.15")
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Enable semantic paragraph grouping using sentence embeddings when available.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.min_tokens > args.max_tokens:
        raise ValueError("min_tokens must be <= max_tokens")
    if not (0 <= args.overlap <= 0.5):
        raise ValueError("overlap must be in range [0, 0.5]")

    input_paths = [Path(p) for p in args.inputs]
    output_path = Path(args.output)

    chunks = chunk_files(
        input_paths=input_paths,
        output_path=output_path,
        target_tokens=args.target_tokens,
        min_tokens=args.min_tokens,
        max_tokens=args.max_tokens,
        overlap_ratio=args.overlap,
        semantic_chunking=args.semantic,
    )

    print(f"Chunks written: {len(chunks)}")
    print(f"Output: {output_path.resolve()}")
    print(f"LangChain enabled: {HAS_LANGCHAIN}")
    print(f"Unstructured enabled: {HAS_UNSTRUCTURED}")
    print(f"LlamaIndex enabled: {HAS_LLAMAINDEX}")
    print(f"Semantic embeddings enabled: {HAS_SENTENCE_TRANSFORMERS and args.semantic}")


if __name__ == "__main__":
    main()
