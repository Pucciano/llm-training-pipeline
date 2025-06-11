from pathlib import Path
from hashlib import md5
from datetime import datetime, timezone
import fitz  # PyMuPDF
import json

PDF_FOLDER = "../data/pdf"
OUTPUT_FILE = "../data/markdown/metadata.jsonl"

DEFAULT_SOURCE = "Unbekannt"
DEFAULT_LICENSE = "Unbekannt"

def compute_md5(path: Path) -> str:
    """
    Berechnet den MD5-Hash einer Datei.
    """
    hash_md5 = md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def extract_pdf_metadata(path: Path) -> dict:
    """
    Extrahiert Metadaten aus einer PDF-Datei.
    """
    doc = fitz.open(path)
    meta = doc.metadata

    return {
        "filename": path.name,
        "file_path": str(path),
        "file_hash_md5": compute_md5(path),
        "num_pages": doc.page_count,
        "title": meta.get("title") or "",
        "author": meta.get("author") or "",
        "subject": meta.get("subject") or "",
        "producer": meta.get("producer") or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": DEFAULT_SOURCE,
        "license": DEFAULT_LICENSE
    }


def main():
    input_dir = Path(PDF_FOLDER)
    output_path = Path(OUTPUT_FILE)
    pdf_files = list(input_dir.glob("*.pdf"))

    if not pdf_files:
        print("⚠️ Keine PDF-Dateien gefunden.")
        return

    print(f"📊 {len(pdf_files)} PDF-Dateien gefunden. Starte Metadaten-Extraktion...")

    with open(output_path, "w", encoding="utf-8") as out_f:
        for pdf_path in pdf_files:
            try:
                print(f"🔍 Analysiere: {pdf_path.name}")
                meta = extract_pdf_metadata(pdf_path)
                out_f.write(json.dumps(meta, ensure_ascii=False) + "\n")
                print(f"✅ Metadaten geschrieben: {pdf_path.name}")
            except Exception as e:
                print(f"❌ Fehler bei {pdf_path.name}: {e}")

    print(f"✅ Metadaten gespeichert in: {output_path}")


if __name__ == "__main__":
    main()
