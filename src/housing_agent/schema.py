from dataclasses import dataclass, field
from typing import Optional, List

# eligibility_struct 클래스

@dataclass
class Regions:
    sido: List[str] = field(default_factory=list)
    sigungu: List[str] = field(default_factory=list)

@dataclass # LLM 사용 전 구조화 스키마
class EligibilityStruct:
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    income_max: Optional[int] = None # 월 소득 상한 (만 단위)
    asset_max: Optional[int] = None # 자산 상한 (만 단위)

    household_types: List[str] = field(default_factory=list) # 대상 가구 유형 (예: "청년", "신혼", "다자녀", "1인 가구" 등)
    requires_no_house: Optional[bool] = None # 무주택 조건 필요 여부

    regions: Regions = field(default_factory=Regions)
    housing_types: List[str] = field(default_factory=list) # 주거 형태 (예: "월세", "공공임대", "분양", "기숙사" 등)


# 최종 정책 스키마

@dataclass
class Policy:
    policy_id: str
    category: str
    title: str

    eligibility_struct: EligibilityStruct

    # 설명 생성용 (LLM)
    eligibility_text: Optional[str] = None # 지원 대상 및 조건 전체 텍스트
    benefit_text: Optional[str] = None # 지원 내용, 금액, 혜택 전체 텍스트
    process_text: Optional[str] = None # 신청 방법, 기간, 문의 전체 텍스트

    provider: Optional[str] = None
    region: Optional[str] = None
    source_url: Optional[str] = None