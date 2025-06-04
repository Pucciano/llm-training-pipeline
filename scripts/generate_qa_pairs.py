#scripts/generate_qa_pairs.py
import json
import uuid
import httpx
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List

# Pfade
MARKDOWN_FOLDER = Path("../data/markdown")
METADATA_FILE = Path("../data/metadata/metadata.jsonl")
OUTPUT_FILE = Path("../data/generated/qa_pairs.jsonl")
LMSTUDIO_API = "http://localhost:1234/v1/chat/completions"

# Konfiguration
MAX_CHARS = 10240
HEADERS = {"Content-Type": "application/json"}
MODEL = "qwen/qwen3-4b"

def split_text(text: str, max_length: int = MAX_CHARS) -> List[str]:
    """
    Teilt den Text in Abschnitte von maximaler Länge unter Berücksichtigung von Satz- und Absatzgrenzen.
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
    Lädt die Metadaten aus der JSONL-Datei.
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
    Sendet einen Prompt an LM Studio (lokale API) und erwartet eine strukturierte JSON-Antwort.
    """
    payload = {
        "model": MODEL,
        "temperature": 0.8,
        "max_tokens": 32768,
        "stream": False,
        "messages": [
            { "role": "user", "content": prompt }
        ]
    }

    try:
        response = httpx.post(LMSTUDIO_API, headers=HEADERS, json=payload, timeout=120.0)
        response.raise_for_status()
        raw = response.json()

        content = raw["choices"][0]["message"]["content"]

        print("🧪 Rohantwort erhalten:")
        print(content[:300], "...")

        # Entferne evtl. <think>…</think> Wrapper
        if "<think>" in content:
            content = content.split("<think>")[-1]
        if "</think>" in content:
            content = content.split("</think>")[0]

        # JSON extrahieren
        start = content.find("{")
        end = content.rfind("}") + 1
        json_str = content[start:end]

        return json.loads(json_str)

    except Exception as e:
        print(f"❌ Fehler beim LLM-Aufruf: {e}")
        return {}


def generate_qa_pairs():
    """
    Hauptfunktion zum Generieren von QA-Paaren aus Markdown-Dateien.
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
