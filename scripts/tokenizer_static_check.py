#!/usr/bin/env python3
"""
Static sanity-check & quick stats für einen Hugging-Face-Tokenizer.

➟  Änderungen:
    •  Try/Except-Blöcke beim Laden von Tokenizer und specials.txt
    •  Bei Fehlern:   - Klarer Hinweis  (✗)
                     - Anzeige aller CLI-Parameter & Pfade
                     - Exit-Code 2   (statt rohem Traceback)
"""

import argparse
import pathlib
import sys
from collections import Counter

from tokenizers import Tokenizer


# ───────────────────────── Hilfsfunktionen ──────────────────────────
def banner(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def load_specials(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except Exception as e:
        banner("✗ FEHLER beim Laden von specials.txt")
        print(f"Pfad        : {path}")
        print(f"Exception   : {type(e).__name__}: {e}")
        sys.exit(2)


def load_tokenizer(path: str) -> Tokenizer:
    try:
        return Tokenizer.from_file(path)
    except Exception as e:
        banner("✗ FEHLER beim Laden der tokenizer.json")
        print(f"Pfad        : {path}")
        print(f"Exception   : {type(e).__name__}: {e}")
        sys.exit(2)


# ─────────────────────────── Checks ────────────────────────────────
def vocab_integrity(tok: Tokenizer) -> bool:
    vocab = tok.get_vocab()
    duplicates = [k for k, v in Counter(vocab.values()).items() if v > 1]
    if duplicates:
        print("✗ duplicate token-IDs gefunden:", duplicates[:10])
        return False
    print(f"✓ vocab_integrity – {len(vocab):,} Einträge, keine Duplikate")
    return True


def special_token_atomic(tok: Tokenizer, specials: list[str]) -> bool:
    broken = [sp for sp in specials if len(tok.encode(sp).ids) != 1]
    if broken:
        print("✗ Non-atomic special tokens:")
        for sp in broken:
            print("   •", sp)
        return False
    print("✓ special_token_atomic – alle Spezial-Tokens atomar")
    return True


def corpus_stats(tok: Tokenizer, corpus_path: str,
                 low_thr: float, high_thr: float) -> bool:
    banner("CORPUS STATS")
    p = pathlib.Path(corpus_path)
    paths = [p] if p.is_file() else list(p.rglob("*.txt"))[:1000]
    if not paths:
        print("Keine *.txt-Dateien in:", corpus_path)
        return True

    total_chars = total_tokens = 0
    special_hits: Counter[str] = Counter()

    for fp in paths:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        enc = tok.encode(text)
        total_chars  += len(text)
        total_tokens += len(enc.ids)
        special_hits.update(tok.id_to_token(tid) for tid in enc.ids
                            if tok.id_to_token(tid).startswith("<"))

        clean = lambda s: s.lstrip("Ġ▁Ċ")  # Marker entfernen
        special_hits.update(
            clean(tok.id_to_token(tid))
            for tid in enc.ids
            if clean(tok.id_to_token(tid)).startswith("<")
        )

    # Deutsches Tausender-Format (Punkt)
    fmt = lambda n: f"{n:,}".replace(",", ".")

    ratio = total_tokens / total_chars

    print(f"Analysierte Dateien : {len(paths)}")
    print(f"Zeichen insgesamt   : {fmt(total_chars)}")
    print(f"Tokens insgesamt    : {fmt(total_tokens)}")
    print(f"Tokens/Char-Ratio   : {ratio:.3f}  "
          f"(Schwellwert {low_thr:.2f}–{high_thr:.2f})\n")

    print("Top-20 Spezial-Token-Hits:")
    if special_hits:
        for tok_str, cnt in special_hits.most_common(20):
            print(f"  {tok_str:15s} {fmt(cnt):>10}")
    else:
        print("  (keine Treffer im Korpus)")

    if not (low_thr <= ratio <= high_thr):
        print(f"\n✗  Ratio außerhalb des Zielbereichs!")
        return False

    print("✓  Ratio im Zielbereich")
    return True


# ───────────────────────────── CLI ────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--specials",  required=True)
    ap.add_argument("--corpus")
    ap.add_argument("--ratio-min", type=float, default=0.20,
                    help="untere Schranke für Tokens/Char (default 0.20)")
    ap.add_argument("--ratio-max", type=float, default=0.35,
                    help="obere Schranke für Tokens/Char (default 0.35)")
    args = ap.parse_args()

    banner("TOKENIZER STATIC CHECK – Parameter")
    for k, v in vars(args).items():
        print(f"{k:10s}: {v}")
    banner("LAUFENDE CHECKS")

    tok       = load_tokenizer(args.tokenizer)
    specials  = load_specials(args.specials)

    ok = True
    ok &= vocab_integrity(tok)
    ok &= special_token_atomic(tok, specials)

    if args.corpus:
        ok &= corpus_stats(tok, args.corpus, args.ratio_min, args.ratio_max)

    # Exit-Code-Konvention:
    # 0 = alles ok
    # 1 = atomar/vocab-Fehler
    # 2 = File-I/O-Fehler (bereits vorher exit)
    # 3 = Ratio außerhalb Schwelle
    if not ok:
        sys.exit(3 if args.corpus else 1)


if __name__ == "__main__":
    main()