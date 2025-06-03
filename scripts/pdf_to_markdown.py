from pathlib import Path
import pymupdf4llm

PDF_FOLDER = "../data/pdf"
OUTPUT_FOLDER = "../data/markdown"


def convert_pdf_to_markdown(pdf_path: Path) -> str:
    """
    Konvertiert eine PDF-Datei in ein Markdown-Textformat.

    Args:
        pdf_path (Path): Pfad zur PDF-Datei.

    Returns:
        str: Extrahierter Inhalt im Markdown-Format.
    """
    return pymupdf4llm.to_markdown(str(pdf_path))


def save_markdown(markdown_text: str, output_path: Path):
    """
    Speichert den Markdown-Text in einer .md-Datei.

    Args:
        markdown_text (str): Der zu speichernde Text.
        output_path (Path): Zielpfad der Markdown-Datei.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)


def process_all_pdfs(input_dir: Path, output_dir: Path):
    """
    Durchläuft alle PDF-Dateien im Eingabeordner und konvertiert sie in Markdown-Dateien.

    Args:
        input_dir (Path): Verzeichnis mit PDF-Dateien.
        output_dir (Path): Zielverzeichnis für Markdown-Dateien.
    """
    if not input_dir.exists():
        print(f"❌ Eingabeordner nicht gefunden: {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = list(input_dir.glob("*.pdf"))

    if not pdf_files:
        print("⚠️ Keine PDF-Dateien gefunden.")
        return

    print(f"📄 {len(pdf_files)} PDF-Datei(en) werden verarbeitet...")

    for pdf_file in pdf_files:
        try:
            print(f"🔄 Verarbeite: {pdf_file.name}")
            markdown = convert_pdf_to_markdown(pdf_file)
            output_file = output_dir / (pdf_file.stem + ".md")
            save_markdown(markdown, output_file)
            print(f"✅ Gespeichert: {output_file.name}")
        except Exception as e:
            print(f"❌ Fehler bei {pdf_file.name}: {e}")


def main():
    """
    Hauptfunktion zum Starten der Konvertierung.
    """
    input_dir = Path(PDF_FOLDER)
    output_dir = Path(OUTPUT_FOLDER)

    print("🚀 Starte PDF → Markdown Konvertierung")
    process_all_pdfs(input_dir, output_dir)
    print("✅ Konvertierung abgeschlossen.")


if __name__ == "__main__":
    main()
