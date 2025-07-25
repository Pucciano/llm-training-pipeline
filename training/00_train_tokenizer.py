#!/usr/bin/env python
"""
Baut einen BPE-Tokenizer.
Läuft auf der CPU.
"""
from pathlib import Path
from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, trainers
import argparse
import sys


def validate_args(args):
    if args.vocab_size <= 0:
        raise ValueError("vocab-size must be positive")

    corpus_dir = Path(args.corpus_dir)
    if not corpus_dir.exists():
        raise ValueError(f"Directory not found: {args.corpus_dir}")

    output_dir = Path(args.output).parent
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)


def get_text_files(directory):
    """Yield text files one at a time instead of loading all paths into memory."""
    for file_path in Path(directory).rglob('*.txt'):
        yield str(file_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", required=True,
                    help="Ordner mit *.txt-Dateien")
    ap.add_argument("--vocab-size", type=int, default=50000)
    ap.add_argument("--output", default="tokenizer_de.json")
    args = ap.parse_args()

    try:
        validate_args(args)

        # Count files first
        files = list(get_text_files(args.corpus_dir))
        if not files:
            raise ValueError(f"No .txt files found in {args.corpus_dir}")

        print(f"{len(files)} Textdateien gefunden ...")
        print(f"Verarbeite Dateien aus: {args.corpus_dir}")

        # Tokenizer setup
        tok = Tokenizer(models.BPE(unk_token="<unk>"))
        tok.normalizer = normalizers.Sequence([
            normalizers.NFKC(),
            normalizers.Lowercase()
        ])
        tok.pre_tokenizer = pre_tokenizers.ByteLevel()

        special_tokens = [
            # ─────────────────── Basis ───────────────────
            "<s>", "</s>", "<unk>", "<pad>",

            # ────────────── Juristische Strukturwörter ──────────────
            "<§>", "<Art.>", "<Abs.>", "<Satz>", "<Nr.>", "<Rn.>", "<ECLI:>",

            # ─────────────── Gerichte & Instanzen ───────────────
            "<AG>",  # Amtsgericht
            "<LG>",  # Landgericht
            "<OLG>",  # Oberlandesgericht
            "<BGH>",  # Bundesgerichtshof
            "<BVerfG>",  # Bundesverfassungsgericht
            "<BVerwG>",  # Bundesverwaltungsgericht
            "<BSG>",  # Bundessozialgericht
            "<BFH>",  # Bundesfinanzhof
            "<BAG>",  # Bundesarbeitsgericht
            "<FG>",  # Finanzgericht (allg.)
            "<EuGH>",  # Gerichtshof der Europäischen Union
            "<EuG>",  # Gericht der Europäischen Union

            # ───────────────── Gesetze & Abkürzungen ─────────────────
            "<GG>", "<BGB>", "<HGB>", "<StGB>", "<StPO>", "<ZPO>",
            "<VwGO>", "<VwVfG>", "<AO>", "<SGB>", "<IfSG>",
            "<UStG>", "<EStG>", "<GewO>", "<UrhG>", "<AktG>",
            "<InsO>", "<GKG>", "<GWB>",

            # Lateinische Rechtsbegriffe
            "<lex>", "<ratio>", "<subs>", "<obiter>",

            # ────────────── Programmier-Tokens (multi-lang) ──────────────
            # Python
            "<def>", "<class>", "<async>", "<await>", "<self>",
            # C/C++
            "<#include>", "<std::>", "<::>", "<->",
            # Rust
            "<fn>", "<mut>", "<println!>",
            # Go
            "<func>", "<package>", "<chan>", "<go>",
            # Kommentare
            "<//>", "<#>", "</*>", "<*/>",

            # ─────────────── Markdown-Kontroll-Tokens ───────────────
            "<MD_H1>", "<MD_H2>", "<MD_H3>", "<MD_H4>",
            "<MD_UL>", "<MD_OL>",
            "<MD_CB>",  # ``` ohne Sprachlabel
            "<MD_CODE_LANG_py>", "<MD_CODE_LANG_cpp>",
            "<MD_CODE_LANG_rs>", "<MD_CODE_LANG_go>",
            "<MD_TABLE>",
            "<MD_END>"
        ]

        trainer = trainers.BpeTrainer(
            vocab_size=args.vocab_size,
            special_tokens=special_tokens
        )

        # Train tokenizer
        tok.train(files, trainer)

        # Save result
        tok.save(args.output)
        print(f"Tokenizer gespeichert unter {args.output}")

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()