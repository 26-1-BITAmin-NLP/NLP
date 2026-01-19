# 청년 주거 정책 추천 에이전트 🏠

> 청년 대상 주거 정책을 통합하여
> <br/>
> 사용자 정보 기반 정책 추천 및 전략 수립을 수행하는 멀티 에이전트 기반 nlp 프로젝트

<br/>

## 멤버
| Data | Data | Data | Data |
|:----:|:----:|:----:|:----:|
| 곽혜진 | 김영진 | 서지훈 | 조혜림 |

<br/>

## 개발 환경
* 언어 : Python
* 데이터 처리 및 저장 : Pandas, csv 기반
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
   
<br/>

## 브랜치 컨벤션
* `main` - 프로젝트 배포 및 제출
* `develop` - 통합 개발
* `feature/` - 기능/파트별 개발

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