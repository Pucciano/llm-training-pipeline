import pandas as pd
import json
from datetime import datetime, timezone
from pathlib import Path

INPUT_FILE = "../data/excel/dataset.xlsx"
OUTPUT_FILE = "../data/dataset.jsonl"
APPEND = True  # False = überschreibt bestehende Datei

REQUIRED_COLUMNS = {"instruction", "output", "tags", "source", "license"}

def read_excel_dataset(path: str) -> list:
    """
    Liest die Excel-Datei ein und validiert den Inhalt.
    Gibt eine Liste von Dicts zurück.
    """
    df = pd.read_excel(path)

    # Spaltenprüfung
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"Excel-Datei fehlt folgende Spalten: {missing_cols}")

    # Fehlende Spalten auffüllen
    df["input"] = df.get("input", "")

    records = []
    for _, row in df.iterrows():
        if pd.isna(row["instruction"]) or pd.isna(row["output"]):
            continue  # Leere Einträge überspringen

        record = {
            "instruction": str(row["instruction"]).strip(),
            "input": str(row["input"]).strip(),
            "output": str(row["output"]).strip(),
            "meta": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "tags": [tag.strip() for tag in str(row["tags"]).split(",") if tag.strip()],
                "source": str(row["source"]).strip(),
                "license": str(row["license"]).strip()
            }
        }
        records.append(record)

    return records


def write_jsonl(records: list, path: str, append: bool = True):
    """
    Schreibt die Liste von Datensätzen in eine JSONL-Datei.
    """
    mode = "a" if append and Path(path).exists() else "w"
    with open(path, mode, encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    print(f"📥 Lese Excel-Datei: {INPUT_FILE}")
    try:
        records = read_excel_dataset(INPUT_FILE)
        print(f"✅ {len(records)} gültige Datensätze gefunden")
        write_jsonl(records, OUTPUT_FILE, APPEND)
        print(f"📤 Erfolgreich geschrieben nach: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ Fehler beim Import: {e}")


if __name__ == "__main__":
    main()
