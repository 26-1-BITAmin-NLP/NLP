import streamlit as st

from ui_sections import (
    render_user_form,
    render_user_profile_summary,
    render_housing_section,
    render_finance_section,
    render_integrated_section,
    render_roadmap,
)
from stub_data import (
    generate_fake_housing_memo,
    generate_fake_finance_memo,
    generate_fake_integrated_plan,
    generate_fake_roadmap,
)
from pdf_report import generate_pdf

st.set_page_config(page_title="청년 미래 설계 에이전트", layout="wide")

st.title("📄 청년 미래 설계 보고서")
st.caption("주거(정책 RAG) + 금융(API) 의견서를 통합해 로드맵과 PDF 보고서를 생성합니다.")

# -----------------------
# session_state init
# -----------------------
for k in ["user_profile", "housing_memo", "finance_memo", "integrated_plan", "roadmap"]:
    if k not in st.session_state:
        st.session_state[k] = None

# -----------------------
# 1) User input
# -----------------------
user_profile = render_user_form()
if user_profile is not None:
    st.session_state["user_profile"] = user_profile
    # 입력이 바뀌면 이후 산출물은 무효화(혼동 방지)
    st.session_state["housing_memo"] = None
    st.session_state["finance_memo"] = None
    st.session_state["integrated_plan"] = None
    st.session_state["roadmap"] = None

st.divider()

if st.session_state["user_profile"] is None:
    st.warning("사용자 정보를 입력하고 '분석 시작'을 눌러주세요.")
    st.stop()

render_user_profile_summary(st.session_state["user_profile"])

st.divider()

# -----------------------
# 2) Stub generation buttons
# -----------------------
colA, colB, colC = st.columns(3)

with colA:
    if st.button("🏠주거 의견서 생성(가짜)", use_container_width=True):
        st.session_state["housing_memo"] = generate_fake_housing_memo(st.session_state["user_profile"])
        st.session_state["integrated_plan"] = None
        st.session_state["roadmap"] = None

with colB:
    if st.button("💰 금융 의견서 생성(가짜)", use_container_width=True):
        st.session_state["finance_memo"] = generate_fake_finance_memo(st.session_state["user_profile"])
        st.session_state["integrated_plan"] = None
        st.session_state["roadmap"] = None

with colC:
    can_integrate = (st.session_state["housing_memo"] is not None) and (st.session_state["finance_memo"] is not None)
    if st.button("🧩 통합 전략 생성(가짜)", use_container_width=True, disabled=not can_integrate):
        st.session_state["integrated_plan"] = generate_fake_integrated_plan(
            st.session_state["user_profile"],
            st.session_state["housing_memo"],
            st.session_state["finance_memo"],
        )
        st.session_state["roadmap"] = generate_fake_roadmap(
            st.session_state["user_profile"],
            st.session_state["housing_memo"],
            st.session_state["finance_memo"],
        )

st.divider()

# -----------------------
# 3) Render sections
# -----------------------
if st.session_state["housing_memo"] is not None:
    render_housing_section(st.session_state["housing_memo"])
else:
    st.info("주거 의견서가 아직 없습니다. '주거 의견서 생성(가짜)'를 눌러주세요.")

st.divider()

if st.session_state["finance_memo"] is not None:
    render_finance_section(st.session_state["finance_memo"])
else:
    st.info("금융 의견서가 아직 없습니다. '금융 의견서 생성(가짜)'를 눌러주세요.")

st.divider()

if st.session_state["integrated_plan"] is not None:
    render_integrated_section(st.session_state["integrated_plan"])
else:
    st.info("통합 전략이 아직 없습니다. 주거/금융 의견서를 만든 뒤 '통합 전략 생성(가짜)'를 눌러주세요.")

st.divider()

if st.session_state["roadmap"] is not None:
    render_roadmap(st.session_state["roadmap"])
else:
    st.info("로드맵이 아직 없습니다. 통합 전략을 생성하면 함께 만들어집니다.")

st.divider()

# -----------------------
# 4) PDF Download
# -----------------------
st.subheader("⬇️ PDF 보고서 출력")

pdf_disabled = st.session_state["integrated_plan"] is None or st.session_state["roadmap"] is None

if pdf_disabled:
    st.info("PDF는 통합 전략 + 로드맵 생성 후 출력할 수 있습니다.")
else:
    pdf_bytes = generate_pdf(
        user_profile=st.session_state["user_profile"],
        housing_memo=st.session_state["housing_memo"],
        finance_memo=st.session_state["finance_memo"],
        integrated_plan=st.session_state["integrated_plan"],
        roadmap=st.session_state["roadmap"],
    )

    st.download_button(
        label="PDF 다운로드",
        data=pdf_bytes,
        file_name="청년_미래설계_에이전트결과_보고서.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
