#!/usr/bin/env python3
"""
epub_to_markdown.py

Konvertiert eine EPUB-Datei in ein Markdown-Textformat.

Benötigte Pakete:
    pip install ebooklib beautifulsoup4 markdownify
"""

from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub
from markdownify import markdownify as md

# ➡️  Ordnerpfade anpassen, falls nötig
EPUB_FOLDER = "../data/epub"
OUTPUT_FOLDER = "../data/markdown"


def convert_epub_to_markdown(epub_path: Path) -> str:
    """
    Konvertiert eine EPUB‑Datei in Markdown‑Text.

    Args:
        epub_path (Path): Pfad zur EPUB‑Datei.

    Returns:
        str: Extrahierter Inhalt im Markdown‑Format.
    """
    book = epub.read_epub(str(epub_path))
    markdown_parts = []

    for item in book.get_items():
        # Dokument‑HTML extrahieren
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), "html.parser")
            html_as_markdown = md(str(soup), heading_style="ATX")
            markdown_parts.append(html_as_markdown.strip())

    # Kapitel sauber trennen
    return "\n\n---\n\n".join(markdown_parts)


def clean_markdown(
        markdown_text: str,
        fix_spacing: bool = True,
        standardize_headers: bool = True,
        fix_lists: bool = True,
        remove_multiple_blanks: bool = True,
        extract_text: bool = False,
        remove_non_printable: bool = True,
) -> str:
    """
    Bereinigt Markdown‑Text mithilfe verschiedener Strategien.

    Parameter siehe PDF‑Skript.
    """
    import re
    import unicodedata

    def _remove_non_printable(s: str) -> str:
        return "".join(
            c for c in s if unicodedata.category(c)[0] != "C" or c in ("\n", "\t")
        )

    def _fix_header(line: str) -> str:
        match = re.match(r"^(#+)(.*)$", line.lstrip())
        if match:
            hashes, content = match.groups()
            return f"{hashes} {content.lstrip()}"
        return line

    def _fix_list_item(line: str) -> str:
        indent = len(line) - len(line.lstrip())
        content = line.lstrip()

        match = re.match(r"^(\d+\.)\s*(.*)", content)  # nummerierte Liste
        if match:
            number, item = match.groups()
            return " " * indent + f"{number} {item.strip()}"

        match = re.match(r"^([-*])\s*(.*)", content)  # Bullet‑Liste
        if match:
            bullet, item = match.groups()
            return " " * indent + f"{bullet} {item.strip()}"

        return line

    def _strip_markdown(text: str) -> str:
        # Sehr einfache Markdown‑Entfernung
        text = re.sub(r"(!?\[.*?\]\(.*?\))", "", text)
        text = re.sub(r"`{1,3}(.*?)`{1,3}", r"\1", text)
        text = re.sub(r"[*_]{1,3}(.*?)?[*_]{1,3}", r"\1", text)
        text = re.sub(r"#+ ", "", text)
        return text.strip()

    if remove_non_printable:
        markdown_text = _remove_non_printable(markdown_text)

    lines = markdown_text.splitlines()
    cleaned_lines = []
    prev_line = ""
    in_list = False
    i = 0

    while i < len(lines):
        line = lines[i]

        if fix_spacing:
            line = line.rstrip()

        if standardize_headers and line.lstrip().startswith("#"):
            line = _fix_header(line)

        is_list_item = False
        if fix_lists and (
                line.lstrip().startswith(("- ", "* ", "-", "*"))
                or re.match(r"^\s*\d+\.", line)
        ):
            line = _fix_list_item(line)
            is_list_item = True

        if remove_multiple_blanks:
            if line.strip() == "" and prev_line.strip() == "":
                i += 1
                continue

        if i > 0 and (
                line.lstrip().startswith(("#", "-", "*")) or re.match(r"^\s*\d+\.", line)
        ):
            if cleaned_lines and cleaned_lines[-1].strip() != "":
                if not (in_list and is_list_item):
                    cleaned_lines.append("")

        cleaned_lines.append(line)
        prev_line = line
        in_list = is_list_item
        i += 1

    # trailing blanks
    while cleaned_lines and cleaned_lines[-1].strip() == "":
        cleaned_lines.pop()
    cleaned_lines.append("")

    final_text = "\n".join(cleaned_lines)

    if extract_text:
        return "\n".join(
            _strip_markdown(line) for line in final_text.splitlines() if line.strip()
        )

    return final_text


def save_markdown(markdown_text: str, output_path: Path):
    """
    Speichert Markdown‑Text als Datei.

    Args:
        markdown_text (str): Inhalt.
        output_path (Path): Zielpfad.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)


def process_all_epubs(input_dir: Path, output_dir: Path):
    """
    Durchläuft alle EPUB‑Dateien im Eingabeordner und konvertiert sie.

    Args:
        input_dir (Path): Verzeichnis mit EPUBs.
        output_dir (Path): Zielverzeichnis für Markdown.
    """
    if not input_dir.exists():
        print(f"❌ Eingabeordner nicht gefunden: {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    epub_files = list(input_dir.glob("*.epub"))

    if not epub_files:
        print("⚠️  Keine EPUB‑Dateien gefunden.")
        return

    print(f"📚 {len(epub_files)} EPUB‑Datei(en) werden verarbeitet...")

    for epub_file in epub_files:
        try:
            print(f"🔄 Verarbeite: {epub_file.name}")
            markdown = convert_epub_to_markdown(epub_file)
            markdown = clean_markdown(markdown)
            output_file = output_dir / (epub_file.stem + ".md")
            save_markdown(markdown, output_file)
            print(f"✅ Gespeichert: {output_file.name}")
        except Exception as e:
            print(f"❌ Fehler bei {epub_file.name}: {e}")


def main():
    """
    Einstiegspunkt für die Massenkonvertierung.
    """
    input_dir = Path(EPUB_FOLDER)
    output_dir = Path(OUTPUT_FOLDER)

    print("🚀 Starte EPUB → Markdown Konvertierung")
    process_all_epubs(input_dir, output_dir)
    print("🏁 Konvertierung abgeschlossen.")


if __name__ == "__main__":
    main()
