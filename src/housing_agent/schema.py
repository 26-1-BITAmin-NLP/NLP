from dataclasses import dataclass, field
from typing import Optional, List

# eligibility_struct 클래스

@dataclass
class Regions:
    sido: List[str] = field(default_factory=list)
    sigungu: List[str] = field(default_factory=list)

@dataclass
class EligibilityStruct:
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    income_max_m: Optional[int] = None
    asset_max_m: Optional[int] = None

    household_types: List[str] = field(default_factory=list)
    requires_no_house: Optional[bool] = None

    regions: Regions = field(default_factory=Regions)
    housing_types: List[str] = field(default_factory=list)


# 최종 정책 스키마

@dataclass
class Policy:
    policy_id: str
    category: str
    title: str

    eligibility_struct: EligibilityStruct

    eligibility_text: Optional[str] = None
    benefit_text: Optional[str] = None
    process_text: Optional[str] = None

    provider: Optional[str] = None
    region: Optional[str] = None
    source_url: Optional[str] = None