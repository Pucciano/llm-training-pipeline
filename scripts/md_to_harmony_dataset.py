#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Konvertiert Markdown-Dateien mit YAML-Frontmatter in Harmony-Conversationen
und exportiert sie als JSONL für Hugging Face.

Funktionen:
- Liest .md-Dateien mit variabler YAML-Frontmatter.
- Extrahiert Meta (Gericht, ECLI, Normen, Quelle/URL, etc.) und Body (Zusammenfassung + Urteil).
- Erzeugt Harmony-Conversations via `openai_harmony`:
  * System: Identität, Reasoning (low/med/high verteilt), Cutoff=2024-06, Current date=today.
  * Developer: juristische Anweisungen + deklarierte Function-Tools (ohne Calls).
  * User: Aufgabe + Meta + (konfigurierbar) Urteil: full | truncated | meta-only.
  * Assistant.final: 1:1 geprüfte Zusammenfassung.
  * Optional Assistant.analysis: deterministisch/LLM-generiert/aus.
- Token-Budget-Prüfung; bei Überschreitung wird Urteil gekürzt (oder optional gechunkt).
- Erzeugt train/validation/test-Splits.
- Schreibt JSONL mit `conversation` (Harmony-JSON) + `meta` + `stats`.
- Optionale LLM-CoT-Generierung via Ollama oder OpenAI (deaktiviert per Default).

Benötigt:
  python 3.12, uv/pip install:
    - openai-harmony
    - pyyaml
    - markdown-it-py (nur wenn Markdown weiter geparst wird; hier optional)

Beispielaufruf:
python md_to_harmony_dataset.py \
    --input /pfad/markdown \
    --output ./dataset \
    --include-judgment truncated \
    --reasoning balanced \
    --analysis openai \
    --analysis-llm "gpt-4o-mini" \
    --openai-base-url "http://127.0.0.1:1234" \
    --openai-api-key "lm-studio"

"""

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml

from openai_harmony import (
    Conversation,
    DeveloperContent,
    HarmonyEncodingName,
    Message,
    ReasoningEffort,
    Role,
    SystemContent,
    ToolDescription,
    load_harmony_encoding,
    RenderConversationConfig,
)

# ----------------- Defaults & Const -----------------

DEFAULT_KNOWLEDGE_CUTOFF = "2024-06"
VALID_CHANNELS = ["analysis", "commentary", "final"]

RANDOM_SEED = 47

# Zielbudget für den User-Content (Urteil)
DEFAULT_TARGET_USER_TOKENS = 16_384
# Globales Budget über die gesamte Conversation (System+Dev+User+Assistant)
DEFAULT_MAX_CONVO_TOKENS = 24_576

# ------------- kleine Utils -------------

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", "ignore")).hexdigest()

def normalize_key(k: str) -> str:
    k = k.strip().replace(" ", "_").replace(".", "")
    return k.lower()

def extract_frontmatter(md: str) -> tuple[dict, str]:
    lines = md.splitlines()
    if not lines or not lines[0].strip().startswith('---'):
        return {}, md
    fm_lines, i = [], 1
    while i < len(lines):
        if lines[i].strip().startswith('---'):
            break
        fm_lines.append(lines[i])
        i += 1
    # Falls kein schließendes --- gefunden:
    if i >= len(lines) or not lines[i].strip().startswith('---'):
        return {}, md
    raw_yaml = "\n".join(fm_lines)
    body = "\n".join(lines[i+1:])
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except Exception:
        data = {}
    return data, body


def split_summary_and_judgment(body_md: str) -> tuple[str, str]:
    # Heuristik: ab "## Urteil" oder "## Entscheidungsgründe" den Body als Urteil werten
    m = re.search(r"(?mi)^\s{0,3}##\s+(Urteil|Entscheidungsgründe|Tatbestand)\b", body_md)
    if not m:
        return body_md.strip(), ""
    return body_md[:m.start()].strip(), body_md[m.start():].strip()


def normalize_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    norm: Dict[str, Any] = {normalize_key(str(k)): v for k, v in meta.items()}
    src = meta.get("Quelle") or meta.get("source") or meta.get("URL")
    if src: norm["source"] = str(src).strip()
    ecli = meta.get("ECLI") or meta.get("ecli")
    if ecli and (v := validate_ecli(str(ecli))):
        norm["ecli"] = v
    # Normen normalisieren
    raw_norms = meta.get("Normen") or meta.get("normen")
    norms_list = []
    if isinstance(raw_norms, str):
        parts = [p.strip() for p in raw_norms.split(",")]
        norms_list = [re.sub(r"\s+", " ", p) for p in parts if p]
    elif isinstance(raw_norms, list):
        norms_list = [re.sub(r"\s+", " ", str(p)).strip() for p in raw_norms]
    if norms_list:
        # Deduplizieren, Ordnung bewahren
        seen, uniq = set(), []
        for n in norms_list:
            if n not in seen:
                seen.add(n); uniq.append(n)
        norm["norms"] = uniq
    return norm

def det_reasoning(i: int) -> ReasoningEffort:
    return [ReasoningEffort.LOW, ReasoningEffort.MEDIUM, ReasoningEffort.HIGH][i % 3]

def build_system_content(reasoning: ReasoningEffort,
                         current_date: Optional[str],
                         with_browser: bool,
                         with_python: bool) -> SystemContent:
    # System-Message gemäß Harmony: Identität, Reasoning, Dates, Channels, Tools
    sysc = (
        SystemContent.new()
        .with_model_identity("You are ChatGPT, a large language model trained by OpenAI.")
        .with_reasoning_effort(reasoning)
        .with_conversation_start_date(current_date or dt.date.today().isoformat())
        .with_knowledge_cutoff(DEFAULT_KNOWLEDGE_CUTOFF)
        .with_required_channels(VALID_CHANNELS)
    )
    if with_browser:
        sysc = sysc.with_browser_tool()
    if with_python:
        sysc = sysc.with_python_tool()
    return sysc

def build_developer_content(instructions: Optional[str],
                            include_function_sigs: bool) -> DeveloperContent:
    dev = DeveloperContent.new().with_instructions(instructions or (
        "# Instructions\n"
        "Antworte auf Deutsch, juristisch präzise und strukturiert. "
        "Nutze die Gliederung (Leitsatz, Sachverhalt, Entscheidungsgründe, Ergebnis). "
        "Bewahre Zitate/Normen, führe eine Rechtsberatung durch.\n"
    ))
    if include_function_sigs:
        tools = [
            ToolDescription.new(
                "validate_citation",
                "Prüft eine Norm- oder Fundstellenangabe auf korrekte Zitierweise.",
                parameters={"type": "object", "properties": {"ref": {"type": "string"}}, "required": ["ref"]},
            ),
            ToolDescription.new(
                "extract_norms",
                "Extrahiert Normverweise aus einem Text.",
                parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            ),
            ToolDescription.new(
                "find_ecli",
                "Findet eine ECLI in einem Text.",
                parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            ),
            ToolDescription.new(
                "summarize_section",
                "Fasst einen Abschnitt auf Zielquote zusammen.",
                parameters={"type": "object", "properties": {
                    "title": {"type": "string"},
                    "text": {"type": "string"},
                    "ratio": {"type": "number"}
                }, "required": ["title","text"]},
            ),
        ]
        dev = dev.with_function_tools(tools)
    return dev

def synthesize_user_prompt(norm_meta: Dict[str, Any], include_judgment: str, judgment_text: str) -> str:
    lines = []
    lines.append("Fasse den folgenden Rechtstext prägnant zusammen (Leitsatz, Sachverhalt, Entscheidungsgründe, Ergebnis).")
    lines.append("Bewahre Zitate, wörtliche Zitationen und Normen.")
    lines.append("")
    if norm_meta.get("source"):
        lines.append(f"Quelle: {norm_meta.get('source')}")
    if norm_meta.get("fundstelle"):
        lines.append(f"Fundstelle: {norm_meta.get('fundstelle')}")
    if norm_meta.get("gericht"):
        lines.append(f"Gericht: {norm_meta.get('gericht')}")
    if norm_meta.get("ecli"):
        lines.append(f"ECLI: {norm_meta.get('ecli')}")
    if norm_meta.get("norms"):
        lines.append("Normen: " + ", ".join(norm_meta.get("norms")))
    lines.append("")
    if include_judgment in ("full", "truncated") and judgment_text:
        lines.append("=== URTEIL (EINGANG) ===")
        lines.append(judgment_text)
        lines.append("=== URTEIL (ENDE) ===")
    else:
        lines.append("(Hinweis: Volltext des Urteils wurde nicht eingebettet; arbeite mit den Metadaten.)")
    return "\n".join(lines).strip()

def deterministic_analysis_stub(norm_meta: Dict[str, Any], summary_md: str) -> str:
    title_match = re.search(r"^#\s+(.+)$", summary_md, flags=re.M)
    title = title_match.group(1).strip() if title_match else "Zusammenfassung"
    court = norm_meta.get("gericht") or "Gericht nicht angegeben"
    return (f'Ziel: „{title}“. Kontext: {court}. '
            f'Vorgehen: Gliederung Leitsatz–Sachverhalt–Gründe–Ergebnis mit Normenbezug. '
            f'Kriterien: Präzision, Zitatgenauigkeit, keine Rechtsberatung.')

# ---------- Harmony-Tokenisierung / Budget ----------

def token_len(enc, txt: str) -> int:
    return len(enc.render(Message.from_role_and_content(Role.USER, txt)))

def truncate_to_token_budget(enc, text: str, target_tokens: int) -> Tuple[str, bool]:
    toks = enc.render(Message.from_role_and_content(Role.USER, text))
    if len(toks) <= target_tokens:
        return text, False
    paras = re.split(r"\n{2,}", text)
    out, total = [], 0
    for p in paras:
        cand = "\n\n".join(out + [p])
        n = len(enc.render(Message.from_role_and_content(Role.USER, cand)))
        if n <= target_tokens:
            out.append(p); total = n
        else:
            break
    if not out:
        approx_ratio = target_tokens / max(1, len(toks))
        cutoff = max(200, int(len(text) * approx_ratio))
        truncated = text[:cutoff]
    else:
        truncated = "\n\n".join(out)
    truncated += "\n\n[Hinweis: Urteil gekürzt, vollständiger Text nicht vollständig eingebettet.]"
    return truncated, True

def enforce_conversation_budget(enc, convo: Conversation, max_tokens: int, max_rounds: int = 4) -> tuple[Conversation, bool]:
    changed = False
    for _ in range(max_rounds):
        toks = enc.render_conversation_for_training(convo)
        if len(toks) <= max_tokens or max_tokens <= 0:
            return convo, changed
        msgs = list(convo.messages)
        # USER i.d.R. index 2
        if len(msgs) >= 3 and msgs[2].role == Role.USER:
            content = msgs[2].get_text_content()
            m = re.search(r"=== URTEIL \(EINGANG\) ===(.*)=== URTEIL \(ENDE\) ===", content, flags=re.S)
            if not m:
                break
            judgment = m.group(1).strip()
            # Reduziere progressiv (z. B. 70%, 50%, 30%, 15%)
            factor = 0.7
            target = int(len(enc.render(Message.from_role_and_content(Role.USER, judgment))) * factor)
            truncated, _ = truncate_to_token_budget(enc, judgment, max(512, target))
            new_content = content[:m.start(1)] + "\n" + truncated + "\n" + content[m.end(1):]
            msgs[2] = msgs[2].with_text_content(new_content)
            convo = Conversation.from_messages(msgs)
            changed = True
        else:
            break
    return convo, changed


# ---------- Conversation-Bau ----------

def build_conversation(enc,
    reasoning: ReasoningEffort,
    developer_instructions: Optional[str],
    include_function_sigs: bool,
    include_builtins: Tuple[bool, bool],
    user_prompt: str,
    summary_md: str,
) -> Conversation:
    sysc = build_system_content(reasoning, dt.date.today().isoformat(), include_builtins[0], include_builtins[1])  #
    devc = build_developer_content(developer_instructions, include_function_sigs)
    msgs: List[Message] = [
        Message.from_role_and_content(Role.SYSTEM, sysc),
        Message.from_role_and_content(Role.DEVELOPER, devc),
        Message.from_role_and_content(Role.USER, user_prompt),
        Message.from_role_and_content(Role.ASSISTANT, summary_md).with_channel("final"),
    ]
    return Conversation.from_messages(msgs)

def insert_analysis(convo: Conversation, analysis_text: str) -> Conversation:
    msgs = list(convo.messages)
    analysis_msg = Message.from_role_and_content(Role.ASSISTANT, analysis_text).with_channel("analysis")
    # Einfügen direkt vor dem final
    msgs.insert(3, analysis_msg)
    return Conversation.from_messages(msgs)

# ---------- OpenAI-kompatibles CoT ----------

def generate_analysis_openai(
    prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    timeout_s: float = 30.0,
    max_chars: int = 1500,
) -> str:
    """
    Minimaler Client für POST /v1/chat/completions (OpenAI-kompatibel, z.B. LM Studio)
    """
    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Du verfasst nur eine kurze Plan-Notiz (2-4 Sätze) für eine juristische Zusammenfassung. Keine Inhalte zitieren, nur Vorgehensplan/Kriterien."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 256,
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
        r.raise_for_status()
        data = r.json()
        txt = data["choices"][0]["message"]["content"].strip()
        return txt[:max_chars]
    except Exception as e:
        # Fallback: deterministische Notiz
        return "Plan: Gliederung Leitsatz–Sachverhalt–Gründe–Ergebnis; Normen markieren; präzise, keine Rechtsberatung."

# -------------- Datenobjekt --------------

@dataclasses.dataclass
class Record:
    conversation_json: str
    meta: Dict[str, Any]
    stats: Dict[str, Any]

# -------------- Hauptverarbeitung --------------

def process_file(
    path: Path,
    enc,
    idx: int,
    args: argparse.Namespace,
) -> List[Record]:
    raw = read_text(path)
    yaml_dict, body_md = extract_frontmatter(raw)
    norm_meta = normalize_meta(yaml_dict)
    raw_yaml_str = raw.split("---", 2)[1].strip() if raw.lstrip().startswith("---") else ""

    summary_md, judgment_md = split_summary_and_judgment(body_md)

    # --- Längen-Mix steuert Zielbudget pro Beispiel ---
    short_p, mid_p, long_p = map(float, args.length_mix.split(","))
    rnd = random.Random(idx + RANDOM_SEED)
    u = rnd.random()
    if u < short_p:
        target_user_tokens = min(args.target_user_tokens, 4096)
    elif u < short_p + mid_p:
        target_user_tokens = min(args.target_user_tokens, 16384)
    else:
        target_user_tokens = args.target_user_tokens  # z.B. 16k oder via CLI 24–32k

    # Urteil ggf. einbetten
    truncated = False
    judgment_embedded = ""
    if args.include_judgment in ("full", "truncated") and judgment_md:
        if args.include_judgment == "full":
            judgment_embedded = judgment_md
        else:
            judgment_embedded, truncated = truncate_to_token_budget(enc, judgment_md, target_user_tokens)

    user_prompt = synthesize_user_prompt(norm_meta, args.include_judgment, judgment_embedded)

    reasoning = det_reasoning(idx) if args.reasoning == "balanced" else {
        "low": ReasoningEffort.LOW,
        "medium": ReasoningEffort.MEDIUM,
        "high": ReasoningEffort.HIGH,
    }[args.reasoning]

    convo = build_conversation(
        enc=enc,
        reasoning=reasoning,
        developer_instructions=args.dev_instructions,
        include_function_sigs=not args.no_functions,
        include_builtins=(not args.no_browser, not args.no_python),
        user_prompt=user_prompt,
        summary_md=summary_md,
    )

    # Analysis optional hinzufügen
    if args.analysis == "deterministic":
        analysis_text = deterministic_analysis_stub(norm_meta, summary_md)
        convo = insert_analysis(convo, analysis_text)
    elif args.analysis == "openai":
        cot_prompt = "Erzeuge eine kurze Plan-Notiz zur juristischen Zusammenfassung (2–4 Sätze), nur Vorgehen und Qualitätskriterien."
        analysis_text = generate_analysis_openai(
            prompt=cot_prompt,
            base_url=args.openai_base_url,
            api_key=args.openai_api_key or "lm-studio",
            model=args.analysis_llm or "gpt-4o-mini",  # beliebiger Model-Name, LM Studio mappt lokal
        )
        convo = insert_analysis(convo, analysis_text)

    # Globales Budget prüfen/erzwingen
    if args.max_conversation_tokens > 0:
        convo, _ = enforce_conversation_budget(enc, convo, args.max_conversation_tokens)

    # Render-Test (Harmony Renderer)
    try:
        _ = enc.render_conversation_for_training(convo, config=RenderConversationConfig(auto_drop_analysis=False))
    except Exception:
        # Drop analysis als Fallback
        convo = Conversation.from_messages([m for m in convo.messages if m.channel != "analysis"])
        _ = enc.render_conversation_for_training(convo)

    conv_json = convo.to_json()
    rid = sha1_hex((norm_meta.get("source") or "") + path.name + conv_json[:4096])

    meta_out = {
        "id": rid,
        "source_path": str(path),
        "source_url": norm_meta.get("source"),
        "raw_yaml": raw_yaml_str,
        "yaml": yaml_dict,
        "normalized": norm_meta,
    }
    stats = {
        "truncated": truncated,
        "include_judgment": args.include_judgment,
        "reasoning": reasoning.name.lower(),
        "target_user_tokens": target_user_tokens,
        "max_conversation_tokens": args.max_conversation_tokens,
    }
    return [Record(conversation_json=conv_json, meta=meta_out, stats=stats)]

def write_jsonl(path: Path, records: List[Record]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            obj = {
                "conversation": json.loads(r.conversation_json),
                "meta": r.meta,
                "stats": r.stats,
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def split_records(records: List[Record], train: float, val: float, test: float, seed: int):
    assert abs((train + val + test) - 1.0) < 1e-6
    rnd = random.Random(seed)
    items = records[:]
    rnd.shuffle(items)
    n = len(items)
    n_train = int(n * train)
    n_val = int(n * val)
    return items[:n_train], items[n_train:n_train+n_val], items[n_train+n_val:]

def main():
    ap = argparse.ArgumentParser(description="Markdown -> Harmony JSONL (HF-kompatibel)")
    ap.add_argument("--input", type=str, required=True)
    ap.add_argument("--output", type=str, required=True)
    ap.add_argument("--include-judgment", choices=["meta","truncated","full"], default="truncated")
    ap.add_argument("--target-user-tokens", type=int, default=DEFAULT_TARGET_USER_TOKENS,
                    help="Ziel-Tokenbudget für den eingebetteten Urteilstext (User-Message).")
    ap.add_argument("--max-conversation-tokens", type=int, default=DEFAULT_MAX_CONVO_TOKENS,
                    help="Gesamtbudget über alle Messages (0=deaktiviert).")
    ap.add_argument("--length-mix", type=str, default="0.6,0.3,0.1",
                    help="Anteile kurz,mittel,lang (Summe=1). Steuert Ziel-Budgets pro Sample.")
    ap.add_argument("--reasoning", choices=["balanced","low","medium","high"], default="balanced")
    ap.add_argument("--analysis", choices=["deterministic","none","openai"], default="deterministic")
    ap.add_argument("--analysis-llm", type=str, default=None,
                    help="Modellname für /v1/chat/completions (bei --analysis=openai).")
    ap.add_argument("--openai-base-url", type=str, default=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:1234"),
                    help="Basis-URL des OpenAI-kompatiblen Dienstes (ohne /v1).")
    ap.add_argument("--openai-api-key", type=str, default=os.getenv("OPENAI_API_KEY", "lm-studio"),
                    help="API-Key (LM Studio akzeptiert meist einen Dummy-Token).")
    ap.add_argument("--no-functions", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--no-python", action="store_true")
    ap.add_argument("--dev-instructions", type=str, default=None,
                    help="Pfad zu Developer-Template. Wenn leer, wird ein Default genutzt.")
    ap.add_argument("--train-ratio", type=float, default=0.9)
    ap.add_argument("--val-ratio", type=float, default=0.05)
    ap.add_argument("--test-ratio", type=float, default=0.05)
    ap.add_argument("--encoding", type=str, default="HARMONY_GPT_OSS",
                    help="HarmonyEncodingName oder String (z.B. HARMONY_GPT_OSS).")
    args = ap.parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if args.dev_instructions and Path(args.dev_instructions).exists():
        args.dev_instructions = read_text(Path(args.dev_instructions))

    # Encoder laden (OSS-Encoding)
    try:
        enc = load_harmony_encoding(getattr(HarmonyEncodingName, args.encoding))
    except Exception:
        enc = load_harmony_encoding(args.encoding)

    paths = sorted(list(input_dir.rglob("*.md")))
    all_records: List[Record] = []
    for i, p in enumerate(paths):
        try:
            all_records += process_file(p, enc, i, args)
        except Exception as e:
            print(f"[WARN] {p}: {e}", file=sys.stderr)

    if not all_records:
        print("Keine Datensätze erzeugt.", file=sys.stderr)
        sys.exit(2)

    train_set, val_set, test_set = split_records(
        all_records, args.train_ratio, args.val_ratio, args.test_ratio, RANDOM_SEED
    )

    write_jsonl(data_dir / "train.jsonl", train_set)
    write_jsonl(data_dir / "validation.jsonl", val_set)
    write_jsonl(data_dir / "test.jsonl", test_set)

    print(f"Fertig. train={len(train_set)}  val={len(val_set)}  test={len(test_set)}")
    print(f"Ausgabe: {output_dir}")

if __name__ == "__main__":
    main()
