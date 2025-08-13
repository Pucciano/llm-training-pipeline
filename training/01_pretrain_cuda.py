#!/usr/bin/env python
"""
Continued-Pre-Training oder From-Scratch-Training auf CUDA.
Der gesamte Korpus liegt auf NFS/Samba/… und wird gestreamt.
"""
import argparse, math, os
from datasets import load_dataset, interleave_datasets
import torch, transformers
from transformers import (
    GPTNeoXConfig, GPTNeoXForCausalLM,
    AutoTokenizer, TrainingArguments, Trainer,
    DataCollatorForLanguageModeling
)

parser = argparse.ArgumentParser()
parser.add_argument("--tokenizer", default="tokenizer_de_jura.json")
parser.add_argument("--model-size", default="1b", choices=["350m","1b"])
parser.add_argument("--seq-len", type=int, default=1024)
parser.add_argument("--epochs", type=int, default=1)
parser.add_argument("--device", default="auto", choices=["auto","cuda","cpu"])
args = parser.parse_args()

# ----- Device auswählen -----
if args.device == "auto":
    dev = "cuda" if torch.cuda.is_available() else "cpu"
else:
    dev = args.device
torch_device = torch.device(dev)
print("Gerät:", torch_device)

# ----- Tokenizer laden -----
tok = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=False)
tok.pad_token = tok.eos_token

# ----- Modellkonfiguration -----
cfgs = {
    "350m": dict(hidden_size=2048, num_layers=20, num_attention_heads=16),
    "1b":   dict(hidden_size=3072, num_layers=24, num_attention_heads=24),
}
cfg = GPTNeoXConfig(
    vocab_size=tok.vocab_size,
    intermediate_size=cfgs[args.model_size]["hidden_size"]*4,
    **cfgs[args.model_size],
    max_position_embeddings=args.seq_len,
    rotary_pct=1.0,
)

model = GPTNeoXForCausalLM(cfg).to(torch_device)
model.gradient_checkpointing_enable()

# ----- Datenstream (OSCAR-de + BGBl u. a.) -----
ds_web  = load_dataset("oscar", "unshuffled_deduplicated_de", split="train", streaming=True)
ds_ol   = load_dataset("openlegaldata/old_cases_de", split="train", streaming=True)
def tok_map(b): return tok(b["text"], truncation=True, max_length=args.seq_len)
ds = interleave_datasets([ds_web, ds_ol]).map(tok_map)

# ----- Training -----
collator = DataCollatorForLanguageModeling(tok, mlm=False)
targs = TrainingArguments(
    output_dir="./pretrained",
    num_train_epochs=args.epochs,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    fp16=True,
    learning_rate=3e-4,
    warmup_ratio=0.03,
    logging_steps=50,
    report_to="none",
)
Trainer(model, targs, train_dataset=ds, data_collator=collator).train()
model.save_pretrained("./pretrained")
tok.save_pretrained("./pretrained")
