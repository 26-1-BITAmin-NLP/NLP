import requests
import json
import os
from dotenv import load_dotenv

# API KEY 불러오기
load_dotenv()
API_KEY = os.getenv("FINLIFE_API_KEY")

BASE_URL = "http://finlife.fss.or.kr/finlifeapi"

# API 호출
def call_api(endpoint, params):
    URL = BASE_URL + endpoint

    params["auth"] = API_KEY

    response = requests.get(URL, params=params)
    data = response.json()
    print("API 호출 완료")

    return data["result"]


# API 호출로 얻은 원본 데이터 저장
def save_raw_json(data, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("raw data 저장 완료")