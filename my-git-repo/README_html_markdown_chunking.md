# HTML → Markdown → Chunks: пайплайн подготовки данных для RAG

Два скрипта работают в связке и реализуют двухэтапный пайплайн:

```
HTML-файлы  ──(1)──►  Markdown-файлы  ──(2)──►  Чанки (.txt + .jsonl)
```

---

## Скрипт 1: `html_to_markdown_trafilatura.py`

### Что делает

Читает локальные HTML-файлы и конвертирует каждый в Markdown (.md), сохраняя
структуру папок.

### Как работает

1. Рекурсивно обходит входную директорию и находит все `.html` / `.htm` файлы.
2. Для каждого файла вызывает `trafilatura.extract()` с параметрами:
   - `output_format="markdown"` — вывод в формате Markdown
   - `include_formatting=True` — сохраняет заголовки, списки, курсив и жирный шрифт
   - `include_links=True` — сохраняет ссылки
   - `favor_precision=True` — приоритет точности над полнотой: отсекает рекламу, навигацию, футеры
3. Если из файла не извлечён контент (пустая страница, одна навигация и т. д.)
   — файл пропускается с сообщением `SKIP`.
4. Сохраняет результат в `.md`-файл с тем же именем, сохраняя структуру
   подпапок внутри output-директории.
5. В конце выводит сводку: сколько файлов конвертировано / пропущено.

### Ключевые функции

| Функция | Назначение |
|---|---|
| `iter_html_files(root_dir)` | Рекурсивный обход HTML-файлов |
| `html_to_markdown(html_text)` | Конвертация через trafilatura.extract |
| `convert_directory(input_dir, output_dir)` | Основная логика обхода и записи |
| `main()` | Точка входа, разбор аргументов CLI |

### Зависимости

```
trafilatura
```

Установка:

```bash
python3.11 -m pip install trafilatura
```

### Запуск

```bash
# Дефолтные пути (html/ → html_markdown/)
python3.11 html_to_markdown_trafilatura.py

# Свои пути
python3.11 html_to_markdown_trafilatura.py \
  --input-dir "C:/Chunking/html" \
  --output-dir "C:/Chunking/html_markdown"
```

### Дефолтные пути

| Параметр | Значение |
|---|---|
| `--input-dir` | `C:\Users\ar.kartavtsev\Desktop\Chunking\html` |
| `--output-dir` | `C:\Users\ar.kartavtsev\Desktop\Chunking\html_markdown` |

---

## Скрипт 2: `chunk_markdown_files.py`

### Что делает

Читает Markdown-файлы, разбивает их на чанки по структуре заголовков,
применяет рекурсивный fallback для длинных секций и сохраняет результат
в двух форматах: `.txt` и `.jsonl`.

### Как работает

#### Шаг 1 — Подсчёт токенов

- Используется `tiktoken` с кодировкой `cl100k_base` (GPT-4 / GPT-3.5-turbo).
- Если `tiktoken` не установлен — автоматически включается fallback:
  `токены ≈ len(text) // 4`.

#### Шаг 2 — Разбиение по заголовкам

`MarkdownHeaderTextSplitter` делит текст по заголовкам `#`, `##`, `###`.  
Каждая получившаяся секция получает метаданные `h1`, `h2`, `h3`, которые
автоматически наследуются при дальнейшем разбиении.

```python
headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
sections = md_splitter.split_text(text)
```

#### Шаг 3 — Рекурсивный fallback для длинных секций

Если отдельная секция длиннее `max_tokens` (800), она дополнительно
разбивается через `RecursiveCharacterTextSplitter`.

Параметры сплиттера:

| Параметр | Значение |
|---|---|
| `chunk_size` | 800 токенов |
| `chunk_overlap` | 120 токенов (15 % от 800) |
| `length_function` | token_counter (tiktoken или fallback) |
| `separators` | `\n\n`, `\n`, `. `, `! `, `? `, `; `, `: `, ` `, `""` |
| `keep_separator` | True — разделитель остаётся в тексте |

Порядок разделителей гарантирует, что разрыв происходит сначала между
абзацами, затем между предложениями — и никогда не посередине слова.

```python
split_docs = rec_splitter.split_documents(sections)
# Метаданные h1/h2/h3 автоматически наследуются каждым чанком.
```

#### Шаг 4 — Постобработка: слияние коротких чанков

После разбиения некоторые чанки могут оказаться короче `min_tokens` (500).
Такие чанки сливаются с соседними, при условии:

- Соседний чанк принадлежит **той же секции** (одинаковые `h1`, `h2`, `h3`).
- Объединённый размер не превышает `max_tokens` (800).

Направление слияния: сначала вперёд (с правым соседом), при неудаче — назад
(с левым соседом).

#### Шаг 5 — Сохранение результата

Для каждого `.md` файла создаются два файла в output-директории:

**`.txt`** — читаемый человеком отчёт:
```
Source file: ...
Total chunks: N
...
Statistics: Min=X tokens, Max=Y tokens, Avg=Z tokens
================================================================================

--- CHUNK 1 (543 tokens / 2191 chars) ---
H1: Название раздела
H2: Подраздел
H3: ...

Текст чанка...
```

**`.jsonl`** — по одному JSON-объекту на строку (удобно для загрузки в RAG):
```json
{
  "chunk_index": 1,
  "source_file": "...",
  "h1": "Название раздела",
  "h2": "Подраздел",
  "h3": "",
  "tokens": 543,
  "chars": 2191,
  "text": "Текст чанка..."
}
```

### Ключевые функции

| Функция | Назначение |
|---|---|
| `get_token_counter()` | Инициализация tiktoken или fallback |
| `get_splitters(...)` | Создание MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter |
| `iter_markdown_files(root_dir)` | Обход .md-файлов (игнорирует папки *_files) |
| `merge_small_chunks(docs, ...)` | Постобработка: слияние коротких чанков |
| `save_txt(...)` | Запись читаемого .txt-отчёта |
| `save_jsonl(...)` | Запись .jsonl для загрузки в RAG |
| `process_markdown_file(...)` | Полный цикл обработки одного файла |
| `main()` | Точка входа, разбор аргументов CLI |

### Параметры чанкинга

| Параметр | Значение |
|---|---|
| `min_tokens` | 500 — минимальный размер чанка после слияния |
| `max_tokens` | 800 — максимальный размер чанка до overlap |
| `overlap_tokens` | 120 (15 % от 800) |

### Зависимости

```
langchain-text-splitters   # или langchain[text-splitters]
tiktoken                   # опционально, рекомендуется для точного счёта токенов
```

Установка:

```bash
python3.11 -m pip install langchain-text-splitters tiktoken
```

### Запуск

```bash
# Дефолтные пути (html_markdown/ → markdown_chunks/)
python3.11 chunk_markdown_files.py

# Свои пути
python3.11 chunk_markdown_files.py \
  --input-dir "C:/Chunking/html_markdown" \
  --output-dir "C:/Chunking/markdown_chunks"
```

### Дефолтные пути

| Параметр | Значение |
|---|---|
| `--input-dir` | `C:\Users\ar.kartavtsev\Desktop\Chunking\html_markdown` |
| `--output-dir` | `C:\Users\ar.kartavtsev\Desktop\Chunking\markdown_chunks` |

---

## Полный пайплайн

### 1. Установка зависимостей

```bash
python3.11 -m pip install trafilatura langchain-text-splitters tiktoken
```

### 2. Шаг 1: HTML → Markdown

```bash
python3.11 html_to_markdown_trafilatura.py
```

Результат: папка `html_markdown/` с `.md`-файлами.

### 3. Шаг 2: Markdown → Чанки

```bash
python3.11 chunk_markdown_files.py
```

Результат: папка `markdown_chunks/` с парами `*_chunks.txt` + `*_chunks.jsonl`.

---

## Структура файлов

```
Chunking/
├── html/                          # Входные HTML-файлы
│   └── *.html
├── html_markdown/                 # Результат шага 1
│   └── *.md
└── markdown_chunks/               # Результат шага 2
    ├── *_chunks.txt
    └── *_chunks.jsonl

my-git-repo/
├── html_to_markdown_trafilatura.py   # Шаг 1
└── chunk_markdown_files.py           # Шаг 2
```
