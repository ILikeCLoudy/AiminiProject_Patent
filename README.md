# Design and Implementation project about Edge AI / On-Device Patent Evaluation Agent 
본 프로젝트는 Edge AI/온디바이스 기술 특허 및 평가 에이전트를 설계하고 구현한 프로젝트입니다.

## Overview

### Objective
#### 1) Technical Merit
1-1. 기술 성숙도(TRL) 맵핑
- 방법: 초록/청구항의 키워드(실험·프로토타입·파일럿·운용 등)를 규칙화해 TRL 1–9에 근사 매핑.
- 판단: TRL 6+이면 “시스템/대표 모델 검증 이상”으로 가점.
- 근거: TRL은 NASA가 만든 **기술 성숙도 표준(1–9)**로, 항공우주 외 산업 전반으로 확산.

1-2. 전방 인용수(연차·분야 보정)
- 방법: 공개 후 고정 창(예: 5년)의 forward citations를 CPC×연도 코호트로 정규화(퍼센타일).
- 판단: P90≈“영향력 매우 큼”으로 고득점.
- 근거: 전방 인용이 경제적/기술적 가치와 유의미하게 상관(Tobin’s Q 등)한다는 누적 연구.

1-3. 청구항 특성(범위/명확성 프록시)
- 방법: 독립항 수/길이(과도하게 많거나 과도하게 짧음에 U-자 페널티), 종속항 구조 텍스트 분석.
- 판단: 적정 독립항과 명료한 범위 → 가점.
- 근거: 청구항은 보호범위의 핵심이며(특허 실무 상식), 텍스트적 특성으로 분석/도식화 가능.

1-4. 법적 상태·유지(갱신·존속) 시그널
- 방법: 상태(거절/등록/만료), 유지·갱신(maintenance/renewal) 여부/연차 확인.
- 판단: 연차가 높을수록 비용을 감수하고 유지 → 기대가치 시그널로 가점.
- 근거: 유지·갱신은 비용 대비 가치 판단의 결과라는 제도 취지(USPTO), 갱신 지속이 가치의 실사(자기평가) 지표라는 경제학 문헌.

1-5. 패밀리 규모·지리 커버리지
- 방법: family size / 다국 출원 수(foreign-oriented 여부) 산출.
- 판단: 다국 출원·대형 패밀리 → 상업화 의지/범위 시그널로 가점.
- 근거: WIPO는 외국 지향 패밀리를 가치·품질이 높은 지표로 간주, 패밀리 데이터는 중복 제거된 발명 단위 포착에 사용.

1-6. 기술 확산성/범용성(Generality/Originality)
- 방법: HJT 지표(분류 다변성 기반 Generality/Originality) 계산.
- 판단: 분야에 걸친 확산 잠재(Generality↑)는 가점(단, 해석 시 절단 문제 주의).
- 근거: NBER 특허 인용 데이터의 Generality/Originality 정의와 활용.

#### 2) Market Potential
2-1. 국제화/상업화 의지 프록시(패밀리·해외출원)
- 방법: foreign-oriented family 비율/국가 수.
- 판단: 다국 보호는 비용을 무릅쓴 선택 → 상업적 기대가 큼.
- 근거: 외국 지향 패밀리 = 더 높은 품질/가치 지표(WIPO WIPI 2024).

2-2. 유지·존속 기간(수요 지속성 시그널)
- 방법: 만료 전 장기 유지, 고연차 갱신 여부 확인.
- 판단: 장기 갱신은 시장 수요/수익 기대 지속 신호.
- 근거: 갱신은 소유자가 가치>비용 판단 시 지속(USPTO 제도 설명), 연구에서도 갱신 지속=가치로 사용

2-3. 표준(SEP/FRAND) 연계 신호
- 방법: ETSI 등 SDO SEP 선언/FRAND 연결 여부, 표준 사양 매칭(키워드/문서).
- 판단: 표준필수(SEP) 또는 표준 참여는 광범위 채택 가능성 시그널(단, 과다선언 리스크 표시).
- 근거: SEP = 표준 구현에 필수, SSO는 FRAND 라이선스 요구(ETSI IPR/정의).

#### 3) Competitive Advantage
3-1. 기술 영역 내 경쟁 밀도(경합도) 지표
- 방법: 동일 CPC 서브클래스/키워드 컷에서 출원인 점유율 HHI 산출.
- 판단: HHI 낮음(분산) = 화이트스페이스/차별화 여지↑, HHI 높음 = 레드오션 경고.
- 근거: HHI는 표준적 시장집중도 지표로 규제/경쟁 분석에 사용.

3-2. 차별화 신호(Generality/Originality, 클레임 범위)
- 방법: HJT 지표로 기술 출처 폭/영향 범위를 보고, 청구항 범위로 차별화 가능성 추정.
- 판단: 고유·범용 조합(높은 originality 또는 generality + 합리적 클레임 폭) → 기술적 차별화.
- 근거: HJT의 Generality/Originality 정의 및 활용.

3-3. 차단력/방어력 신호(법적 상태·FTO 플래그)
- 방법: 경쟁 특허의 유효/만료·지리 범위, 우리 기술 대비 FTO 리스크 플래그.
- 판단: 광범위 유효권리/중첩 높음 → 충돌 가능성 경고(법률 자문 필요 표기).
- 근거: WIPO는 FTO 분석을 제품 출시 전 핵심 단계로 권고(“절대 보장 불가, 리스크 최소화”).

#### 4) Scoring
**정규화**: 모든 정량 지표는 CPC×공개연도 코호트로 퍼센타일 변환 후 5점화.
**스코어링 예시:**
- 기술성(60): 전방 인용(연차보정)·패밀리·청구항·법적상태·TRL·Generality
- 시장성(25): foreign-oriented·유지/갱신·표준(SEP/FRAND)
- 경쟁우위(15): HHI(역가점), Generality/Originality, FTO 플래그(감점 규칙)

리포트 표기: 각 점수 옆에 원시값→정규화값→출처 링크(특허번호/ETSI/법령) + 위 근거를 근거 패킷으로 병기

### Method
- Agentic Workflow: 수집/중복정리→요약→코어 점수화(서지·법적 메타)→어댑터 점수화(지연·전력·메모리·모델 크기·정확도 변동·표준 신호)→집계/랭킹→보고서 자동화.
- 정규화/평가: 분야(CPC)×연도 코호트 퍼센타일 정규화 → 5점 척도 + S/M/L 병기, 가중합 총점(100점 환산), 감도분석(랭킹 일치율).
- 근거 패킷화: 특허별로 지표 원시값·정규화 값·요약 스니펫·식별자 링크를 함께 저장/표기.
- 재현성: 쿼리·기간·버전·Seed·캐시 여부를 실행 메타로 기록.

### Tools
- Orchestration: LangGraph, Python 3.11
- LLM: GPT-4o-mini (OpenAI API)
- Retrieval/Store: Chroma
- Data/Scoring: pandas, numpy, scikit-learn

## Features

- 코어 평가 자동화: 전방인용(연차보정), 패밀리/국가, CPC 다양성, 청구항 특성, 법적 상태, (선택) TRL을 분야×연도 코호트 퍼센타일 → 5점 척도로 일괄 산출
- 어댑터(Edge) 평가: 지연(ms)·전력(mW/µJ)·메모리(MB)·모델 크기(MB)·정확도 변동(Δ)·표준/컨소시엄 신호를 별도 병기(플래그 포함)
- 설명가능 결과(근거 패킷): 특허별 원시값 → 정규화값 → 근거 스니펫/링크를 함께 제공
- 랭킹/라벨링: 가중합 총점(100점 환산) 기반 A/P/M/X(Adopt/Prototype/Monitor/Archive) 기술 라벨 출력
- 보고서 자동 생성: Top-K 카드 + 비교 차트 + 방법론 부록(가중치·컷·정규화 규칙·재현성 메타) PDF 생성
- 재현성 확보: 쿼리·기간·버전·Seed·가중치/컷 테이블·캐시 여부를 실행 메타로 기록


## Tech Stack 

| Category   | Details                      |
|------------|------------------------------|
| Framework  | LangGraph, Python 3.11 |
| LLM        | GPT-4o-mini via OpenAI API   |
| Retrieval  | Chroma                |
| Embedding  | text-embedding-3-small (OpenAI)  |
| Data  | pandas, numpy, scikit-learn        |

## Agents
- Master Agent: Edge AI / On-device 관련 기술 특허 검색 Agent
- Patent-Search Agent: 키워드/CPC/기간 기반 수집, 패밀리 병합·중복 제거·비관련 필터
- Summarizer Agent: 초록/청구항에서 문제–해결–효과 3문장 요약 + 근거 스니펫
- Core-Scoring Agent: 코호트 퍼센타일 정규화→5점화, 코어 지표(A1~A6) 산출
- Edge-Adapter Agent: Edge 지표/표준 신호 추출, 보조 점수 및 플래그 생성
- Aggregator Agent: 가중합·랭킹·Top-K 선정 및 A/P/M/X 라벨 결정(플래그 반영 규칙 포함)
- Report Agent: 특허 카드/비교 차트/부록/면책 문구 포함 PDF 생성

## State 
- query_scope : 키워드, CPC/IPC, 기간, 데이터 소스
- patents_raw : 수집 원시 메타(제목·초록·출원인·CPC·공개일·인용·패밀리)
- patents_dedup : 패밀리 병합/중복 제거/비관련 필터 결과
- summaries : 특허 요약 3문장 + 근거 스니펫/링크
- core_scores : 코어 지표 원시값/퍼센타일/5점 변환 테이블
- adapter_scores : Edge 지표/표준 신호 점수·플래그
- ranking : 가중합 총점, Top-K 리스트, A/P/M/X 라벨
- exec_meta : 실행일시(Asia/Seoul), 버전, Seed, 가중치·컷 스냅샷, 캐시 여부
- report_path : PDF/CSV 산출물 경로


## Architecture
<img width="1511" height="3618" alt="image" src="https://github.com/user-attachments/assets/86823dde-1a66-4b0b-88f8-f0eb64075092" />



## Directory Structure
```
├── data/                      # 원시/정제 메타데이터(JSON/Parquet)
├── agents/                    # 에이전트 모듈 (search, summarize, score, report ...)
├── prompts/                   # 프롬프트 템플릿
├── scoring/                   # 지표 계산/정규화/라벨 규칙
├── reports/                   # PDF/CSV 산출물
├── cache/                     # 중간 캐시(임베딩/요약/스코어)
├── app.py                     # 엔드투엔드 실행 스크립트(CLI)
├── README.md
└── requirements.txt
```

## Contributors 
- 이정엽 : 기술 특허 평가 Agent 설계 및 구축, Context 엔지니어링
