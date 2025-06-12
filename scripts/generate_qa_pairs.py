import json
import uuid
import httpx
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List
from tiktoken import encoding_for_model

# Pfade und API-Endpunkt
MARKDOWN_FOLDER = Path("../data/markdown")
METADATA_FILE = Path("../data/markdown/metadata.jsonl")
OUTPUT_FILE = Path("../data/generated/qa_pairs.jsonl")
LMSTUDIO_API = "http://localhost:1234/v1/chat/completions"

# LLM-Konfiguration
MODEL = "qwen/qwen3-4b"
TEMPERATURE = 0.8
MAX_TOKENS = 32768  # Maximale Tokenanzahl der Ausgabe
WINDOW_TOKENS = 2048  # Sliding Window Größe
STRIDE_TOKENS = 1024  # Schrittweite für Sliding Window
HEADERS = {"Content-Type": "application/json"}

# Debug-Modus
DEBUG = True

# Initialisiere Tokenizer (tiktoken erfordert spezifisches Modell)
try:
    tokenizer = encoding_for_model("gpt-3.5-turbo")  # Kompatibler Tokenizer (auch für GGUF geeignet)
except Exception:
    tokenizer = encoding_for_model("cl100k_base")


def debug_print(message: str):
    if DEBUG:
        print(message)


def tokenize(text: str) -> List[int]:
    """Tokenisiert einen Text und gibt eine Liste von Token-IDs zurück."""
    return tokenizer.encode(text)


def detokenize(tokens: List[int]) -> str:
    """Detokenisiert eine Liste von Token-IDs zurück in einen String."""
    return tokenizer.decode(tokens)


def sliding_windows(text: str, window_size: int, stride: int) -> List[str]:
    """
    Erzeugt überlappende Textfenster basierend auf Tokenlängen (Sliding-Window-Prinzip).
    """
    token_ids = tokenize(text)
    windows = []
    i = 0
    while i < len(token_ids):
        chunk = token_ids[i:i + window_size]
        windows.append(detokenize(chunk))
        if i + window_size >= len(token_ids):
            break
        i += stride
    return windows


def load_metadata() -> dict:
    """
    Lädt die Metadaten aus einer JSONL-Datei und erstellt ein Mapping nach Dateinamen.
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
    Sendet einen Prompt an das lokal laufende Sprachmodell (LM Studio) und erwartet strukturierte JSON-Antwort.
    Zusätzlich wird der tatsächliche Tokenverbrauch überwacht.
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
        usage = raw.get("usage", {})

        if DEBUG:
            print(f"🧪 Tokenverbrauch (Prompt/Input): {usage.get('prompt_tokens')} Tokens")
            print(f"🧪 Tokenverbrauch (Output): {usage.get('completion_tokens')} Tokens")
            print(f"🧪 Gesamt: {usage.get('total_tokens')} Tokens")

        # Entferne evtl. <think> Wrapper
        if "<think>" in content:
            content = content.split("<think>")[-1]
        if "</think>" in content:
            content = content.split("</think>")[0]

        start = content.find("{")
        end = content.rfind("}") + 1
        json_str = content[start:end]

        return json.loads(json_str)

    except Exception as e:
        print(f"❌ Fehler beim LLM-Aufruf: {e}")
        return {}


def generate_qa_pairs():
    """
    Hauptfunktion zur QA-Generierung:
    - Liest Markdown-Dateien ein
    - Teilt sie in Sliding-Window-Segmente auf
    - Sendet diese an das LLM
    - Speichert strukturierte QA-Daten in JSONL
    """
    metadata_map = load_metadata()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    for md_path in MARKDOWN_FOLDER.glob("*.md"):
        print(f"📄 Verarbeite Datei: {md_path.name}")
        text = md_path.read_text(encoding="utf-8")
        segments = sliding_windows(text, window_size=WINDOW_TOKENS, stride=STRIDE_TOKENS)

        for i, segment in enumerate(segments):
            print(f"✂️  Sliding-Window Segment {i + 1} von {len(segments)}")

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
