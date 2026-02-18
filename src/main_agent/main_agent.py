import os
import operator
from datetime import date, datetime
from typing import Annotated, Dict, List, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from IPython.display import Markdown, display
# from google.colab import files

from dotenv import load_dotenv

load_dotenv()

# 키 보안 관리
api_key = os.environ["OPENAI_API_KEY"]


# --- 전문가 에이전트 로직 ---

def generate_fake_housing_memo(user_profile: dict) -> dict:
    """주거 전문가 에이전트"""
    city = user_profile["region"]["city"]
    gu = user_profile["region"]["gu"]
    return {
        "summary": f"{city} {gu} 지역의 {user_profile['age']}세 청년 맞춤형 주거 정책 분석 결과입니다.",
        "eligible_policies": [
            {"name": "청년 안심주택", "why": "역세권 중심의 우수한 접근성 및 임대료 지원"},
            {"name": "버팀목 전세자금 대출", "why": f"자산 {user_profile['assets_m']}만원 기준 저금리 활용 가능"}
        ],
        "strategy": f"{user_profile['move_timeline']} 내 입주를 위한 공고 모니터링 및 서류 준비",
        "generated_at": str(date.today()),
    }

def generate_fake_finance_memo(user_profile: dict) -> dict:
    """금융 전문가 에이전트"""
    return {
        "summary": f"월 소득 {user_profile['monthly_income_m']}만원 및 {user_profile['risk_pref']} 성향 기반 자산 설계입니다.",
        "recommended_products": [
            {"name": "청년 우대형 청약통장", "why": "비과세 혜택 및 높은 우대 금리 제공"},
            {"name": "비상금 파킹통장", "why": "유동성 확보를 통한 주거 이동 비용 대비"}
        ],
        "asset_strategy": f"월 주거 예산 {user_profile['monthly_housing_budget_m']}만원 이내 지출 최적화 전략",
        "generated_at": str(date.today()),
    }

# --- LangGraph State 설계 ---

class AgentState(TypedDict):
    user_profile: Dict[str, Any]
    housing_analysis: Dict[str, Any]
    financial_analysis: Dict[str, Any]
    final_report_markdown: str
    steps: Annotated[List[str], operator.add]

# --- Workflow 노드 정의 ---

def housing_node(state: AgentState):
    memo = generate_fake_housing_memo(state["user_profile"])
    return {"housing_analysis": memo, "steps": ["주거 분석 완료: 정책 데이터 추출"]}

def finance_node(state: AgentState):
    memo = generate_fake_finance_memo(state["user_profile"])
    return {"financial_analysis": memo, "steps": ["금융 분석 완료: 상품 데이터 추출"]}

def orchestrator_node(state: AgentState):
    """메인 에이전트: 지능형 리포트 제너레이션 및 데이터 바인딩"""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    u = state["user_profile"]
    h = state["housing_analysis"]
    f = state["financial_analysis"]

    # Prompt Engineering
    # 개별 데이터를 직렬화? => Context에 주입
    h_policies = "\n".join([f"- **{p['name']}**: {p['why']}" for p in h["eligible_policies"]])
    f_products = "\n".join([f"- **{p['name']}**: {p['why']}" for p in f["recommended_products"]])

    prompt = ChatPromptTemplate.from_template("""
    너는 청년 주거/금융 통합 컨설팅 전문가야.
    아래 4가지 핵심 섹션 가이드에 따라 사용자 '{name}' 님을 위한 최종 리포트를 Markdown으로 작성해줘.

    ### 1. 전문가별 핵심 분석 요약 (Expert Summary)
    - 주거 전문가 의견: 지역({city}), 나이({age}세), 희망형태({rent_type})를 고려한 분석 결과 요약
    - 금융 전문가 의견: 소득({income}만원), 리스크 성향({risk})을 기반으로 한 자산 방향성 요약
    - 데이터 출처: 주거({h_summary}) 및 금융({f_summary}) 데이터를 직접 인용할 것.

    ### 2. 맞춤형 상세 추천 리스트 (Detailed Recommendations)
    - [주거 정책 추천]
    {h_policies}
    - [금융 상품 추천]
    {f_products}

    ### 3. LLM 통합 분석 및 시너지 제언 (Integrated Insights)
    - 주거 정책 수혜로 절감된 비용을 금융 상품에 재투자했을 때의 시나리오를 구체적으로 제시할 것. (예: 월세 절감액 X원을 적금에 추가 납입 시 5년 후 자산 가치 시뮬레이션)
    - 사용자의 부채({debt}만원)와 자산 형성 간의 균형점에 대한 종합 조언.

    ### 4. 12개월 실행 로드맵 및 체크리스트 (Action Plan)
    - '현재-3개월-6개월-12개월' 단위의 액션 플랜을 마크다운 표 형식으로 작성.
    - 즉시 준비가 필요한 필수 서류(체크리스트) 목록 포함.

    전체적인 톤은 친절하고 전문적이어야 하며, Human-Centric 관점에서 작성해줘.
    """)

    response = llm.invoke(prompt.format(
        name=u["name"],
        city=u["region"]["gu"],
        age=u["age"],
        rent_type=u["rent_type"],
        income=u["monthly_income_m"],
        risk=u["risk_pref"],
        debt=u["debt_m"],
        h_summary=h["summary"],
        f_summary=f["summary"],
        h_policies=h_policies,
        f_products=f_products
    ))

    return {
        "final_report_markdown": response.content,
        "steps": ["메인 에이전트: 4대 섹션 기반 구조적 리포트 생성 완료"]
    }

# --- LangGraph 구축 및 실행 ---

workflow = StateGraph(AgentState)

workflow.add_node("housing", housing_node)
workflow.add_node("finance", finance_node)
workflow.add_node("orchestrator", orchestrator_node)

workflow.add_edge(START, "housing")
workflow.add_edge(START, "finance")
workflow.add_edge("housing", "orchestrator")
workflow.add_edge("finance", "orchestrator")
workflow.add_edge("orchestrator", END)

app = workflow.compile()

streamlit_input = {
    "name": "영진",
    "age": 24,
    "household_type": "청년(1인가구)",
    "region": {"city": "서울특별시", "gu": "광진구"},
    "monthly_income_m": 250,
    "assets_m": 500,
    "debt_m": 0,
    "monthly_housing_budget_m": 60,
    "rent_type": "월세",
    "move_timeline": "1~3개월",
    "risk_pref": "중립",
}

final_result = app.invoke({"user_profile": streamlit_input, "steps": []})

# 최종 결과 & 로그
print("🏠 전문가 협업 및 통합 분석 시스템 가동 결과\n")
display(Markdown(final_result["final_report_markdown"]))

print("\n" + "="*50)
print("시스템 워크플로우 로그")
for i, step in enumerate(final_result["steps"], 1):
    print(f"{i}. {step}")

def download_report(result_state: dict):
    user_name = result_state["user_profile"].get("name", "사용자")
    today_str = datetime.now().strftime("%y%m%d")
    filename = f"{today_str}_{user_name}_주거금융_통합보고서.md"

    # 리포트와 로그 통합
    full_content = result_state["final_report_markdown"]
    full_content += "\n\n" + "="*50 + "\n🤖 시스템 실행 로그\n"
    for i, step in enumerate(result_state["steps"], 1):
        full_content += f"{i}. {step}\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_content)

    # files.download(filename)
    print(f"\n리포트 파일 생성 완료: {filename}")

download_report(final_result)

import matplotlib.pyplot as plt
import matplotlib.patches as patches

# 1. Diagram 1: AgentState Schema
def draw_state_schema():
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_axis_off()

    # State Box
    rect = patches.Rectangle((0.1, 0.1), 0.8, 0.8, linewidth=2, edgecolor='navy', facecolor='#f0f8ff', capstyle='round')
    ax.add_patch(rect)

    plt.text(0.5, 0.82, "class AgentState(TypedDict)", weight='bold', ha='center', fontsize=12)

    fields = [
        "• user_profile: Dict[str, Any] (Input)",
        "• housing_analysis: Dict[str, Any] (Domain Slot)",
        "• financial_analysis: Dict[str, Any] (Domain Slot)",
        "• final_report_markdown: str (Output)",
        "• steps: Annotated[List[str], operator.add] (Reducer)"
    ]

    for i, field in enumerate(fields):
        plt.text(0.15, 0.65 - (i * 0.12), field, fontsize=11, family='monospace')

    plt.title(" AgentState Schema (Single State Management)", weight='bold', pad=20)
    plt.tight_layout()
    plt.savefig('agent_state_schema.png')

draw_state_schema()