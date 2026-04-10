#!/usr/bin/env python3
"""
Простой скрипт для чанкинга текста из .doc файлов
Параметры:
- Размер чанка: 800 символов
- Перекрытие: 120 символов (15%)
- Выход: текстовый файл
"""

import re
from pathlib import Path
from typing import List

try:
    from docx import Document
    DOC_AVAILABLE = True
except ImportError:
    DOC_AVAILABLE = False
    print("⚠️  python-docx не установлен. Установите: pip install python-docx")


# =========================
# CONFIG
# =========================

CHUNK_SIZE = 800        # Размер чанка в символах
CHUNK_OVERLAP = 120     # Перекрытие (15% от 800)
INPUT_FILE = r"c:\Users\ar.kartavtsev\Desktop\Chunking\Test.doc"
OUTPUT_FILE = r"c:\Users\ar.kartavtsev\Desktop\Chunking\chunks.txt"


# =========================
# FUNCTIONS
# =========================

def extract_text_from_doc(file_path: str) -> str:
    """Извлекает текст из .doc файла"""
    if not DOC_AVAILABLE:
        raise ImportError("python-docx не установлен")
    
    doc = Document(file_path)
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    return text


def clean_text(text: str) -> str:
    """Очистка текста от лишних символов и нормализация"""
    # Нормализация переносов строк
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Удаляем множественные пробелы
    text = re.sub(r" +", " ", text)
    
    # Удаляем множественные пустые строки
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text.strip()


def create_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Разбивает текст на чанки с перекрытием
    
    Args:
        text: исходный текст
        chunk_size: размер чанка в символах
        overlap: размер перекрытия между чанками
    
    Returns:
        Список чанков
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        
        # Если это последний чанк, выходим
        if end == len(text):
            break
        
        # Переходим к следующему чанку с перекрытием
        start = end - overlap
    
    return chunks


def save_chunks_to_file(chunks: List[str], output_file: str) -> None:
    """Сохраняет чанки в текстовый файл с номерами"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Всего чанков: {len(chunks)}\n")
        f.write(f"Размер чанка: {CHUNK_SIZE} символов\n")
        f.write(f"Перекрытие: {CHUNK_OVERLAP} символов\n")
        f.write("=" * 80 + "\n\n")
        
        for i, chunk in enumerate(chunks, 1):
            f.write(f"--- CHUNK {i} ({len(chunk)} символов) ---\n")
            f.write(chunk)
            f.write("\n\n")
    
    print(f"✅ Сохранено в {output_file}")
    print(f"📊 Всего чанков: {len(chunks)}")


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    # Проверяем наличие входного файла
    if not Path(INPUT_FILE).exists():
        print(f"❌ Файл {INPUT_FILE} не найден!")
        exit(1)
    
    print(f"📖 Читаю файл: {INPUT_FILE}")
    text = extract_text_from_doc(INPUT_FILE)
    print(f"✓ Извлечено {len(text)} символов")
    
    print("🧹 Очищаю текст...")
    text = clean_text(text)
    print(f"✓ После очистки: {len(text)} символов")
    
    print(f"✂️  Разбиваю на чанки (размер: {CHUNK_SIZE}, перекрытие: {CHUNK_OVERLAP})...")
    chunks = create_chunks(text, CHUNK_SIZE, CHUNK_OVERLAP)
    
    print(f"💾 Сохраняю результат...")
    save_chunks_to_file(chunks, OUTPUT_FILE)
