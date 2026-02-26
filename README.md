# 청년 미래 설계 에이전트 🏠

> 사용자 개인 프로필(소득, 자산, 계획 등)을 분석하여
> <br/>
> 최적의 주거 정책과 맞춤형 금융 상품을 결합한 미래 설계 의견서를 제공하는 멀티 에이전트 시스템

<br/>

## 멤버 및 역할
| 이름 | 역할 |
|------|------|
| 곽혜진 | 데이터 수집 + 주거 에이전트 개발 |
| 조혜림 | 데이터 수집 + 금융 에이전트 개발 |
| 김영진 | 데이터 수집 + 메인 에이전트 개발 |
| 서지훈 | 데이터 수집 + Streamlit UI 연결 |

<br/>

## 개발 환경
* 언어 : Python
* 데이터 처리 및 저장 : Pandas, csv, json 기반
* 협업 툴 : Notion, Github

<br/>

## 실행 순서
### 1. Repo Clone

   ```
    git clone <repo-url>
    cd <repo-folder>
   ```
   
### 2. 가상환경 생성 및 실행
   
   ```
    python3 -m venv .venv
    source .venv/bin/activate  #mac/linux
    .venv\Scripts\activate  #windows
   ```
    
### 3. 라이브러리 설치
   
   ```
    pip install -r requirements.txt
   ```

### 4. Streamlit 실행
   
   ```
    streamlit run app.py
   ```
   
<br/>

## 브랜치 컨벤션
* `main` - 프로젝트 배포 및 제출
* `develop` - 통합 개발
* `이름` - 기능/파트별 개발

<br/>

## 커밋 컨벤션
> 타입 + 내용

* `feat` - 기능 추가
* `fix` - 버그 수정
* `docs` - 문서 추가/수정
* `style` - 코드 포맷 수정
* `refactor` - 리팩토링
* `chore` - 빌드/패키지/환경 설정

<br/>

## 비고
* 데이터 파일 및 모델 파일은 `.gitignore` 폴더에서 관리
* `.env` 파일을 통한 환경변수 관리