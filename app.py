import os
import sys

# ---------------------------------
# import 경로 설정
# ---------------------------------
ROOT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.join(ROOT_DIR, "src")
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, SRC_DIR)

import streamlit as st

# 메인에이전트 단일 호출
from src.main_agent.graph import run_workflow

from streamlitUI.ui_sections import (
    render_user_form,
    render_user_profile_summary,
    render_housing_section,
    render_finance_section,
    render_integrated_section
)

from streamlitUI.pdf_report import generate_pdf

st.set_page_config(page_title="청년 미래 설계 에이전트", layout="wide")

st.title("📄 청년 미래 설계 보고서")
st.caption("주거(정책 RAG) + 금융(API) 의견서를 통합해  PDF 보고서를 생성합니다.")

# ---------------------------------
# session_state 초기화
# ---------------------------------
for k in [
    "user_profile",
    "housing_memo",
    "finance_memo",
    "integrated_plan",
    "final_report_markdown",
]:
    if k not in st.session_state:
        st.session_state[k] = None

# ---------------------------------
# 1) 사용자 입력
# ---------------------------------
user_profile = render_user_form()

if user_profile is not None:
    st.session_state["user_profile"] = user_profile

    # 입력 변경 시 기존 결과 무효화
    st.session_state["housing_memo"] = None
    st.session_state["finance_memo"] = None
    st.session_state["integrated_plan"] = None
    st.session_state["roadmap"] = None
    st.session_state["final_report_markdown"] = None

st.divider()

if st.session_state["user_profile"] is None:
    st.warning("사용자 정보를 입력하고 '전체 분석 실행'을 눌러주세요.")
    st.stop()

render_user_profile_summary(st.session_state["user_profile"])

st.divider()

# ---------------------------------
# 2)  단일 실행 버튼 
# ---------------------------------
if st.button("🚀 전체 분석 실행 (주거 + 금융 + 통합)", use_container_width=True):
    with st.spinner("AI가 주거·금융·통합 전략을 생성 중입니다..."):
        result = run_workflow(st.session_state["user_profile"])

        st.session_state["housing_memo"] = result["housing_memo"]
        st.session_state["finance_memo"] = result["finance_memo"]
        st.session_state["integrated_plan"] = result["integrated_plan"]
        st.session_state["final_report_markdown"] = result["final_report_markdown"]

    st.success("전체 분석 완료!")

st.divider()

# ---------------------------------
# 3) 결과 렌더링
# ---------------------------------
if st.session_state["housing_memo"] is not None:
    render_housing_section(st.session_state["housing_memo"])
else:
    st.info("아직 주거 의견서가 없습니다. 전체 분석을 실행하세요.")

st.divider()

if st.session_state["finance_memo"] is not None:
    render_finance_section(st.session_state["finance_memo"])
else:
    st.info("아직 금융 의견서가 없습니다. 전체 분석을 실행하세요.")

st.divider()

if st.session_state["integrated_plan"] is not None:
    render_integrated_section(
    st.session_state["integrated_plan"],
    st.session_state.get("final_report_markdown")
)
else:
    st.info("아직 통합 전략이 없습니다. 전체 분석을 실행하세요.")



st.divider()

# ---------------------------------
# 4) PDF 다운로드
# ---------------------------------
st.subheader("⬇️ PDF 보고서 출력")

pdf_disabled = (
    st.session_state["integrated_plan"] is None
)

if pdf_disabled:
    st.info("PDF는 전체 분석 실행 후 출력할 수 있습니다.")
else:
    pdf_bytes = generate_pdf(
        user_profile=st.session_state["user_profile"],
        housing_memo=st.session_state["housing_memo"],
        finance_memo=st.session_state["finance_memo"],
        integrated_plan=st.session_state["integrated_plan"],
        final_report_markdown=st.session_state.get("final_report_markdown"),
    
    )

    st.download_button(
        label="PDF 다운로드",
        data=pdf_bytes,
        file_name="청년_미래설계_에이전트결과_보고서.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
