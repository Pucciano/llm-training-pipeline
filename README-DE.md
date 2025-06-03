# Toolkit zur Erstellung eines LLM-Datensatzes

[![de](https://img.shields.io/badge/lang-de-blue.svg)](./README-DE.md) · [![en](https://img.shields.io/badge/lang-en-red.svg)](./README.md)

## 🧠 Projektvision

Ziel dieses Projekts ist es, ein qualitativ hochwertigen Datensatz zur Feinabstimmung eines **deutschsprachigen Sprachmodells** zu entwickeln. Viele Open-Source-Modelle sind zwar mehrsprachig trainiert, nutzen intern aber meist Englisch. Der deutschsprachige Raum (DACH) bietet enormes Potenzial — sowohl sprachlich als auch thematisch.

Dieses Toolkit begleitet den gesamten Lebenszyklus der Datensatzerstellung: von der manuellen Eingabe über den Massenimport bis zur automatisierten Extraktion von Metadaten.

---

## 🔍 Funktionsumfang

- ✅ Kommandozeilentool zur strukturierten Eingabe von `instruction`, `input`, `output`, `tags`, `source`, `license`
- ✅ Excel-basierter Bulk-Import und Konvertierung in HuggingFace-kompatibles `.jsonl`-Format
- ✅ Umwandlung von PDF-Dokumenten in Markdown (`pymupdf4llm`)
- ✅ Extraktion von PDF-Metadaten inkl. MD5-Hash, Autor, Lizenz, Seitenanzahl usw.
- ✅ JSONL-Datensätze für Befehlsabgestimmte Sprachmodelle (`<thinking>`)
- ✅ Mehrsprachige Unterstützung mit vollständiger Rückverfolgbarkeit der Quellen
- 🛠️ Web-UI zur komfortablen Erweiterung und Validierung

---

## 📦 Datensatzformat

Der Datensatz wird im `.jsonl`-Format gespeichert (eine Zeile pro Eintrag). Es eignet sich besonders für instruction-tuned generative Modelle wie **Gemma 3B**, **Qwen**, **Mistral** u. a.

### Beispiel-Datensatz:

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

1. 📝 Strukturierte Dateneingabe & Bulk-Import
2. 🪄 Markdown-Erzeugung aus PDF-Quellen
3. 📤 Metadatenexport mit Hash-Überprüfung
4. 🔄 Validierung und Duplikaterkennung
5. 📡 Upload des Datensets als HuggingFace-Dataset
6. 🧪 Validierung und Erweiterung mit Testbeispielen
7. 🔬 LLM-Training mit LoRA/QLoRA/DPO
8. 🌐 Webinterface für die manuelle Datenpflege

---

## 📂 Projektstruktur

```
.
├── data/
│   ├── pdf/                # Quell-PDFs
│   ├── markdown/           # Generierte Markdown-Dateien
│   ├── dataset.jsonl       # Trainingsdaten im JSONL-Format
│   └── pdf_metadata.jsonl  # Extrahierte PDF-Metadaten
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

* [ ] Web-Interface zur Dateneingabe und Validierung
* [ ] YAML-zu-JSONL-Konvertierung für andere LLM-Formate
* [ ] HuggingFace `datasets`-kompatibler Loader
* [ ] Duplikatprüfung anhand von MD5/Filepath
* [ ] Quellen- und Lizenz-Helfer für Bulk-Importe
* [ ] Validierung und Testschema für Datensätze
* [ ] Automatische Aufteilung in train/valid/test