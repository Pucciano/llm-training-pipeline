#!/usr/bin/env python
"""
Policy-PPO-Trainer; Rewards holt er via REST vom Mac.
"""
import argparse, requests, torch
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from trl import PPOTrainer, PPOConfig

ap = argparse.ArgumentParser()
ap.add_argument("--policy", default="./sft")
ap.add_argument("--prompts", default="./data/prompts_jura.jsonl")
ap.add_argument("--reward-url", default="http://macstudio.local:8008/score")
args = ap.parse_args()

tok = AutoTokenizer.from_pretrained(args.policy, padding_side="left")
tok.pad_token = tok.eos_token
model = AutoModelForCausalLM.from_pretrained(
    args.policy, torch_dtype=torch.float16, device_map={"": "cuda"}
)

def reward(texts):
    r = requests.post(args.reward_url, json={"texts": texts}, timeout=30).json()
    return r["scores"]

prompts = load_dataset("json", data_files=args.prompts, split="train")["text"]

ppo_cfg = PPOConfig(
    learning_rate=1e-6, batch_size=4, mini_batch_size=2, ppo_epochs=4
)
trainer = PPOTrainer(model, tok, **ppo_cfg.__dict__)

for epoch in range(3):
    for q in prompts.shuffle(seed=epoch):
        q_ids = tok(q, return_tensors="pt").input_ids.to("cuda")
        # 2 Kandidaten
        outs = [model.generate(q_ids, max_new_tokens=256, do_sample=True, top_k=50)[0]
                for _ in range(2)]
        texts = [tok.decode(o, skip_special_tokens=True) for o in outs]
        scores = reward(texts)
        best = int(max(range(2), key=lambda i: scores[i]))
        trainer.step([q], [texts[best]], [scores[best]])
    trainer.save_pretrained(f"./ppo_epoch{epoch+1}")
