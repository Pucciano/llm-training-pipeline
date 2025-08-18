#!/usr/bin/env python3
"""
epub_to_markdown.py

Konvertiert eine EPUB-Datei in ein Markdown-Textformat.

Benötigte Pakete:
    pip install ebooklib beautifulsoup4 markdownify
"""

from pathlib import Path
import re

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub
from markdownify import markdownify as md

# ➡️  Ordnerpfade anpassen, falls nötig
EPUB_FOLDER = "../data/epub/de"
OUTPUT_FOLDER = "../data/corpus/de"


XML_DECL_RE = re.compile(r'^\s*<\?xml[^>]*\?>\s*', flags=re.IGNORECASE)


def _preclean_soup(soup: BeautifulSoup) -> None:
    """DOM-Bereinigung vor Markdownify."""
    # 0) TOC-Container entfernen
    for tag in soup.select('nav[epub\\:type~="toc"], nav[role="doc-toc"], [role="doc-toc"]'):
        tag.decompose()

    # 1) Audio entfernen
    for tag in soup.find_all("audio"):
        tag.decompose()

    # 2) Seitenzahlen-Spans entfernen
    for tag in soup.select("span.c1.c3"):
        tag.decompose()

    # 3) Bilder entfernen
    for tag in soup.find_all("img"):
        tag.decompose()


def _fix_german_quotes(text: str) -> str:
    """
    Ersetzt französische Guillemets durch deutsche Anführungszeichen.
    »...« -> „...“
    """
    text = re.sub(r"»", "„", text)
    text = re.sub(r"«", "“", text)
    return text


def _extract_title_and_strip_h1(soup: BeautifulSoup) -> str:
    """
    Ermittelt die Dokumentüberschrift.
    Priorität: erstes <h1> (Textinhalt), sonst <title>.
    Entfernt das verwendete <h1> aus dem DOM, damit markdownify es nicht erneut rendert.
    """
    # 1) echtes H1
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
        h1.decompose()
        return title.strip()

    # 2) <title>
    if soup.title:
        return soup.title.get_text(strip=True)

    # 3) Fallback
    return ""


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
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # Rohinhalt laden und XML-Deklaration vor dem Parsen entfernen
            raw = item.get_content()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            raw = XML_DECL_RE.sub("", raw, count=1)

            soup = BeautifulSoup(raw, "html.parser")

            # Vorreinigung auf DOM-Ebene
            _preclean_soup(soup)

            # Titel ermitteln und H1 entfernen
            title = _extract_title_and_strip_h1(soup)

            # HTML -> Markdown
            body_md = md(str(soup), heading_style="ATX").strip()

            # Deutsche Anführungszeichen korrigieren
            body_md = _fix_german_quotes(body_md)

            # Überschrift setzen, unabhängig von H-Leveln in der Quelle
            if title:
                part = f"# {title}\n\n{body_md}".strip()
            else:
                part = body_md

            markdown_parts.append(part)

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
    """
    import re
    import unicodedata

    def _remove_non_printable(s: str) -> str:
        # explizite Problemzeichen rauswerfen
        s = s.replace("\f", "")  # Form Feed U+000C
        s = s.replace("\uFFFC", "")  # Object Replacement Character U+FFFC

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
        text = re.sub(r"(!?\[.*?\]\(.*?\))", "", text)
        text = re.sub(r"`{1,3}(.*?)`{1,3}", r"\1", text)
        text = re.sub(r"[*_]{1,3}(.*?)?[*_]{1,3}", r"\1", text)
        text = re.sub(r"#+ ", "", text)
        return text.strip()

    # Zusätzliche Sicherung: Guillemets -> deutsche Anführungszeichen
    markdown_text = _fix_german_quotes(markdown_text)

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

        if remove_multiple_blanks and line.strip() == "" and prev_line.strip() == "":
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
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)


def process_all_epubs(input_dir: Path, output_dir: Path):
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
    input_dir = Path(EPUB_FOLDER)
    output_dir = Path(OUTPUT_FOLDER)

    print("🚀 Starte EPUB → Markdown Konvertierung")
    process_all_epubs(input_dir, output_dir)
    print("🏁 Konvertierung abgeschlossen.")


if __name__ == "__main__":
    main()
