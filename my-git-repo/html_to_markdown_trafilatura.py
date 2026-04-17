#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path

import trafilatura


DEFAULT_INPUT_DIR = Path(r"C:\Users\ar.kartavtsev\Desktop\Chunking\my-git-repo\html")
DEFAULT_OUTPUT_DIR = Path(r"C:\Users\ar.kartavtsev\Desktop\Chunking\my-git-repo\html_markdown")


def iter_html_files(root_dir: Path):
    """Итерирует html/htm файлы рекурсивно."""
    for file_path in sorted(root_dir.rglob("*")):
        if file_path.is_file() and file_path.suffix.lower() in {".html", ".htm"}:
            yield file_path


def html_to_markdown(html_text: str) -> str | None:
    """Извлекает основной контент и возвращает markdown."""
    return trafilatura.extract(
        html_text,
        output_format="markdown",
        include_formatting=True,
        include_links=True,
        favor_precision=True,
    )


def convert_directory(input_dir: Path, output_dir: Path) -> tuple[int, int]:
    """Конвертирует HTML-файлы в Markdown и сохраняет структуру папок."""
    converted = 0
    skipped = 0

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    for html_file in iter_html_files(input_dir):
        rel_path = html_file.relative_to(input_dir)
        md_path = (output_dir / rel_path).with_suffix(".md")
        md_path.parent.mkdir(parents=True, exist_ok=True)

        html_text = html_file.read_text(encoding="utf-8", errors="ignore")
        markdown = html_to_markdown(html_text)

        if not markdown or not markdown.strip():
            skipped += 1
            print(f"SKIP: no extractable content -> {html_file}")
            continue

        md_path.write_text(markdown.strip() + "\n", encoding="utf-8")
        converted += 1
        print(f"OK: {html_file} -> {md_path}")

    return converted, skipped


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert local HTML files to Markdown with trafilatura"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory with HTML files (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for Markdown files (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    converted, skipped = convert_directory(args.input_dir, args.output_dir)
    print("-" * 80)
    print(f"Converted: {converted}")
    print(f"Skipped: {skipped}")
    print(f"Output dir: {args.output_dir}")


if __name__ == "__main__":
    main()
