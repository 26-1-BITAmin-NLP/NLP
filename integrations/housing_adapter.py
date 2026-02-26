from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict
import sys  

def _fill_missing_keys(hm: Dict[str, Any]) -> Dict[str, Any]:
    hm.setdefault("summary", "")
    hm.setdefault("eligible_policies", [])
    hm.setdefault("strategy", "")
    hm.setdefault("evidence", [])
    hm.setdefault("generated_at", "")

    fixed = []
    for p in hm.get("eligible_policies", []):
        p.setdefault("name", "")
        p.setdefault("why", "")
        p.setdefault("benefit", "세부 내용은 공고/링크 확인")
        p.setdefault("caution", "자격요건/제출서류는 공고 기준 확인")
        fixed.append(p)
    hm["eligible_policies"] = fixed
    return hm

def run_housing(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    housing_agent CLI 실행 → JSON 출력 파싱 → housing_memo 반환
    실패 시: '가짜 추천' 대신 '연동 실패 안내' 반환
    """
    try:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            profile_path = td_path / "user_profile.json"
            profile_path.write_text(json.dumps(user_profile, ensure_ascii=False), encoding="utf-8")

            cmd = [
                sys.executable,  # "python" 대신 현재 venv 파이썬을 강제
                "-m",
                "src.housing_agent.pipeline.housing_opinion_prompt",
                "--user-profile-path",
                str(profile_path),
                "--json",
            ]

            proc = subprocess.run(cmd, capture_output=True, text=True)

            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())

            data = json.loads(proc.stdout)
            hm = data["housing_memo"] if isinstance(data, dict) and "housing_memo" in data else data
            hm = _fill_missing_keys(hm)
            hm["_status"] = "ok"  
            return hm

    except Exception as e:
        hm = {
            "_status": "error",
            "summary": (
                "현재 주거 정책 검색(인덱스/RAG) 연동에 실패했습니다.\n\n"
                "아래 항목을 확인 후 다시 시도해주세요:\n"
                "- 인덱스 파일 경로가 올바른지\n"
                "- vectorstore 파일이 존재하는지\n"
                "- 실행 환경(venv)이 동일한지\n\n"
                "문제가 지속되면 개발자에게 오류 로그를 전달해주세요."
            ),
            "eligible_policies": [],  # 가짜 추천 없음
            "strategy": "",
            "evidence": [
                {"source": "local_error", "snippet": str(e)}
            ],
        }
        hm = _fill_missing_keys(hm)
        return hm
    