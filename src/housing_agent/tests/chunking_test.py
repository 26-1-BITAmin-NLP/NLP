import json, statistics

path = "data/processed/policies_chunking.jsonl"
with open(path, encoding="utf-8") as f:
    chunks = [json.loads(line) for line in f]

lens = [len(c["text"]) for c in chunks]
print("chunks:", len(chunks))
print("min/median/mean/max:", min(lens), statistics.median(lens), round(statistics.mean(lens)), max(lens))

from collections import Counter

cnt = Counter(c["policy_id"] for c in chunks)
print(cnt.most_common(10))
