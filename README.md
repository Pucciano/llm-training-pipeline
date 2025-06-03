# LLM Training Pipeline

[![de](https://img.shields.io/badge/lang-de-blue.svg)](./README-DE.md) · [![en](https://img.shields.io/badge/lang-en-red.svg)](./README.md)

## 🧠 Project Vision

The goal of this project is to build a high-quality dataset for training a German-language large language model (LLM). While most open-source LLMs are trained multilingually, they often use English internally as a primary language. However, the DACH region (Germany, Austria, Switzerland) holds massive untapped linguistic and domain-specific potential.

This toolkit supports the full dataset lifecycle — from structured manual data entry to scalable bulk imports and automated metadata extraction.

---

## 🔍 Features

- ✅ Command-line interface for structured dataset entry (`instruction`, `input`, `output`, `tags`, `source`, `license`)
- ✅ Excel-based bulk import and conversion to Hugging Face-compatible `.jsonl`
- ✅ Markdown generation from PDF books (using `pymupdf4llm`)
- ✅ Metadata extraction from PDF files including MD5 hash, authorship, license, page count, etc.
- ✅ JSONL output suitable for fine-tuning instruction-tuned LLMs (`<thinking>`)
- ✅ Multilingual dataset support with metadata traceability
- 🛠️ CLI and Web UI for extending datasets interactively

---

## 📦 Dataset Format

The dataset is stored in `.jsonl` format (one record per line), designed for instruction-tuned generative models like **Gemma 3B**, **Qwen**, or **Mistral**.

### Example Entry:

```json
{
  "instruction": "Erkläre die Unterschiede zwischen TCP und UDP.",
  "input": "",
  "output": "TCP ist verbindungsorientiert ...",
  "tags": ["Netzwerktechnik", "Informatik"],
  "source": "OpenBook: Netzwerke leicht erklärt",
  "license": "CC-BY-SA 4.0",
  "created_at": "2025-06-03T22:26:29.342385+00:00"
}
````

---

## 🚀 Roadmap

1. 📝 Manual and bulk dataset generation
2. 🪄 PDF conversion to Markdown
3. 📤 Metadata export with hashing
4. 🔄 Validation and deduplication tooling
5. 📡 Hugging Face dataset upload
6. 🧪 Evaluation pipeline for new examples
7. 🔬 Model fine-tuning (LoRA, QLoRA, DPO)
8. 🌐 Web frontend for dataset curation

---

## 📂 Directory Structure

```
.
├── data/
│   ├── pdf/                # Source PDF books
│   ├── markdown/           # Extracted Markdown files
│   ├── dataset.jsonl       # Training data entries
│   └── pdf_metadata.jsonl  # Extracted PDF-metadata
├── scripts/
│   ├── create_dataset_entry.py
│   ├── excel_to_dataset.py
│   ├── pdf_to_markdown.py
│   └── generate_pdf_metadata.py
├── README.md
└── README-DE.md
```

---

## ✅ TODO

* [ ] Add Web UI for dataset entry and validation
* [ ] Add YAML → JSONL converter for other model families
* [ ] Build HF-compatible `datasets` Python loader
* [ ] Add duplicate detector via MD5/file path
* [ ] Add license + source inference helper for bulk PDF imports
* [ ] Integration tests and schema validation
* [ ] Prepare test/train/validation split logic

