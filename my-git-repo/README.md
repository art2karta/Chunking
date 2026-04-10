# MDX Chunking For RAG

This project chunks API documentation in MDX format into JSONL records suitable for retrieval-augmented generation (RAG).

## What This Chunker Does

1. Splits documents by MDX headings (strict section boundaries).
2. Detects API endpoints such as /routing/7.0.0/global and /public_transport/2.0.
3. Builds token-aware chunks with overlap, tuned for method-level retrieval.
4. Writes JSONL with metadata: source file, section path, section kind, endpoint list, token estimate, and text.

## Recommended Parameters

For API docs, defaults are aligned with your target setup:

1. Window size: around 650 tokens.
2. Min/max boundaries: 500/800 tokens.
3. Overlap: 12%.

This keeps nearby method description context while preserving semantic boundaries.

## Run

From the project folder:

```bash
python Main.py
```

Default inputs:

1. ../overview.mdx
2. ../start.mdx
3. ../examples.mdx

Default output:

1. ./out/rag_chunks.jsonl

## Custom Run Example

```bash
python Main.py --inputs ../overview.mdx ../start.mdx ../examples.mdx --output ./out/rag_chunks.jsonl --target-tokens 650 --min-tokens 500 --max-tokens 800 --overlap 0.12
```

## Output Format

Each line in JSONL is a chunk object:

```json
{
	"id": "start-s5-c2",
	"source": "start.mdx",
	"section_path": "Начало работы > Построение маршрута на автомобиле",
	"section_level": 2,
	"section_kind": "reference",
	"endpoints": ["/routing/7.0.0/global"],
	"tokens_estimate": 642,
	"text": "..."
}
```