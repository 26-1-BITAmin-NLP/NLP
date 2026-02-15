import os
from openai import OpenAI
from dotenv import load_dotenv

# API KEY 불러오기
load_dotenv()
API_KEY = os.getenv("OPEN_API_KEY")

# llm 활용 의견서 생성
def generate_report(products, user_condition):
    client = OpenAI()

    prompt = f"""
사용자 조건: {user_condition}

추천 상품: {products}

이 상품들을 비교해서 금융 전략 의견서를 작성해주세요.

형식:
1. 사용자 금융 상황 요약
2. 추천 상품 TOP 3개 선정해 비교
3. 각 상품별 추천 이유와 활용 방안
4. 최종 결론
"""
    
    response = client.chat.completions.create(
        model = "gpt-4o-mini",
        messages = [{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content