import re
from pathlib import Path
from striprtf.striprtf import rtf_to_text


# 📁 Eingabe- und Ausgabeverzeichnisse
RTF_FOLDER = Path("../data/rtf")
MARKDOWN_FOLDER = Path("../data/markdown")
MARKDOWN_FOLDER.mkdir(parents=True, exist_ok=True)


def clean_text(text: str,
               remove_non_printable: bool = True,
               apply_regex_filters: bool = True,
               remove_footer: bool = True,
               convert_italic_to_quote: bool = True) -> str:
    """
    Bereinigt den extrahierten Text durch verschiedene konfigurierbare Filter.
    """

    if remove_non_printable:
        text = ''.join(c for c in text if c.isprintable() or c in '\r\n\t')

    if apply_regex_filters:
        # Bullet Point-Korrekturen
        text = re.sub(r"^[•]\t\s*\r?\n", "* ", text, flags=re.MULTILINE)
        text = re.sub(r"•\r?\n", "* ", text)

        # Aufzählungszeichenbereinigung
        text = re.sub(r"(?<=^\d\d\))\s*\r?\n\s*\r?\n", " ", text, flags=re.MULTILINE)
        text = re.sub(r"(?<=^[\d\*]\))\s*\r?\n\s*\r?\n", " ", text, flags=re.MULTILINE)
        text = text.replace("¬", " ")

        # In korrekter Reihenfolge:
        text = re.sub(r"(?<=^\d{3}\))\r?\n", " ", text, flags=re.MULTILINE)
        text = re.sub(r"(?<=^\d{2}\))\r?\n", " ", text, flags=re.MULTILINE)
        text = re.sub(r"(?<=^[\d\*]\))\r?\n", " ", text, flags=re.MULTILINE)

    if remove_footer:
        text = re.sub(r"(Seite\s+\d+\s+von\s+\d+)", "", text, flags=re.IGNORECASE)

    if convert_italic_to_quote:
        # Option: Simuliere einfache Kursiv-Umwandlung durch Erkennung von typischen *kursiv* Mustern
        text = re.sub(r"(?<!\*)\*([^\*]+)\*(?!\*)", r"> \1", text)

    return text.strip()


def convert_rtf_to_markdown(input_path: Path, output_path: Path):
    """
    Konvertiert ein RTF-Dokument zu Markdown und speichert das Ergebnis.
    """
    with open(input_path, "r", encoding="utf-8") as file:
        rtf_content = file.read()

    plain_text = rtf_to_text(rtf_content)
    cleaned_text = clean_text(plain_text)

    with open(output_path, "w", encoding="utf-8") as md_file:
        md_file.write(cleaned_text)

    print(f"✅ Konvertiert: {input_path.name} → {output_path.name}")


def batch_convert_all_rtf_files():
    """
    Durchsucht den RTF-Ordner und konvertiert alle Dateien in das Markdown-Format.
    """
    for rtf_file in RTF_FOLDER.glob("*.rtf"):
        md_filename = rtf_file.stem + ".md"
        md_path = MARKDOWN_FOLDER / md_filename
        convert_rtf_to_markdown(rtf_file, md_path)


if __name__ == "__main__":
    batch_convert_all_rtf_files()
