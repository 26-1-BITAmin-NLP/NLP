from dataclasses import dataclass
from typing import Optional

# 데이터 최종 스키마 정리
@dataclass
class Policy:
    policy_id: str
    category: str
    title: str
    region: Optional[str]
    provider: Optional[str]
    source_url: Optional[str]

    target_text: Optional[str]
    condition_text: Optional[str]
    benefit_text: Optional[str]
    apply_text: Optional[str]
    contact_text: Optional[str]

    raw_text: str