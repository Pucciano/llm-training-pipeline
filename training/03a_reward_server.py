#!/usr/bin/env python
"""
Startet einen FastAPI-Reward-Service auf dem Mac (MPS).
"""
from fastapi import FastAPI
import uvicorn, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline

RM_PATH = "./reward_de_legal"  # DeBERTa-Large, deutsch feinjustiert
tok = AutoTokenizer.from_pretrained(RM_PATH)
rm_model = AutoModelForSequenceClassification.from_pretrained(
    RM_PATH, torch_dtype=torch.float16, device_map="mps"
)
clf = pipeline("text-classification", model=rm_model, tokenizer=tok, device="mps")

app = FastAPI()
@app.post("/score")
def score(payload: dict):
    scores = [o["score"] for o in clf(payload["texts"], truncation=True, max_length=1024)]
    return {"scores": scores}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8008)
