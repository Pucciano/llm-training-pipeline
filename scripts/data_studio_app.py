#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Harmony Data Studio (Gradio) – inspiriert vom Hugging Face Data Studio

Features
- Streaming/Index-basiertes Laden großer JSONL/JSONL.GZ (Byte-Offsets)
- Threaded Indexaufbau (mehrere CPU-Kerne)
- Filter: Reasoning, Suche (user/final/developer/analysis oder alle), Quelle, Längen, has_analysis
- Pagination + Vorschau umschaltbar (gekürzt/voll)
- Detailansicht + Editor (user / analysis / final) mit Zwischenspeicher und Export
- Gradio Queue-Kompatibilität (versch. Versionen) via enable_queue()

Benötigt:
  uv pip install gradio pandas pyarrow
"""

import os
import io
import json
import math
import time
import gzip
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import gradio as gr
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed


# ---------------- Harmony-Helpers (Format beachten) ----------------
# Messages bestehen aus {role, channel?, content:list[...]}

def _join_text_content(content) -> str:
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and "text" in c:
                t = str(c.get("text", "")).strip()
                if t:
                    parts.append(t)
        return "\n\n".join(parts).strip()
    return ""

def _first_role(messages: List[dict], role: str, channel: Optional[str] = None, default: str = "") -> str:
    for m in messages:
        if m.get("role") == role and (channel is None or m.get("channel") == channel):
            return _join_text_content(m.get("content", [])) or default
    return default

def _concat_role(messages: List[dict], role: str, channel: Optional[str] = None) -> str:
    out = []
    for m in messages:
        if m.get("role") == role and (channel is None or m.get("channel") == channel):
            t = _join_text_content(m.get("content", []))
            if t:
                out.append(t)
    return "\n\n---\n\n".join(out).strip()


# ---------------- JSONL Streaming + Index ----------------

def _is_gzip(path: Path) -> bool:
    return path.suffix.lower() in {".gz", ".gzip"}

def _iter_lines(path: Path) -> Iterable[Tuple[int, bytes]]:
    """
    Liefert (byte_offset, line_bytes) – ohne RAM-Voll-Load.
    Für .gz kein echtes Seek-Indexing; wir geben offset=-1 zurück.
    """
    if _is_gzip(path):
        with gzip.open(path, "rb") as f:
            for line in f:
                yield -1, line
    else:
        with open(path, "rb") as f:
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    break
                yield pos, line

def _safe_json_loads(b: bytes) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(b.decode("utf-8"))
    except Exception:
        return None

def _meta_from_obj(o: Dict[str, Any]) -> Dict[str, Any]:
    conv = o.get("conversation", {})
    msgs = conv.get("messages", []) or []
    developer = _first_role(msgs, "developer")
    user = _first_role(msgs, "user")
    analysis = _concat_role(msgs, "assistant", channel="analysis")
    final = _first_role(msgs, "assistant", channel="final")
    stats = o.get("stats", {}) or {}
    meta = o.get("meta", {}) or {}
    return dict(
        id=meta.get("id", ""),
        reasoning=str(stats.get("reasoning", "")),
        developer=developer,
        user=user,
        analysis=analysis,
        final=final,
        source=meta.get("source_url", ""),
        include_judgment=str(stats.get("include_judgment", "")),
        messages_count=len(msgs),
        user_len=len(user or ""),
        final_len=len(final or ""),
        has_analysis=bool(analysis),
    )

def build_or_load_index(dataset_path: Path, reuse: bool = True, workers: int = 0) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Erzeugt einen leichten Index (eine Zeile pro Beispiel) mit Byte-Offsets auf die JSONL-Datei.
    Spalten: id, reasoning, user, final, analysis, source, include_judgment, messages_count, user_len, final_len,
             has_analysis, byte_offset
    Für .gz ist byte_offset=-1 (kein random seek); wir streamen dann beim Paging.
    """
    idx_path = dataset_path.with_suffix(dataset_path.suffix + ".idx.parquet")
    sig = hashlib.sha1(f"{dataset_path.resolve()}:{dataset_path.stat().st_mtime}".encode()).hexdigest()[:12]

    if reuse and idx_path.exists():
        df = pd.read_parquet(idx_path)
        return df, sig

    rows = []
    lines_iter = list(_iter_lines(dataset_path))

    # Chunking
    chunk_size = 50_000 if not _is_gzip(dataset_path) else 20_000
    chunks = [lines_iter[i:i+chunk_size] for i in range(0, len(lines_iter), chunk_size)]

    def parse_chunk(chunk):
        out = []
        for offset, line in chunk:
            o = _safe_json_loads(line)
            if not o:
                continue
            m = _meta_from_obj(o)
            m["byte_offset"] = offset
            out.append(m)
        return out

    w = workers or max(1, os.cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=w) as ex:
        futs = [ex.submit(parse_chunk, ch) for ch in chunks]
        for fut in as_completed(futs):
            rows.extend(fut.result())

    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_parquet(idx_path, index=False)
    return df, sig

def read_records_by_offsets(dataset_path: Path, offsets: List[int]) -> List[Dict[str, Any]]:
    """Liest vollständige JSON-Objekte für gegebene Byte-Offsets (nur für unkomprimierte JSONL)."""
    out = []
    if _is_gzip(dataset_path):
        # Fallback: streamen, aber ineffizient – zur Not alles durchgehen
        for _, line in _iter_lines(dataset_path):
            o = _safe_json_loads(line)
            if o:
                out.append(o)
        return out

    with open(dataset_path, "rb") as f:
        for pos in offsets:
            f.seek(pos)
            line = f.readline()
            o = _safe_json_loads(line)
            if o:
                out.append(o)
    return out


# ---------------- Filtering / Paging ----------------

def apply_filters(df: pd.DataFrame,
                  reasoning: str,
                  search_in: str,
                  query: str,
                  source_contains: str,
                  user_len: Tuple[int,int],
                  final_len: Tuple[int,int],
                  has_analysis: Optional[bool]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    mask = pd.Series(True, index=df.index)

    if reasoning and reasoning != "(alle)":
        mask &= (df["reasoning"] == reasoning)

    if source_contains:
        mask &= df["source"].str.contains(source_contains, case=False, na=False)

    mask &= df["user_len"].between(user_len[0], user_len[1])
    mask &= df["final_len"].between(final_len[0], final_len[1])

    if has_analysis is True:
        mask &= df["has_analysis"] == True
    elif has_analysis is False:
        mask &= df["has_analysis"] == False

    if query:
        cols = ["developer", "user", "analysis", "final"] if search_in == "(alle Felder)" else [search_in]
        sub = pd.Series(False, index=df.index)
        for c in cols:
            sub |= df[c].fillna("").str.contains(query, case=False, na=False)
        mask &= sub

    return df[mask].copy()

def page_slice(df: pd.DataFrame, page: int, page_size: int) -> pd.DataFrame:
    total = len(df)
    if total == 0:
        return df
    pages = max(1, math.ceil(total / page_size))
    page = max(1, min(page, pages))
    start, end = (page-1)*page_size, (page-1)*page_size + page_size
    return df.iloc[start:end].copy()

def make_table_preview(df_page: pd.DataFrame, shorten=True) -> pd.DataFrame:
    if df_page.empty:
        return pd.DataFrame()
    def cut(s, n=120):
        s = str(s or "")
        return s if len(s) <= n else s[:n] + "…"
    view = df_page[["id","reasoning","source","user","final","messages_count","has_analysis"]].copy()
    if shorten:
        view["user"] = view["user"].map(lambda x: cut(x, 120))
        view["final"] = view["final"].map(lambda x: cut(x, 120))
    return view


# ---------------- Detail, Editor, Export ----------------

def show_detail(dataset_path: str, idx_row_json: str):
    if not idx_row_json:
        return "Kein Eintrag ausgewählt.", "", "", ""
    idx_row = json.loads(idx_row_json)
    offset = idx_row.get("byte_offset", -1)

    # Full record lesen
    o = None
    if offset >= 0:
        recs = read_records_by_offsets(Path(dataset_path), [offset])
        if recs:
            o = recs[0]
    else:
        # .gz: stream fallback
        for _, line in _iter_lines(Path(dataset_path)):
            cand = _safe_json_loads(line)
            if cand and (cand.get("meta", {}) or {}).get("id") == idx_row.get("id"):
                o = cand
                break
    if o is None:
        return "Record nicht gefunden.", "", "", ""

    # Nachrichtentexte extrahieren
    conv = o.get("conversation", {})
    msgs = conv.get("messages", []) or []
    parts = [f"**ID:** `{idx_row.get('id','')}`  \n**Quelle:** {idx_row.get('source','')}`  \n**Reasoning:** `{idx_row.get('reasoning','')}`  \n**Messages:** {len(msgs)}\n\n---"]
    for m in msgs:
        role = (m.get("role","") or "").upper()
        ch = m.get("channel","")
        header = f"**{role}**" + (f"  _(channel: {ch})_" if ch else "")
        text = _join_text_content(m.get("content", [])) or "_(kein Textinhalt)_"
        parts.append(header + "\n\n" + text + "\n\n---")
    detail_md = "\n".join(parts)

    # Editor-Felder vorbelegen
    user_txt = _first_role(msgs, "user")
    analysis_txt = _concat_role(msgs, "assistant", channel="analysis")
    final_txt = _first_role(msgs, "assistant", channel="final")

    return detail_md, user_txt, analysis_txt, final_txt

def export_subset(dataset_path: str, df_filtered_json: str) -> Tuple[str, str]:
    # df_filtered_json enthält nur id/byte_offset (Index-Teilmenge)
    dfi = pd.read_json(io.StringIO(df_filtered_json), orient="records")
    if dfi.empty:
        return gr.update(visible=False), "Nichts zu exportieren."
    out = Path("filtered.jsonl").resolve()
    with open(out, "w", encoding="utf-8") as f:
        if not _is_gzip(Path(dataset_path)) and "byte_offset" in dfi.columns:
            # schnell: per Offset
            recs = read_records_by_offsets(Path(dataset_path), dfi["byte_offset"].tolist())
            for o in recs:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
        else:
            # stream fallback
            wanted = set(dfi["id"].tolist())
            for _, line in _iter_lines(Path(dataset_path)):
                o = _safe_json_loads(line)
                if not o:
                    continue
                if (o.get("meta", {}) or {}).get("id", "") in wanted:
                    f.write(json.dumps(o, ensure_ascii=False) + "\n")
    return str(out), f"Exportiert: {out}"

def apply_edits_to_record(o: Dict[str, Any], user_txt: str, analysis_txt: str, final_txt: str) -> Dict[str, Any]:
    """Wendet Editor-Änderungen auf ein in-Memory Record an (nicht auf Datei)."""
    conv = o.get("conversation", {})
    msgs = conv.get("messages", []) or []

    # Helper: setze (ersetze) Textcontent für eine Rolle/Channel
    def set_text(role: str, channel: Optional[str], value: str):
        # finde passende Message
        target = None
        for m in msgs:
            if m.get("role") == role and (channel is None or m.get("channel") == channel):
                target = m
                break
        if target is None:
            # Neue Message anfügen
            m = {"role": role, "content": [{"type": "text", "text": value}]}
            if channel:
                m["channel"] = channel
            msgs.append(m)
        else:
            # content ersetzen
            target["content"] = [{"type": "text", "text": value}]

    if user_txt is not None:
        set_text("user", None, user_txt)
    if analysis_txt is not None:
        # Analysis als eigener Assistant-Block mit channel="analysis"
        set_text("assistant", "analysis", analysis_txt)
    if final_txt is not None:
        set_text("assistant", "final", final_txt)

    conv["messages"] = msgs
    o["conversation"] = conv
    return o


# ---------------- Gradio App ----------------

def enable_queue(demo, workers=None, max_size=64):
    """
    Aktiviert die Gradio-Queue versionssicher:
    - neuere Gradio: concurrency_count / max_size
    - ältere Gradio: default_concurrency_limit / max_size
    - Fallback: ohne Argumente
    """
    workers = workers or (os.cpu_count() or 4)
    tried = (
        {"concurrency_count": workers, "max_size": max_size},
        {"default_concurrency_limit": workers, "max_size": max_size},
        {},
    )
    for kwargs in tried:
        try:
            return demo.queue(**kwargs)
        except TypeError:
            continue
    return demo

def app():
    with gr.Blocks(title="Harmony Data Studio") as demo:
        gr.Markdown("## 🧠 Harmony Data Studio (Gradio) — inspiriert von Hugging Face Data Studio")

        # ---------- Kopf: Dataset laden / Index -----------
        with gr.Row():
            dataset_path = gr.Textbox(label="Pfad zu JSONL/JSONL.GZ", value="../data/dataset/data/train.jsonl")
            build_btn = gr.Button("Index bauen / laden", variant="primary")
        status = gr.Markdown()

        # interner Cache
        cache = {
            "df": None,        # Vollindex (DataFrame)
            "sig": None,       # Signatur
            "edits": {},       # id -> geänderter Full-Record (JSON-Objekt)
        }

        # ---------- Filter -----------
        with gr.Accordion("Filter", open=True):
            with gr.Row():
                reasoning = gr.Dropdown(choices=["(alle)","low","medium","high"], value="(alle)", allow_custom_value=True, label="Reasoning")
                search_in = gr.Dropdown(choices=["(alle Felder)","user","final","developer","analysis"], value="(alle Felder)", allow_custom_value=True, label="Suche in")
                query = gr.Textbox(label="Volltextsuche")
            with gr.Row():
                source_contains = gr.Textbox(label="Quelle enthält")
                has_analysis = gr.Dropdown(choices=["egal","nur mit Analysis","nur ohne Analysis"], value="egal", allow_custom_value=True, label="Analysis")
                shorten_preview = gr.Checkbox(value=True, label="Textvorschau kürzen")
            with gr.Row():
                user_len_max = gr.Slider(0, 100000, value=100000, step=100, label="user_len ≤")
                final_len_max = gr.Slider(0, 100000, value=100000, step=100, label="final_len ≤")
            with gr.Row():
                page = gr.Slider(minimum=1, maximum=1, step=1, value=1, label="Seite")
                page_size = gr.Dropdown(choices=[10,25,50,100,200,500], value=50, label="Zeilen/Seite")
                apply_btn = gr.Button("Filter anwenden", variant="secondary")

        df_filtered_store = gr.State("")   # JSON-String des gefilterten DF (nur Index-Spalten)
        table = gr.Dataframe(interactive=False, wrap=True, label="Vorschau (ähnlich HF Data Studio)")
        select_row = gr.Dropdown(label="Zeile wählen (Detail)", choices=[], value=None)
        detail = gr.Markdown()

        # ---------- Editor ----------
        gr.Markdown("### ✏️ Editor")
        with gr.Row():
            user_edit = gr.Textbox(lines=10, label="USER (Prompt)")
            analysis_edit = gr.Textbox(lines=10, label="ASSISTANT (analysis/CoT)")
            final_edit = gr.Textbox(lines=10, label="ASSISTANT (final)")
        with gr.Row():
            save_edit_btn = gr.Button("Änderungen zwischenspeichern")
            export_edits_btn = gr.Button("Alle Änderungen exportieren")
            edits_download = gr.File(label="Download (edits.jsonl)", interactive=False)

        # ---------- Export gefiltertes Subset ----------
        export_btn = gr.Button("Gefiltertes Subset exportieren (.jsonl)")
        download = gr.File(label="Download (filtered.jsonl)", interactive=False)

        # ---------- Logik ----------

        def _build(path: str):
            p = Path(path).expanduser().resolve()
            if not p.exists():
                return gr.update(value="❌ Datei nicht gefunden."), gr.update(maximum=1, value=1), gr.update(maximum=1, value=1), pd.DataFrame(), [], None, ""
            t0 = time.time()
            df, sig = build_or_load_index(p, reuse=True, workers=os.cpu_count() or 4)
            cache["df"], cache["sig"] = df, sig
            if df.empty:
                return gr.update(value=f"⚠️ Index leer ({p})"), gr.update(maximum=1, value=1), gr.update(maximum=1, value=1), pd.DataFrame(), [], None, ""
            # Slider Maxima
            u_max = int(max(100, df["user_len"].max()))
            f_max = int(max(100, df["final_len"].max()))
            pages = max(1, math.ceil(len(df)/50))
            status_md = f"✅ Index bereit ({len(df)} Zeilen) – Signatur `{sig}`"
            return gr.update(value=status_md), gr.update(maximum=u_max, value=u_max), gr.update(maximum=f_max, value=f_max), \
                   pd.DataFrame(), [], None, ""  # leere Tabelle bis Filter gedrückt wird

        def _filters_to_df(path, reasoning_v, search_in_v, query_v, source_v, has_analysis_v, shorten, user_len_v, final_len_v, page_v, page_size_v):
            df = cache["df"]
            if df is None or df.empty:
                return gr.update(value="⚠️ Bitte zuerst Index bauen."), pd.DataFrame(), gr.update(choices=[], value=None), ""

            ha = None
            if has_analysis_v == "nur mit Analysis": ha = True
            elif has_analysis_v == "nur ohne Analysis": ha = False

            dff = apply_filters(df,
                                reasoning_v, search_in_v, query_v or "",
                                source_v or "", (0, int(user_len_v)), (0, int(final_len_v)),
                                ha)
            total = len(dff)
            page_v = int(max(1, page_v))
            pages = max(1, math.ceil(total / int(page_size_v)))
            page_v = min(page_v, pages)
            # page Slider updaten
            page_update = gr.update(maximum=pages, value=page_v)

            dff_page = page_slice(dff, page_v, int(page_size_v))
            table_df = make_table_preview(dff_page, shorten=bool(shorten))

            # Dropdown-Optionen erstellen
            options = []
            for _, row in dff_page.iterrows():
                label = f"{row['id'][:8]} | {row['reasoning']} | msgs={row['messages_count']}"
                value = json.dumps(row.to_dict())
                options.append((label, value))
            initial_value = options[0][1] if options else None

            # Gefilterten Index sparen (id + byte_offset)
            dff_index_cols = ["id","byte_offset"]
            dff_json = json.dumps(dff[dff_index_cols].to_dict(orient="records"))

            note = f"**Treffer:** {total} — Seite {page_v}/{pages} — PageSize={page_size_v}"
            return gr.update(value=note), table_df, gr.update(choices=options, value=initial_value), dff_json, page_update

        def _detail(path, row_json):
            md, user_txt, analysis_txt, final_txt = show_detail(path, row_json)
            return md, user_txt, analysis_txt, final_txt

        def _save_edit(path, row_json, user_txt, analysis_txt, final_txt):
            if not row_json:
                return gr.update(value="Kein Datensatz ausgewählt. Änderungen nicht gespeichert.")
            idx_row = json.loads(row_json)
            offset = idx_row.get("byte_offset", -1)
            rec = None
            # Vollrecord lesen
            if offset >= 0:
                rs = read_records_by_offsets(Path(path), [offset])
                if rs:
                    rec = rs[0]
            else:
                # Fallback .gz (langsam)
                for _, line in _iter_lines(Path(path)):
                    cand = _safe_json_loads(line)
                    if cand and (cand.get("meta", {}) or {}).get("id") == idx_row.get("id"):
                        rec = cand
                        break
            if rec is None:
                return gr.update(value="Fehler: Record nicht gefunden, keine Speicherung.")
            # Edits anwenden
            rec2 = apply_edits_to_record(rec, user_txt, analysis_txt, final_txt)
            rid = (rec2.get("meta", {}) or {}).get("id") or idx_row.get("id")
            cache["edits"][rid] = rec2
            return gr.update(value=f"✅ Änderungen zwischengespeichert (id={rid[:8]}…, aktuell {len(cache['edits'])} geändert).")

        def _export_edits():
            if not cache["edits"]:
                return gr.update(visible=False), gr.update(value="Keine Änderungen vorhanden.")
            out = Path("edits.jsonl").resolve()
            with open(out, "w", encoding="utf-8") as f:
                for _, rec in cache["edits"].items():
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return gr.update(value=str(out), visible=True), gr.update(value=f"Exportiert: {out} ({len(cache['edits'])} Records)")

        def _export(path, dff_json):
            out, msg = export_subset(path, dff_json)
            return gr.update(value=out, visible=True), gr.update(value=msg)

        # Verdrahtung
        build_btn.click(_build, inputs=[dataset_path],
                        outputs=[status, user_len_max, final_len_max, table, select_row, detail, df_filtered_store])

        apply_btn.click(_filters_to_df,
                        inputs=[dataset_path, reasoning, search_in, query, source_contains, has_analysis, shorten_preview, user_len_max, final_len_max, page, page_size],
                        outputs=[status, table, select_row, df_filtered_store, page])

        select_row.change(_detail, inputs=[dataset_path, select_row], outputs=[detail, user_edit, analysis_edit, final_edit])

        save_edit_btn.click(_save_edit, inputs=[dataset_path, select_row, user_edit, analysis_edit, final_edit], outputs=[status])

        export_edits_btn.click(_export_edits, inputs=None, outputs=[edits_download, status])

        export_btn.click(_export, inputs=[dataset_path, df_filtered_store], outputs=[download, status])

    return demo


if __name__ == "__main__":
    demo = app()
    # Queue versionssicher aktivieren
    def enable_queue(demo, workers=None, max_size=64):
        workers = workers or (os.cpu_count() or 4)
        tried = (
            {"concurrency_count": workers, "max_size": max_size},
            {"default_concurrency_limit": workers, "max_size": max_size},
            {},
        )
        for kwargs in tried:
            try:
                return demo.queue(**kwargs)
            except TypeError:
                continue
        return demo

    enable_queue(demo, workers=os.cpu_count() or 4, max_size=128)
    demo.launch(server_name="0.0.0.0", server_port=7860, show_api=False)
