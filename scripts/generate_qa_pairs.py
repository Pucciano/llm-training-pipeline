"""
QA-Paar-Generator für Markdown-Dokumente

Dieses Skript lädt alle Markdown-Dateien aus einem konfigurierten Verzeichnis,
teilt deren Inhalt in Segmente und sendet diese an ein lokales LLM über die
LM Studio API, um Frage-Antwort-Paare zu generieren. Die Ergebnisse werden
zusammen mit Metadaten in einer JSONL-Datei gespeichert.
"""

import json
import uuid
import httpx
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List

# Konfiguration: Verzeichnisse und Pfade
MARKDOWN_FOLDER = Path("../data/markdown")
METADATA_FILE = Path("../data/markdown/metadata.jsonl")
OUTPUT_FILE = Path("../data/generated/qa_pairs.jsonl")

# LM Studio API-Konfiguration
LMSTUDIO_API = "http://localhost:1234/v1/chat/completions"
HEADERS = {"Content-Type": "application/json"}
MODEL = "qwen/qwen3-4b"
TEMPERATURE = 0.8
MAX_TOKENS = 32768

# Maximale Segmentlänge in Zeichen
MAX_CHARS = 10240

# Debug-Modus zur Protokollierung von Zwischenschritten
DEBUG = False


def debug_print(message: str):
    """Gibt eine Debug-Nachricht aus, wenn der Debug-Modus aktiv ist."""
    if DEBUG:
        print(message)


def split_text(text: str, max_length: int = MAX_CHARS) -> List[str]:
    """
    Teilt den Text in Abschnitte auf, die die maximale Zeichenzahl nicht überschreiten.
    Bevorzugt wird an Zeilenumbrüchen getrennt, um logische Einheiten zu erhalten.

    :param text: Vollständiger Eingabetext
    :param max_length: Maximale Länge eines Segments in Zeichen
    :return: Liste segmentierter Textblöcke
    """
    segments, current = [], ""
    for line in text.splitlines():
        if len(current) + len(line) + 1 > max_length:
            if current.strip():
                segments.append(current.strip())
            current = ""
        current += line + "\n"
    if current.strip():
        segments.append(current.strip())
    return segments


def load_metadata() -> dict:
    """
    Lädt eine JSONL-Datei mit Metadaten zu den Markdown-Dateien.

    :return: Dictionary mit Dateinamen als Schlüssel und Metadaten als Wert
    """
    if not METADATA_FILE.exists():
        print("⚠️  Metadaten-Datei nicht gefunden!")
        return {}
    metadata = {}
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            metadata[data["filename"]] = data
    return metadata


def call_llm(prompt: str) -> dict:
    """
    Sendet einen Prompt an die LM Studio API und erwartet ein JSON-Format mit QA-Paaren.

    :param prompt: Der zu analysierende Text
    :return: Antwort des Modells als Dictionary
    """
    payload = {
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = httpx.post(LMSTUDIO_API, headers=HEADERS, json=payload, timeout=120.0)
        response.raise_for_status()
        raw = response.json()

        content = raw["choices"][0]["message"]["content"]

        debug_print("🧪 Rohantwort erhalten:\n" + content[:1000] + "\n…")

        # Entferne optionale <think>-Tags
        if "<think>" in content:
            content = content.split("<think>")[-1]
        if "</think>" in content:
            content = content.split("</think>")[0]

        # Extrahiere den JSON-Bereich
        start = content.find("{")
        end = content.rfind("}") + 1
        json_str = content[start:end]

        return json.loads(json_str)

    except Exception as e:
        print(f"❌ Fehler beim LLM-Aufruf: {e}")
        return {}


def generate_qa_pairs():
    """
    Durchläuft alle Markdown-Dateien im definierten Ordner, generiert QA-Paare,
    und speichert diese inklusive Metadaten in einer JSONL-Datei.
    """
    metadata_map = load_metadata()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    for md_path in MARKDOWN_FOLDER.glob("*.md"):
        print(f"📄 Verarbeite Datei: {md_path.name}")
        text = md_path.read_text(encoding="utf-8")
        segments = split_text(text)

        for i, segment in enumerate(segments):
            print(f"✂️  Segment {i + 1} von {len(segments)}")
            llm_response = call_llm(segment)

            if not llm_response.get("qa_pairs"):
                print("⚠️  Keine QA-Paare empfangen. Segment wird übersprungen.")
                continue

            try:
                for pair in llm_response["qa_pairs"]:
                    entry = {
                        "id": str(uuid.uuid4()),
                        "instruction": pair["instruction"],
                        "input": pair["input"],
                        "output": pair["output"],
                        "source_file": md_path.name,
                        "file_path": str(md_path.resolve()),
                        "file_hash_md5": hashlib.md5(md_path.read_bytes()).hexdigest(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "license": metadata_map.get(md_path.name, {}).get("license", "Unbekannt"),
                        "source": metadata_map.get(md_path.name, {}).get("source", "Unbekannt")
                    }
                    with open(OUTPUT_FILE, "a", encoding="utf-8") as out:
                        out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    print(f"✅ QA-Paar gespeichert: {entry['id']}")
            except Exception as e:
                print(f"❌ Fehler beim Parsen der Antwort: {e}")
                print(f"Antwort-Content: {llm_response}")


if __name__ == "__main__":
    generate_qa_pairs()
