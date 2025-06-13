import gradio as gr
import pandas as pd
from pandas.io.formats.style import Styler
import json
from pathlib import Path
from typing import List

# 📁 Pfade
QA_PAIRS_PATH = Path("../data/generated/qa_pairs.jsonl")

# 📊 Anzeigeeinstellungen
PAGE_SIZES = [10, 25, 50, 100]
DEFAULT_PAGE_SIZE = 10


def load_qa_pairs_as_dataframe(source_filter: str = "", limit: int = 100, offset: int = 0) -> pd.DataFrame:
    """
    Lädt QA-Paare aus der JSONL-Datei als Pandas DataFrame mit optionalem Filter.

    :param source_filter: Optionaler Filter nach 'source_file'
    :param limit: Maximale Anzahl der Zeilen
    :param offset: Offset für Pagination
    :return: Gefilterter DataFrame
    """
    rows = []
    with open(QA_PAIRS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < offset:
                continue
            if len(rows) >= limit:
                break
            try:
                entry = json.loads(line)
                if source_filter and source_filter.lower() not in entry.get("source_file", "").lower():
                    continue
                rows.append(entry)
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(rows)


def style_dataframe(df: pd.DataFrame) -> Styler:
    """
    Markiert fehlende Felder farblich: instruction/output rot, input gelb.

    :param df: Eingabe-DataFrame
    :return: Gestylter DataFrame
    """

    def highlight_missing(val, col):
        if col in ["instruction", "output"] and (pd.isna(val) or str(val).strip() == ""):
            return "background-color: #ffdddd"
        elif col == "input" and (pd.isna(val) or str(val).strip() == ""):
            return "background-color: #fff3cd"
        return ""

    return df.style.applymap(lambda val: highlight_missing(val, "instruction"), subset=["instruction"]) \
                   .applymap(lambda val: highlight_missing(val, "input"), subset=["input"]) \
                   .applymap(lambda val: highlight_missing(val, "output"), subset=["output"])


def get_source_options() -> List[str]:
    """
    Extrahiert alle eindeutigen 'source_file'-Werte aus der JSONL-Datei für die Dropdown-Auswahl.

    :return: Liste von Quellen
    """
    sources = set()
    with open(QA_PAIRS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if "source_file" in entry:
                    sources.add(entry["source_file"])
            except json.JSONDecodeError:
                continue
    return sorted(list(sources))


def update_table_view(page_size: int, page_number: int, source_filter: str) -> pd.DataFrame:
    """
    Wird durch Gradio aufgerufen, um die aktuelle Tabelle basierend auf Filter/Pagination neu zu laden.

    :param page_size: Anzahl der Einträge pro Seite
    :param page_number: Seitenzahl (0-basiert)
    :param source_filter: Aktiver Filter
    :return: Formatierter DataFrame zur Anzeige
    """
    offset = page_size * page_number
    df = load_qa_pairs_as_dataframe(source_filter, limit=page_size, offset=offset)
    return style_dataframe(df)


def save_dataframe_to_jsonl(df: pd.DataFrame) -> str:
    """
    Speichert den bearbeiteten DataFrame zurück in eine JSONL-Datei.

    :param df: Geänderter DataFrame
    :return: Statusmeldung
    """
    try:
        with open(QA_PAIRS_PATH, "w", encoding="utf-8") as f:
            for _, row in df.iterrows():
                json.dump(row.dropna().to_dict(), f, ensure_ascii=False)
                f.write("\n")
        return "✅ Änderungen wurden gespeichert."
    except Exception as e:
        return f"❌ Fehler beim Speichern: {str(e)}"


# 🧠 Gradio UI
with gr.Blocks(title="QA-Pairs Annotator") as demo:
    gr.Markdown("## 🧠 QA-Paare interaktiv bearbeiten")

    with gr.Row():
        page_size = gr.Dropdown(PAGE_SIZES, value=DEFAULT_PAGE_SIZE, label="Einträge pro Seite")
        page_number = gr.Slider(minimum=0, maximum=100, step=1, value=0, label="Seite")
        source_filter = gr.Dropdown(label="Quelle filtern", choices=[""] + get_source_options())
        refresh_btn = gr.Button("🔍 Laden")

    df_view = gr.Dataframe(label="QA-Daten", interactive=True, wrap=True, row_count=10)
    save_btn = gr.Button("💾 Speichern")
    status_box = gr.Textbox(label="Status", interactive=False)

    refresh_btn.click(
        fn=update_table_view,
        inputs=[page_size, page_number, source_filter],
        outputs=df_view
    )

    save_btn.click(
        fn=save_dataframe_to_jsonl,
        inputs=df_view,
        outputs=status_box
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
