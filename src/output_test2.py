import json

path = "data/processed/policies_chunking.jsonl"
with open(path, encoding="utf-8") as f:
    chunks = [json.loads(line) for line in f]

# 정책 출력 확인
pid = "FIN_001"
items = sorted([c for c in chunks if c["policy_id"] == pid], key=lambda x: x["chunk_id"])

for c in items[:8]:
    print("="*60)
    print(c["chunk_id"], c["section"])
    print(c["text"][:400])