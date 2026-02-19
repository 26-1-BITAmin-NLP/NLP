# 주거 전문가 의견서 생성 코드

"""
retriever 결과를 바탕으로 주거 전문가 의견서 JSON 생성

흐름
- user_profile(폼 입력) + 옵션 읽음
- 내부 질의(query)를 만들고 retriever 호출
- 검색 근거를 GPT 프롬프트에 넣어 의견서 생성
- 스키마 정규화/보정 후 UI에서 사용할 JSON 출력
"""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from src.housing_agent.pipeline.retriever import (
    DEFAULT_CHUNK_PATH,
    DEFAULT_INDEX_LOG_PATH,
    DEFAULT_INDEX_PATH,
    DEFAULT_MAPPING_PATH,
    DEFAULT_METADATA_PATH,
    DEFAULT_SECTION_WEIGHTS,
    run_retrieval,
)


ROOT = Path(__file__).resolve().parents[3]

# gpt에게 요청하는 프롬프트
SYSTEM_PROMPT = """너는 청년 주거 정책 상담 어시스턴트다.
검색 근거에 기반한 주거 의견서(JSON)만 생성한다.
근거에 없는 사실을 단정하지 않는다.
반드시 지정된 JSON 스키마로만 출력한다.
"""

def parse_args() -> argparse.Namespace:

    """
    - 폼 입력값(user_profile)을 직접 받을 수 있도록 함
    - 필요하면 파일(user_profile_path)로 일괄 주입 가능
    - retriever/생성 모델 옵션 분리
    """

    parser = argparse.ArgumentParser(description="Retriever + GPT-4o mini 주거 의견서 생성")
    parser.add_argument("--query", type=str, default="", help="사용자 요청 문장(미입력 시 프로필 기반 자동 생성)")
    parser.add_argument("--top-k", type=int, default=5, help="retriever 최종 반환 개수")
    parser.add_argument("--search-k", type=int, default=0, help="retriever 1차 검색 개수")

    # ui_sections과 폼 입력 변수 통일
    parser.add_argument("--user-profile-path", type=Path, default=None, help="폼 입력 user_profile json 파일 경로")
    parser.add_argument("--age", type=int, default=-1, help="나이")
    parser.add_argument("--household-type", type=str, default="", help="가구 유형")
    parser.add_argument("--region-city", type=str, default="", help="거주 희망 시/도")
    parser.add_argument("--region-gu", type=str, default="", help="거주 희망 시/군/구")
    parser.add_argument("--monthly-income-m", type=int, default=-1, help="월 소득(만원)")
    parser.add_argument("--assets-m", type=int, default=-1, help="보유 자산(만원)")
    parser.add_argument("--debt-m", type=int, default=-1, help="부채(만원, 미입력은 -1)")
    parser.add_argument("--monthly-housing-budget-m", type=int, default=-1, help="월 주거 예산(만원)")
    parser.add_argument("--rent-type", type=str, default="", help="주거 형태 선호")
    parser.add_argument("--move-timeline", type=str, default="", help="입주 희망 시점")
    parser.add_argument("--risk-pref", type=str, default="", help="리스크 성향(선택)")
    parser.add_argument("--banks", type=str, default="", help="자주 쓰는 은행(쉼표 구분)")

    # retriever 경로/옵션
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH, help="FAISS 인덱스")
    parser.add_argument("--index-log", type=Path, default=DEFAULT_INDEX_LOG_PATH, help="인덱스 로그")
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING_PATH, help="벡터 매핑 jsonl")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNK_PATH, help="원본 청크 jsonl")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH, help="정책 metadata json")
    parser.add_argument("--section-weights", type=str, default=DEFAULT_SECTION_WEIGHTS, help="섹션 기본 가중치")
    parser.add_argument("--disable-dynamic-section-weight", action="store_true", help="동적 섹션 가중치 비활성화")
    parser.add_argument("--disable-dynamic-category-weight", action="store_true", help="동적 카테고리 가중치 비활성화")
    parser.add_argument("--disable-text-dedup", action="store_true", help="텍스트 dedup 비활성화")
    parser.add_argument("--text-dedup-min-len", type=int, default=80, help="텍스트 dedup 최소 길이")
    parser.add_argument("--preview-chars", type=int, default=300, help="retriever 미리보기 길이")
    parser.add_argument("--query-model", type=str, default="", help="질의 임베딩 모델(기본: index log)")

    # 생성 모델 옵션
    parser.add_argument("--chat-model", type=str, default="gpt-4o-mini", help="생성 모델")
    parser.add_argument("--temperature", type=float, default=0.2, help="생성 temperature")
    parser.add_argument("--api-key-env", type=str, default="OPENAI_API_KEY", help="API 키 환경변수명")
    parser.add_argument("--debug-verbose", action="store_true", help="retriever 원문(text 포함)까지 출력")
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    return parser.parse_args()


def load_source_map(path: Path) -> Dict[str, str]:

    # evidence.source에 원문 URL을 덧붙임, UI에서 정책 원문으로 이동할 수 있게 함
    
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out: Dict[str, str] = {}
    for policy_id, meta in raw.items():
        url = ((meta or {}).get("source_url") or "").strip()
        if url:
            out[str(policy_id)] = url
    return out


def _none_if_empty(s: str) -> Any:
    return s.strip() if isinstance(s, str) and s.strip() else None


def _none_if_neg(n: int) -> Any:
    return None if n is None or n < 0 else int(n)


def load_user_profile(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        profile = json.load(f)
    if not isinstance(profile, dict):
        raise ValueError(f"user_profile json 형식이 dict가 아닙니다: {path}")
    return profile


def build_profile(args: argparse.Namespace) -> Dict[str, Any]:

    # CLI 입력값으로 기본 프로필 생성
    profile: Dict[str, Any] = {
        "age": _none_if_neg(args.age),
        "household_type": _none_if_empty(args.household_type),
        "region": {
            "city": _none_if_empty(args.region_city),
            "gu": _none_if_empty(args.region_gu),
        },
        "monthly_income_m": _none_if_neg(args.monthly_income_m),
        "assets_m": _none_if_neg(args.assets_m),
        "debt_m": _none_if_neg(args.debt_m),
        "monthly_housing_budget_m": _none_if_neg(args.monthly_housing_budget_m),
        "rent_type": _none_if_empty(args.rent_type),
        "move_timeline": _none_if_empty(args.move_timeline),
        "risk_pref": _none_if_empty(args.risk_pref),
        "banks": [x.strip() for x in args.banks.split(",") if x.strip()],
    }

    # user_profile 파일이 주어지면 해당 값 우선 적용
    if args.user_profile_path is not None:
        if not args.user_profile_path.exists():
            raise FileNotFoundError(f"user_profile 파일이 없습니다: {args.user_profile_path}")
        loaded = load_user_profile(args.user_profile_path)
        profile.update({k: v for k, v in loaded.items() if k != "region"})
        if isinstance(loaded.get("region"), dict):
            profile["region"] = {
                "city": loaded["region"].get("city"),
                "gu": loaded["region"].get("gu"),
            }

    # None/누락 정리 (후속 단계에서 key 존재 여부 체크하기 위함)
    profile.setdefault("region", {"city": None, "gu": None})
    if profile.get("banks") is None:
        profile["banks"] = []
    return profile


def build_auto_query(profile: Dict[str, Any]) -> str:

    # 폼 입력 기반 내부 질의 자동 생성
    # 사용자에게 query를 따로 받지 않아도 retriever가 검색 가능한 문장으로 변환

    parts: List[str] = []

    age = profile.get("age")
    if isinstance(age, int) and age > 0:
        parts.append(f"{age}세")

    region = profile.get("region") or {}
    city = str(region.get("city") or "").strip()
    gu = str(region.get("gu") or "").strip()
    if city and gu:
        parts.append(f"{city} {gu} 거주 희망")
    elif city:
        parts.append(f"{city} 거주 희망")

    household_type = str(profile.get("household_type") or "").strip()
    if household_type:
        parts.append(household_type)

    rent_type = str(profile.get("rent_type") or "").strip()
    if rent_type and rent_type != "상관없음":
        parts.append(f"{rent_type} 중심")

    move_timeline = str(profile.get("move_timeline") or "").strip()
    if move_timeline:
        parts.append(f"입주 시점 {move_timeline}")

    income = profile.get("monthly_income_m")
    if isinstance(income, int) and income >= 0:
        parts.append(f"월소득 {income}만원")

    budget = profile.get("monthly_housing_budget_m")
    if isinstance(budget, int) and budget >= 0:
        parts.append(f"월 주거예산 {budget}만원")

    prefix = " ".join(parts).strip()
    if not prefix:
        return "청년 주거 지원 정책 추천"
    return f"{prefix} 조건에 맞는 청년 주거 지원 정책 추천"


def build_context_text(results: List[Dict[str, Any]], source_map: Dict[str, str], text_limit: int = 900) -> str:

    """
    GPT에 전달할 검색 근거 텍스트 블록 생성

    각 청크마다 policy_id/chunk_id/section/score/source_url을 함께 넣어
    모델이 근거 출처를 명시하면서 답변하도록 유도
    """

    lines: List[str] = []
    for i, row in enumerate(results, start=1):
        text = str(row.get("text", "")).strip()
        if len(text) > text_limit:
            text = text[:text_limit].rstrip() + " ..."
        policy_id = str(row.get("policy_id") or "")
        source_url = source_map.get(policy_id, "")
        lines.append(
            f"[{i}] policy_id={policy_id} chunk_id={row.get('chunk_id')} "
            f"section={row.get('section')} score={row.get('score')} rank={row.get('rank_score')}"
        )
        if source_url:
            lines.append(f"source_url={source_url}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip()


def build_user_prompt(query: str, profile: Dict[str, Any], context_text: str) -> str:

    """
    생성 모델에 전달할 user 프롬프트 본문 구성

    원칙
    - 스키마 고정(변수명 유지)
    - 내용 풍부(요건/혜택/주의/실행전략)
    - 검색 근거 밖 추론 금지
    """

    profile_json = json.dumps(profile, ensure_ascii=False, indent=2)
    return f"""[사용자 요청]
{query}

[사용자 프로필]
{profile_json}

[검색 근거 청크]
{context_text}

[출력 스키마 (JSON)]
{{
  "summary": "string",
  "eligible_policies": [
    {{
      "name": "string",
      "why": "string",
      "benefit": "string",
      "caution": "string"
    }}
  ],
  "strategy": "string",
  "evidence": [
    {{
      "source": "policy_id/chunk_id/source_url 등",
      "snippet": "근거 요약"
    }}
  ],
  "generated_at": "YYYY-MM-DD"
}}

규칙
- eligible_policies는 최대 3개
- summary는 3~5문장으로 작성하고, 사용자 조건(나이/지역/예산/주거형태)을 반영
- 각 정책의 why/benefit/caution은 각각 최소 4~5줄(줄바꿈 포함)로 작성
- 각 정책의 why는 '왜 이 사용자에게 맞는지'를 나이/지역/소득/가구유형 기준으로 명시
- benefit은 지원 형태와 기대 효과를 구체적으로 작성(금액/비율/임대료 수준 등 근거가 있으면 포함)
- caution은 제외 조건, 신청 시기/서류/중복수혜 이슈를 구체적으로 작성
- strategy는 실행 순서(지금/1개월/3개월) + 우선순위 이유 포함
- evidence는 검색 근거에서만 작성하고, 최소 2개 이상 포함
- evidence.snippet은 1~2문장으로 쓰고 과도한 원문 복붙 금지
- JSON 외 다른 텍스트 출력 금지
""".strip()


def extract_json_object(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("빈 응답")
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError("JSON 객체를 찾지 못했습니다.")
    obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("JSON 객체 형식이 아닙니다.")
    return obj


def build_default_memo(results: List[Dict[str, Any]], source_map: Dict[str, str], query: str) -> Dict[str, Any]:

    # 모델 응답 실패 시 사용하는 fallback 의견서
    # 서비스가 중단되지 않도록 최소한의 구조화된 결과 항시 반환
    
    eligible: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()
    for row in results:
        title = str(row.get("title") or "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        eligible.append(
            {
                "name": title,
                "why": "\n".join(
                    [
                        "- 검색 질의와 유사도가 높아 현재 조건과의 적합성이 높습니다.",
                        "- 나이/지역/주거형태 등 핵심 조건에서 우선 검토할 가치가 있습니다.",
                        "- 실제 자격요건 충족 여부를 확인하면 신청 가능성을 빠르게 판단할 수 있습니다.",
                        "- 동일 목적의 대안 정책과 비교했을 때 초기 검토 우선순위가 높습니다.",
                    ]
                ),
                "benefit": "\n".join(
                    [
                        "- 지원 요건 충족 시 월 주거비 또는 초기 주거비 부담 완화에 도움이 됩니다.",
                        "- 정책별로 임대료 경감, 보증금/금융지원, 현금성 지원 등 효과를 기대할 수 있습니다.",
                        "- 단기적으로는 지출 안정화, 중기적으로는 주거 안정성 확보에 기여할 수 있습니다.",
                        "- 다른 제도와 병행 가능 여부를 확인하면 체감 혜택을 더 키울 수 있습니다.",
                    ]
                ),
                "caution": "\n".join(
                    [
                        "- 소득/자산/무주택/연령 등 세부 기준 미충족 시 제외될 수 있습니다.",
                        "- 모집 공고 시기와 신청 기간이 짧을 수 있어 일정 확인이 필요합니다.",
                        "- 제출 서류(주민등록, 소득증빙, 가족관계 등) 준비가 지연되면 탈락 위험이 있습니다.",
                        "- 중복수혜 제한, 지역 제한, 거주요건은 반드시 원문 공고로 재확인해야 합니다.",
                    ]
                ),
            }
        )
        if len(eligible) >= 3:
            break

    evidence: List[Dict[str, str]] = []
    for row in results[:5]:
        pid = str(row.get("policy_id") or "")
        cid = str(row.get("chunk_id") or "")
        source_url = source_map.get(pid, "")
        snippet = str(row.get("text_preview") or "").strip()
        source = f"{pid}/{cid}" + (f"/{source_url}" if source_url else "")
        evidence.append({"source": source, "snippet": snippet})

    return {
        "summary": f"요청 질의('{query}') 기준으로 신청 가능성이 높은 정책을 우선 정리했습니다.",
        "eligible_policies": eligible,
        "strategy": "1) 자격요건 확인 2) 서류 준비 3) 신청기간 내 접수 순으로 진행하세요.",
        "evidence": evidence,
        "generated_at": str(date.today()),
    }


def normalize_housing_memo(memo: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    # 주거 의견서 포맷 통일
    out = dict(fallback)
    if isinstance(memo, dict):
        out.update({k: v for k, v in memo.items() if k in out})

    if not isinstance(out.get("eligible_policies"), list):
        out["eligible_policies"] = fallback["eligible_policies"]
    else:
        fixed: List[Dict[str, Any]] = []
        for idx, row in enumerate(out["eligible_policies"][:3]):
            if not isinstance(row, dict):
                continue
            fallback_row = {}
            if isinstance(fallback.get("eligible_policies"), list) and idx < len(fallback["eligible_policies"]):
                candidate = fallback["eligible_policies"][idx]
                if isinstance(candidate, dict):
                    fallback_row = candidate

            why = str(row.get("why") or "").strip() or str(fallback_row.get("why") or "").strip()
            benefit = str(row.get("benefit") or "").strip() or str(fallback_row.get("benefit") or "").strip()
            caution = str(row.get("caution") or "").strip() or str(fallback_row.get("caution") or "").strip()

            # 생성 품질이 낮아 단문으로 들어오면 최소 4줄 형태로 보강
            why = ensure_min_lines(why, min_lines=4)
            benefit = ensure_min_lines(benefit, min_lines=4)
            caution = ensure_min_lines(caution, min_lines=4)

            fixed.append(
                {
                    "name": str(row.get("name") or "").strip(),
                    "why": why,
                    "benefit": benefit,
                    "caution": caution,
                }
            )
        out["eligible_policies"] = fixed if fixed else fallback["eligible_policies"]

    if not isinstance(out.get("evidence"), list):
        out["evidence"] = fallback["evidence"]
    out["generated_at"] = str(date.today())
    return out


def ensure_min_lines(text: str, min_lines: int = 4) -> str:
    
    # 문장 수가 부족하면 최소 줄 수에 맞도록 확장

    raw = str(text or "").strip()
    if not raw:
        return raw

    lines = [ln.strip(" -\t") for ln in raw.splitlines() if ln.strip()]
    if len(lines) >= min_lines:
        return "\n".join([f"- {ln}" for ln in lines])

    normalized = raw.replace("?", ". ").replace("!", ". ")
    pieces = [p.strip() for p in normalized.split(".") if p.strip()]
    if not pieces:
        pieces = [raw]

    out_lines: List[str] = []
    for p in pieces:
        out_lines.append(p if p.endswith(".") else f"{p}.")
        if len(out_lines) >= min_lines:
            break

    while len(out_lines) < min_lines:
        if len(out_lines) == 1:
            out_lines.append("자격 기준과 지역 조건을 원문 공고에서 함께 확인하세요.")
        elif len(out_lines) == 2:
            out_lines.append("신청 기간과 제출 서류를 미리 준비하면 실제 신청 성공률을 높일 수 있습니다.")
        else:
            out_lines.append("중복수혜 제한과 예외 조건을 사전에 점검해야 누락을 줄일 수 있습니다.")

    return "\n".join([f"- {ln}" for ln in out_lines[:min_lines]])


def _extract_policy_id_from_source(source: str) -> str:
    s = str(source or "").strip()
    if not s:
        return ""

    if "/" in s:
        first = s.split("/", 1)[0]
        if first:
            return first.split("#", 1)[0]
    return s.split("#", 1)[0]


def attach_source_url_to_evidence(housing_memo: Dict[str, Any], source_map: Dict[str, str]) -> Dict[str, Any]:

    # evidence.source에 source_url 포함
    # UI에서 근거 클릭 -> 원문 이동 가능하도록
    
    ev = housing_memo.get("evidence")
    if not isinstance(ev, list):
        return housing_memo
    fixed: List[Dict[str, Any]] = []
    for row in ev:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "").strip()
        pid = _extract_policy_id_from_source(source)
        url = source_map.get(pid, "")
        if url and url not in source:
            if source:
                source = f"{source}/{url}"
            else:
                source = url
        fixed.append(
            {
                "source": source,
                "snippet": str(row.get("snippet") or "").strip(),
            }
        )
    housing_memo["evidence"] = fixed
    return housing_memo

# json 출력 시 디버깅 최소 요약 (main_agent에 같이 전달)
def build_retrieval_summary(results: List[Dict[str, Any]], retrieval_debug: Dict[str, Any], source_map: Dict[str, str]) -> Dict[str, Any]:

    top_items: List[Dict[str, Any]] = []
    for row in results[:5]:
        pid = str(row.get("policy_id") or "")
        top_items.append(
            {
                "policy_id": pid,
                "chunk_id": row.get("chunk_id"),
                "section": row.get("section"),
                "score": row.get("score"),
                "rank_score": row.get("rank_score"),
                "source_url": source_map.get(pid, ""),
            }
        )
    return {
        "result_count": len(results),
        "dedup_skipped": retrieval_debug.get("dedup_skipped"),
        "top_items": top_items,
    }


def main() -> None:

    """
    1) 입력/프로필 준비
    2) retriever 호출
    3) GPT 생성 + 스키마 정규화
    4) JSON 출력
    """

    args = parse_args()
    load_dotenv()

    api_key = os.getenv(args.api_key_env, "").strip()
    if not api_key:
        raise EnvironmentError(f"{args.api_key_env} 환경변수가 비어 있습니다.")

    profile = build_profile(args)
    query = args.query.strip() if isinstance(args.query, str) else ""
    if not query:
        query = build_auto_query(profile)

    region = profile.get("region") or {}
    region_city = str(region.get("city") or "")
    region_gu = str(region.get("gu") or "")
    age = profile.get("age")
    age_num = int(age) if isinstance(age, int) else -1

    # Namespace 재구성
    retriever_args = SimpleNamespace(
        query=query,
        top_k=args.top_k,
        search_k=args.search_k,
        query_model=args.query_model,
        api_key_env=args.api_key_env,
        index=args.index,
        index_log=args.index_log,
        mapping=args.mapping,
        chunks=args.chunks,
        metadata=args.metadata,
        age=age_num,
        region_sido=region_city,
        region_sigungu=region_gu,
        disable_section_weight=False,
        section_weights=args.section_weights,
        disable_dynamic_section_weight=args.disable_dynamic_section_weight,
        disable_dynamic_category_weight=args.disable_dynamic_category_weight,
        disable_text_dedup=args.disable_text_dedup,
        text_dedup_min_len=args.text_dedup_min_len,
        preview_chars=args.preview_chars,
        json=False,
    )
    retrieval_payload = run_retrieval(retriever_args)
    results: List[Dict[str, Any]] = retrieval_payload["results"]

    source_map = load_source_map(args.metadata)
    context_text = build_context_text(results, source_map=source_map)
    user_prompt = build_user_prompt(query, profile, context_text)

    # 생성 : retriever 근거를 user_prompt에 넣고 gpt-4o-mini 호출
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=args.chat_model,
        temperature=args.temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    answer = (resp.choices[0].message.content or "").strip()

    # 모델이 스키마를 어기거나 JSON 파싱에 실패할 경우를 대비한 fallback 의견서
    fallback_memo = build_default_memo(results, source_map=source_map, query=query)
    try:
        memo_obj = extract_json_object(answer)
        housing_memo = normalize_housing_memo(memo_obj, fallback=fallback_memo)
    except Exception:
        housing_memo = fallback_memo
    housing_memo = attach_source_url_to_evidence(housing_memo, source_map=source_map)

    if args.json:
        retrieval_debug = retrieval_payload.get("debug", {})
        out = {
            "query": query,
            "user_profile": profile,
            "retrieval_summary": build_retrieval_summary(
                results=results,
                retrieval_debug=retrieval_debug,
                source_map=source_map,
            ),
            "housing_memo": housing_memo,
        }
        if args.debug_verbose:
            out["retrieval_debug"] = retrieval_debug
            out["retrieved"] = results
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print(json.dumps(housing_memo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
