import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


# =========================
# CONFIG
# =========================

INPUT_DIR = "start.mdx"         # сюда положите ваши .mdx файлы
OUTPUT_FILE = "./chunks.jsonl"

# Рекомендуемые параметры:
# 500–800 токенов, overlap 10–15%
CHUNK_SIZE_TOKENS = 700
CHUNK_OVERLAP_TOKENS = 80

# Если tokenizer недоступен, используем примерно chars
FALLBACK_CHUNK_SIZE_CHARS = 3500
FALLBACK_CHUNK_OVERLAP_CHARS = 400

SUPPORTED_EXTENSIONS = {".mdx", ".md", ".markdown"}


# =========================
# TOKEN COUNTING
# =========================

def get_token_counter():
    if not TIKTOKEN_AVAILABLE:
        return None

    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return lambda text: len(enc.encode(text))
    except Exception:
        return None


TOKEN_COUNTER = get_token_counter()


def length_function(text: str) -> int:
    if TOKEN_COUNTER:
        return TOKEN_COUNTER(text)
    return len(text)


# =========================
# CLEANING MDX / HTML / JSX
# =========================

def clean_mdx(text: str) -> str:
    """
    Очистка MDX/Markdown от import/export, JSX-компонентов, html-мусора.
    Наша цель — оставить полезный текст, заголовки, списки, код, таблицы.
    """
    # Нормализация переносов
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Удаляем import/export из MDX
    text = re.sub(r'^\s*import\s+.*?;\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*export\s+.*?;\s*$', '', text, flags=re.MULTILINE)

    # Удаляем однострочные JSX-компоненты вида:
    # <Component prop="..." />
    text = re.sub(r'<[A-Z][A-Za-z0-9_]*(\s+[^<>]*?)?\/>', '', text)

    # Удаляем блочные JSX-компоненты:
    # <Tabs>...</Tabs>
    # <Note>...</Note>
    text = re.sub(
        r'<([A-Z][A-Za-z0-9_]*)\b[^>]*>.*?</\1>',
        '',
        text,
        flags=re.DOTALL
    )

    # Удаляем html-комментарии
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # Удаляем некоторые html-теги, оставляя содержимое
    text = re.sub(r'</?(div|span|section|article|main|header|footer|br|hr)[^>]*>', '', text, flags=re.IGNORECASE)

    # Схлопываем слишком много пустых строк
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


# =========================
# HEADER PARSING
# =========================

HEADER_RE = re.compile(r'^(#{1,6})\s+(.*)$', re.MULTILINE)


def parse_markdown_sections(text: str) -> List[Dict[str, Any]]:
    """
    Парсим markdown по заголовкам.
    Возвращаем список секций с level, title, content.
    """
    matches = list(HEADER_RE.finditer(text))

    if not matches:
        return [{
            "level": 0,
            "title": None,
            "content": text.strip()
        }]

    sections = []

    # Текст до первого заголовка
    if matches[0].start() > 0:
        preface = text[:matches[0].start()].strip()
        if preface:
            sections.append({
                "level": 0,
                "title": None,
                "content": preface
            })

    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        sections.append({
            "level": level,
            "title": title,
            "content": content
        })

    return sections


# =========================
# HIERARCHICAL STRUCTURE
# =========================

def build_section_tree(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Строим дерево секций по уровням заголовков.
    """
    root = {"level": 0, "title": None, "content": "", "children": []}
    stack = [root]

    for sec in sections:
        node = {
            "level": sec["level"],
            "title": sec["title"],
            "content": sec["content"],
            "children": []
        }

        while stack and stack[-1]["level"] >= node["level"]:
            stack.pop()

        stack[-1]["children"].append(node)
        stack.append(node)

    return root["children"]


def node_to_text(node: Dict[str, Any]) -> str:
    """
    Собираем текст узла вместе с дочерними секциями.
    """
    parts = []

    if node["title"]:
        parts.append(f'{"#" * node["level"]} {node["title"]}')

    if node["content"]:
        parts.append(node["content"])

    for child in node.get("children", []):
        child_text = node_to_text(child)
        if child_text.strip():
            parts.append(child_text)

    return "\n\n".join(parts).strip()


# =========================
# SPLITTERS
# =========================

def get_final_splitter() -> RecursiveCharacterTextSplitter:
    if TOKEN_COUNTER:
        return RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE_TOKENS,
            chunk_overlap=CHUNK_OVERLAP_TOKENS,
            length_function=length_function,
            separators=[
                "\n\n",
                "\n",
                ". ",
                "! ",
                "? ",
                " ",
                ""
            ]
        )
    else:
        return RecursiveCharacterTextSplitter(
            chunk_size=FALLBACK_CHUNK_SIZE_CHARS,
            chunk_overlap=FALLBACK_CHUNK_OVERLAP_CHARS,
            length_function=length_function,
            separators=[
                "\n\n",
                "\n",
                ". ",
                "! ",
                "? ",
                " ",
                ""
            ]
        )


FINAL_SPLITTER = get_final_splitter()


# =========================
# RECURSIVE CHUNKING LOGIC
# =========================

def split_by_paragraphs(text: str) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paragraphs:
        return [text.strip()] if text.strip() else []
    return paragraphs


def recursive_chunk_node(
    node: Dict[str, Any],
    parent_headers: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Логика:
    - сначала пробуем сохранить целиком узел
    - если слишком большой, делим по дочерним заголовкам
    - если дочерних заголовков нет или всё ещё большой — по абзацам
    - затем финальный splitter
    """
    if parent_headers is None:
        parent_headers = []

    current_headers = parent_headers[:]
    if node["title"]:
        current_headers.append(node["title"])

    full_text = node_to_text(node).strip()
    if not full_text:
        return []

    max_size = CHUNK_SIZE_TOKENS if TOKEN_COUNTER else FALLBACK_CHUNK_SIZE_CHARS

    # Если узел уже влезает — отдаём как единый кусок
    if length_function(full_text) <= max_size:
        return [{
            "headers": current_headers,
            "text": full_text
        }]

    chunks = []

    # 1. Пытаемся делить по дочерним заголовкам
    children = node.get("children", [])

    if children:
        own_parts = []
        if node["title"]:
            own_parts.append(f'{"#" * node["level"]} {node["title"]}')
        if node["content"]:
            own_parts.append(node["content"].strip())

        own_text = "\n\n".join([p for p in own_parts if p]).strip()
        if own_text:
            if length_function(own_text) <= max_size:
                chunks.append({
                    "headers": current_headers,
                    "text": own_text
                })
            else:
                chunks.extend(split_large_text_by_paragraphs(own_text, current_headers))

        for child in children:
            chunks.extend(recursive_chunk_node(child, current_headers))

        return chunks

    # 2. Если нет дочерних секций — делим по абзацам
    chunks.extend(split_large_text_by_paragraphs(full_text, current_headers))
    return chunks


def split_large_text_by_paragraphs(text: str, headers: List[str]) -> List[Dict[str, Any]]:
    max_size = CHUNK_SIZE_TOKENS if TOKEN_COUNTER else FALLBACK_CHUNK_SIZE_CHARS
    paragraphs = split_by_paragraph