import operator
import json
from typing import TypedDict, Annotated, Dict, Any, List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

#  Streamlit이 이미 쓰고 있는 import 호출을 그대로 재사용
from integrations.housing_adapter import run_housing
from finance_agent.main import run_finance

load_dotenv()


# -----------------------------
# LangGraph State 정의
# -----------------------------
class AgentState(TypedDict):
    user_profile: Dict[str, Any]
    housing_memo: Dict[str, Any]
    finance_memo: Dict[str, Any]

    # UI/PDF 호환을 위해 최소 스키마로 유지
    integrated_plan: Dict[str, Any]
    roadmap: List[Dict[str, Any]]

    # 디버깅/추적용
    final_report_markdown: str
    steps: Annotated[List[str], operator.add]


# -----------------------------
# Nodes 변경 사항( subprocess 없음, 전부 import 호출)
# -----------------------------
def housing_node(state: AgentState):
    user_profile = state["user_profile"]
    housing_memo = run_housing(user_profile)
    return {"housing_memo": housing_memo, "steps": ["주거 의견서 생성 완료"]}


def finance_node(state: AgentState):
    # app.py에서 하던 banks -> preferred_banks 매핑을 graph로 이동하도록 함
    profile = state["user_profile"].copy()
    profile["preferred_banks"] = profile.get("banks", [])

    finance_memo = run_finance(profile)
    return {"finance_memo": finance_memo, "steps": ["금융 의견서 생성 완료"]}


def orchestrator_node(state: AgentState):
    print("[Orchestrator Node] 메인에이전트 실행 중...")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

    u = state["user_profile"]
    h = state["housing_memo"]
    f = state["finance_memo"]

    prompt = ChatPromptTemplate.from_template("""
너는 청년 주거 및 금융을 통합하여 컨설팅하는 수석 라이프스타일 어드바이저야.
너의 역할은 청년들의 자산 형성과 주거 안정을 전문적으로 도와주어야 해.
사용자의 프로필과 두 AI 에이전트가 분석한 데이터를 바탕으로 최고 수준의 통합 리포트를 작성해줘.

반드시 아래 출력 형식을 지켜라.
1) Markdown 리포트
2) 구조화 JSON (integrated_plan + roadmap)

다른 텍스트는 절대 추가하지 말 것.

====================
===MARKDOWN===
(여기에 Markdown 리포트 작성)

====================
===JSON===
{{
  "integrated_plan": {{
    "integrated_summary": "통합 전략 요약",
    "conflicts_and_resolutions": [
      {{
        "issue": "충돌 또는 리스크",
        "resolution": "해결 방안",
        "why_it_matters": "왜 중요한지"
      }}
    ],
    "checklist": [
      {{
        "item": "해야 할 행동",
        "deadline": "1개월 이내 / 3개월 이내 등",
        "notes": "주의사항"
      }}
    ]
  }},
  "roadmap": [
    {{
      "month": 1,
      "actions": ["행동1", "행동2"],
      "documents": ["필요서류1", "필요서류2"],
      "expected_outcome": "기대효과"
    }}
  ]
}}

====================

이제 아래 정보를 기반으로 작성해라.

[사용자 프로필]
{user_data}

[주거 에이전트 분석 결과]
{h_data}

[금융 에이전트 분석 결과]
{f_data}

리포트는 가독성 좋은 Markdown으로 작성하고, 반드시 다음 4개 섹션을 포함해야 해:

    1. 현재 재무 및 주거 상황 진단
    - 리포트 최상단에 반드시 다음 양식을 지켜 [사용자 프로필] 요약을 명시할 것:
      * 연령 / 성별:
      * 월 소득 / 자산 / 부채:
      * 희망 거주 지역:
      * 희망 주거 형태 및 예산:
      * 자주 쓰는 은행:
    - 위 프로필을 바탕으로 현재 상황을 객관적으로 분석
    - 앞으로 3년~5년 내에 달성할 수 있는 현실적이고 명확한 재무/주거 목표 제시

    2. 주거-금융 시너지 자산 형성 시뮬레이션 (핵심)
    - [주거비 절감액 추산]: 추천된 주거 정책(예: 주거급여, 청년전월세보증금 대출 등)을 활용했을 때 매월 절약할 수 있는 '예상 주거비 절감액'을 구체적인 수치로 계산
    - [투자 시너지]: 절약한 주거비와 기존 여유 자금을 추천된 금융 상품(고금리 적금 등)에 납입했을 때의 효과를 분석
    - [3년/5년 미래 자산 예측]: 위 전략을 꾸준히 실행했을 때 예상되는 미래 자산 규모를 시뮬레이션하여 수치로 시각화 (예: "매월 절감액 X원을 Y상품에 Z% 금리로 납입 시 3년 뒤 예상 모은 돈 OOO만 원")

    3. 맞춤형 액션 플랜 및 핵심 추천 가이드
    - 주거 정책: 가장 추천하는 정책의 신청 이유, 기대 혜택, 신청 자격 유지 조건.
    - 금융 상품: 추천 금융 상품의 선택 이유, 우대금리(최고 금리)를 100% 달성하기 위한 구체적인 팁.

    4. 12개월 밀착 실행 로드맵 & 필수 준비 서류
    - 당장 1개월 차부터 12개월 차까지 달마다 무엇을 해야 하는지(예: 1개월 차-서류 준비 및 정책 신청, 2개월 차-특정 적금 가입 등) 구체적인 행동 로드맵을 표 형식으로 작성
    - 주민센터나 은행 방문 시 챙겨야 할 필수 서류(가족관계증명서, 임대차계약서, 소득증빙 등) 체크리스트를 제공

    5. 리스크 관리 조언
    - 신용점수 관리법, 향후 소득 증가 시 주거 정책 수급 자격 박탈 위험 등 청년이 놓치기 쉬운 리스크를 관리하는 실질적인 팁을 작성
    """)


    response = llm.invoke(
        prompt.format(
            user_data=json.dumps(u, ensure_ascii=False),
            h_data=json.dumps(h, ensure_ascii=False),
            f_data=json.dumps(f, ensure_ascii=False),
        )
    )

    text = response.content.strip()

    # -------------------------
    # Markdown / JSON 분리
    # -------------------------
    md = ""
    payload = {}

    try:
        md_start = text.index("===MARKDOWN===") + len("===MARKDOWN===")
        json_start = text.index("===JSON===")

        md = text[md_start:json_start].strip()
        json_str = text[json_start + len("===JSON==="):].strip()

        payload = json.loads(json_str)

    except Exception as e:
        md = text
        payload = {
            "integrated_plan": {
                "integrated_summary": "JSON 파싱 실패",
                "conflicts_and_resolutions": [],
                "checklist": []
            },
            "roadmap": [],
            "error": str(e)
        }

    integrated_plan = payload.get("integrated_plan", {})
    roadmap = payload.get("roadmap", [])

    return {
        "final_report_markdown": md,
        "integrated_plan": integrated_plan,
        "roadmap": roadmap,
        "steps": ["LLM 통합 전략 생성 완료"]
    }
    md = response.content

    # UI/PDF 호환 최소 스키마
    integrated_plan = {
        "integrated_summary": md,                 # ui_sections / pdf_report가 사용 
        "conflicts_and_resolutions": [],          # expander에서 loop
        "checklist": [],                          # expander에서 loop
    }

    roadmap: List[Dict[str, Any]] = []            

    return {
        "final_report_markdown": md,
        "integrated_plan": integrated_plan,
        "roadmap": roadmap,
        "steps": ["통합 리포트(Markdown) 생성 완료"],
    }


# -----------------------------
# Graph 구성
# -----------------------------
workflow = StateGraph(AgentState)

workflow.add_node("housing", housing_node)
workflow.add_node("finance", finance_node)
workflow.add_node("orchestrator", orchestrator_node)

# START -> (housing, finance 병렬) -> orchestrator -> END
workflow.add_edge(START, "housing")
workflow.add_edge(START, "finance")
workflow.add_edge("housing", "orchestrator")
workflow.add_edge("finance", "orchestrator")
workflow.add_edge("orchestrator", END)

app = workflow.compile()


# -----------------------------
#  단일 호출 엔트리
# -----------------------------
def run_workflow(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    initial_state: Dict[str, Any] = {
        "user_profile": user_profile,
        "steps": [],
    }
    result = app.invoke(initial_state)

    # app.py / pdf_report.py가 기대하는 키로 반환하는 부분
    return {
        "housing_memo": result.get("housing_memo"),
        "finance_memo": result.get("finance_memo"),
        "integrated_plan": result.get("integrated_plan"),
        "roadmap": result.get("roadmap"),
        "final_report_markdown": result.get("final_report_markdown"),
        "steps": result.get("steps", []),
    }