#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import argparse
from pathlib import Path
from lxml import etree

def extract_text(element):
    """Gibt den reinen Text eines Elements zurück."""
    parts = [t.strip() for t in element.itertext()]
    return " ".join(p for p in parts if p)

def clean_to_one_line(text):
    """Reduziert alle Whitespace (inkl. Zeilenumbrüche) auf einfache Leerzeichen."""
    return re.sub(r"\s+", " ", text).strip()

def process_file(xml_file: Path, out_dir: Path):
    """Parst eine einzelne XML-Datei und schreibt die Ausgabe nach <amtabk>.txt im out_dir."""
    parser = etree.XMLParser(load_dtd=True, no_network=True, recover=True)
    tree = etree.parse(str(xml_file), parser)
    root = tree.getroot()

    # Juristische Abkürzung als Basis für den Dateinamen
    amtabk = root.findtext('.//norm/metadaten/amtabk', default='').strip()
    if not amtabk:
        print(f"Warnung: Kein <amtabk> in {xml_file}, übersprungen.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{amtabk}.txt"

    with open(out_path, 'w', encoding='utf-8') as out_f:
        for norm in root.findall('.//norm'):
            enbez_el = norm.find('.//metadaten/enbez')
            enbez = enbez_el.text.strip() if enbez_el is not None else ""
            # Inhaltsverzeichnis überspringen
            if not enbez or enbez.lower() == "inhaltsübersicht":
                continue

            titel_el = norm.find('.//metadaten/titel')
            titel = extract_text(titel_el) if titel_el is not None else ""

            content_el = norm.find('.//textdaten/text/Content')
            text_body = extract_text(content_el) if content_el is not None else ""
            fuss_el = norm.find('.//textdaten/fussnoten')
            fuss_txt = extract_text(fuss_el) if fuss_el is not None else ""

            # Leere Norm überspringen
            if not text_body and not fuss_txt:
                continue

            # Kopfzeile: §-Nummer, amtabk, Titel
            header = f"{enbez} {amtabk}: {titel}"
            out_f.write(header + "\n")

            # Body in eine Zeile packen; Fußnoten anhängen
            body = text_body
            if fuss_txt:
                body += " Fußnoten: " + fuss_txt
            out_f.write(clean_to_one_line(body) + "\n\n")

    print(f"Erzeugt: {out_path}")

def main():
    parser = argparse.ArgumentParser(description="Parst Bundesgesetze-XML und wandelt sie in Textdateien um.")
    parser.add_argument('--input', '-i', required=True, help="Eingabe-Verzeichnis mit XML-Dateien")
    parser.add_argument('--output', '-o', required=True, help="Ausgabe-Verzeichnis für TXT-Dateien")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.is_dir():
        print(f"Fehler: Eingabe-Pfad '{input_dir}' ist kein Verzeichnis.")
        sys.exit(1)

    for xml_path in input_dir.rglob('*.xml'):
        process_file(xml_path, output_dir)

if __name__ == "__main__":
    main()
