import json

with open("data/processed/policies.json", "r", encoding="utf-8") as f:
    data = json.load(f)

p = next(x for x in data if x["policy_id"] == "FIN_001")
print(p["raw_text"])