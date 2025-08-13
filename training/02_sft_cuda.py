#!/usr/bin/env python
"""
LoRA-SFT für Alpaca-ähnliche Jura-Anweisungen.
"""
import argparse, torch, json
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="./pretrained")
ap.add_argument("--data", default="./data/alpaca_jura.jsonl")
ap.add_argument("--device", default="cuda")
args = ap.parse_args()

tok = AutoTokenizer.from_pretrained(args.base)
tok.pad_token = tok.eos_token

def prompt(ex):
    text = f"### Anweisung:\n{ex['instruction']}\n### Kontext:\n{ex['input']}\n### Antwort:\n{ex['output']}"
    return tok(text, truncation=True, max_length=1024)

ds = load_dataset("json", data_files=args.data, split="train").map(prompt, remove_columns=["instruction","input","output"])

model = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=torch.float16, device_map={"":args.device})
lora = LoraConfig(r=8, alpha=32, dropout=0.05, target_modules=["q_proj","v_proj"])
model = get_peft_model(model, lora)

targs = TrainingArguments(
    output_dir="./sft",
    per_device_train_batch_size=4,
    gradient_accumulation_steps=2,
    num_train_epochs=3,
    fp16=True,
    learning_rate=2e-5,
    logging_steps=25,
    save_strategy="epoch"
)
Trainer(model=model, args=targs, train_dataset=ds).train()
model.save_pretrained("./sft")
