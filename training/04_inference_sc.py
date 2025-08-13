#!/usr/bin/env python
"""
Self-Consistency-Decoding; wählt beste Antwort via Reward-Service.
"""
import argparse, torch, requests, random
from transformers import AutoTokenizer, AutoModelForCausalLM

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="./ppo_epoch3")
ap.add_argument("--reward-url", default="http://macstudio.local:8008/score")
ap.add_argument("--device", default="auto", choices=["auto","cuda","mps","cpu"])
ap.add_argument("--n", type=int, default=5, help="Kandidatenzahl")
args = ap.parse_args()

if args.device == "auto":
    dev = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
else:
    dev = args.device

tok = AutoTokenizer.from_pretrained(args.model)
tok.pad_token = tok.eos_token
# bitsandbytes-4bit auf Linux, sonst FP16
model = AutoModelForCausalLM.from_pretrained(
    args.model,
    device_map={"": dev},
    torch_dtype=torch.float16
)

def best_of(prompt):
    in_ids = tok(prompt, return_tensors="pt").input_ids.to(dev)
    outs = [model.generate(in_ids, max_new_tokens=256, do_sample=True, top_k=40,
                           no_repeat_ngram_size=3)[0] for _ in range(args.n)]
    texts = [tok.decode(o, skip_special_tokens=True) for o in outs]
    scores = requests.post(args.reward_url, json={"texts": texts}).json()["scores"]
    return texts[int(max(range(args.n), key=lambda i: scores[i]))]

print("Chat gestartet – Ctrl-C zum Abbruch.")
while True:
    try:
        user = input("» ")
        print(best_of(user))
    except KeyboardInterrupt:
        break
