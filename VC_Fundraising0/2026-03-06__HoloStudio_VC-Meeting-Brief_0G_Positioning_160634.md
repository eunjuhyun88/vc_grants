# Holo Studio — VC Meeting Brief

---

## Overview

이 문서는 VC 미팅 전 내부 준비용 브리핑 문서다.  
각 프로젝트를 개별 기능 단위가 아니라 **하나의 AI 인프라 스택**으로 설명하는 구조로 정리한다.

---

## VC 투자 관점 이해

VC는 인프라·기반 기술처럼 스케일이 큰 사업에 투자하는 경향이 있다.  
에이전트·애플리케이션 레이어는 성과가 검증된 이후 투자되는 경우가 많으며, 초기 단계에서는 확장성·시장 규모 측면에서 한계로 판단되는 경우가 많다.

따라서 이번 미팅에서 단순히 "이 기능이 특별하다"는 방식보다, 다음 3가지를 중심으로 설명할 수 있도록 **이 문서는 그 준비를 위한 것이다:**

1. **기술 구조** — 어떤 아키텍처로 동작하는가
2. **성능 우위** — 기존 AI 모델 대비 무엇이 다른가 (benchmark 수치)
3. **인프라 확장성** — 개별 앱이 아닌 레이어로 확장될 수 있는가

---

## Why Now — AI 시장 변화

현재 AI 시장에서 동시 발생 중인 변화:

| 변화 | 현황 |
|------|------|
| AI 모델 폭발적 증가 | 수백 개 LLM, 멀티모달 모델 등장 |
| AI agent·자동화 시스템 확산 | 기업·개인 도입 급증 |
| 신뢰 검증 인프라 부재 | 어떤 모델이 더 좋은지 판단할 표준 없음 |

결론: AI ecosystem은 성장하고 있지만 **어떤 모델이 신뢰 가능한지, 어떤 데이터가 검증된 것인지**를 판단하는 표준화된 평가 인프라가 부족하다.

→ **AI Benchmark / Evaluation / Trust Infrastructure** 가 중요한 투자 영역으로 부상 중.

---

## 전체 포지셔닝 구조

```
AI Models (GPT, Claude, Open-source...)
        ↓
Benchmark & Evaluation Layer  ←── MoltVC, StockClaw
        ↓
Trust / Data Infrastructure   ←── HOOT (AI training data), PlayArts (image consistency)
        ↓
Physical AI Layer             ←── ClawGene (Physical AI — Proof of Useful Evolution)
        ↓
Applications                  ←── Elemental, Game AI (게임 VC 대상)
```

**Holo Studio = AI Benchmark & Evaluation Infrastructure**

핵심 기능:
- AI 모델 성능 평가
- Benchmark 시스템
- 모델 결과 데이터 온체인 기록
- 성능 개선 히스토리 관리

---

## 프로젝트별 VC 설명 포지셔닝

### StockClaw

**포지셔닝:** AI Trading Strategy Evaluation Infrastructure

> **VC 한 줄 pitch:** "4년치 백테스팅 데이터로 검증된 AI 트레이딩 전략 평가 인프라 — 일반 LLM 대비 전략 성능을 수치로 증명한다."

단순 차트 분석 툴이 아니라, AI 트레이딩 전략을 평가하는 인프라로 설명.

확보 필요한 데이터:
- BTC / ETH 차트 분석 결과
- 4년치 백테스팅 데이터
- 동일 조건에서 일반 모델 vs StockClaw benchmark 비교
- 모델별 전략 성능 차이 분석

설명 구조:
> "트레이딩 전략 테스트 → AI 모델 성능 비교 → 데이터 기반 전략 평가를 수행하는 금융 AI 분석 인프라"

---

### MoltVC

**포지셔닝:** On-chain AI Model Evaluation Ledger

> **VC 한 줄 pitch:** "ChatGPT·Claude보다 정확한 스타트업 평가 기준을 온체인에 누적 기록 — VC가 포트폴리오 성과를 데이터로 추적하는 유일한 AI 평가 인프라."

단순 평가 서비스가 아니라, AI 모델 평가 결과를 블록체인에 기록하는 인프라로 설명.

확보 필요한 데이터:
- MoltVC 평가 기준 vs ChatGPT / Claude 성능 비교
- 동일 task 수행 시 benchmark 결과

블록체인 필요성 근거:
- AI 모델 평가 결과를 온체인 기록 → 불변성 확보
- ERC-8004 구조 활용 → 평가 데이터 저장
- 모델 성능 개선 과정 추적 → audit trail

설명 구조:
> "AI model performance tracking infrastructure — 평가 결과를 블록체인에 기록하는 on-chain AI evaluation ledger"

---

### PlayArts

**포지셔닝:** Image Consistency Benchmark Infrastructure

> **VC 한 줄 pitch:** "1~10장 입력만으로 어떤 동작에서도 동일한 캐릭터 아트를 생성 — 이미지 일관성을 수치로 증명하는 콘텐츠 AI 인프라."

이미지 생성 기능이 핵심이 아니라, **image consistency 기술**이 핵심.

현재 특징:
- 다양한 동작에서도 캐릭터 스타일 일관성 유지
- 반복 입력 없이 동일한 아트 스타일 유지
- 동일 캐릭터 기반 콘텐츠 제작

수치화 필요한 metric (현재 미확보 — [정보 부족]):
- Image similarity score
- Character identity score
- Style consistency metric

설명 구조:
> "Image Consistency Benchmark Infrastructure — 캐릭터 일관성을 수치로 검증하는 콘텐츠 AI 인프라"

---

### HOOT Protocol

**포지셔닝:** Verified AI Training Data Infrastructure + On-chain Model Marketplace  
*"Use AI. Train AI."*

브라우저에서 AI를 사용하는 행위 자체가 검증된 학습 데이터로 전환되고, 그 데이터로 훈련한 모델을 소유하거나 채팅으로 온체인 거래하는 인프라.

**핵심 작동 구조:**

| 단계 | 내용 |
|------|------|
| 1. 사용 | Hoot Browser에서 ChatGPT / Claude / Gemini 등 어떤 AI든 평소처럼 사용 |
| 2. 포획 | 네트워크 레벨에서 TLS 세션 캡처 — 사용자 행동 변화 없음 |
| 3. 검증 | zkTLS (2PC-HMAC) + FROST 5-of-5로 암호학적 진정성 증명. 위조 확률 2⁻¹²⁸ |
| 4. 구조화 | 학습 가능한 포맷으로 자동 변환 |
| 5. 소유 / 거래 | ERC-721(단일 소유) / ERC-1155(연합 학습 공동 소유) — **채팅 명령으로 온체인 모델 거래 가능** |

**온체인 거래 예시 (채팅 인터페이스):**
- "내 크립토 트레이딩 모델 0.5 ETH에 리스팅해줘"
- "법률 도메인 파인튜닝된 모델 구매해줘"
- "내 연합 학습 지분 50% 양도해줘"

**기술 스펙:**

| 항목 | 내용 |
|------|------|
| 토큰 | HOOT (ERC-20, Arbitrum One) |
| 총 공급 | 1,000,000,000 (고정) |
| 핵심 암호학 | zkTLS (2PC-HMAC) + FROST 5-of-5 (RFC 9591) |
| 스마트 컨트랙트 표준 | ERC-8004 (Agent) · ERC-4337 (Wallet) · ERC-721 (Model NFT) |
| 블록체인 | 0G Labs (Zero Gravity) — AI-native decentralized L1, EVM 호환 |

**VC용 설명 구조:**

> "AI 사용 데이터는 매일 수십억 건 발생하지만 검증·소유·거래가 불가능했다. Hoot은 브라우저 레벨에서 이 데이터를 암호학적으로 포획하고, 훈련된 모델을 온체인 자산으로 만들어 채팅으로 거래 가능하게 한다."

**확인 필요 (미팅 전):** Hoot Browser 구현 완료 여부, 온체인 거래 시연 가능 여부

---

### ClawGene

**포지셔닝:** Physical AI — Browser-Based On-Chain Evolutionary Simulator  
*"Bitcoin mines hashes. ClawGene mines brains."*

단순 NFT 게임이 아니다. **지구상에서 완전한 커넥톰이 존재하는 유일한 생물(C. elegans)**의 279개 신경회로를 브라우저에서 시뮬레이션하고, 진화 결과를 온체인에 기록하는 Physical AI 프로토콜.

**기술 근거 (실제 데이터 기반):**

| 항목 | 내용 |
|------|------|
| 생물 기반 | C. elegans — 4번의 노벨상(2002·2006·2008·2024), 1986년 White et al. 커넥톰 완전 매핑 |
| 신경회로 | 279 뉴런 / 2,183개 수정 가능 시냅스 / 4개 기능 레이어(Sensory→Interneuron→Command→Motor) |
| 학습 메커니즘 | STDP (Spike-Timing Dependent Plasticity) — Markram et al.(1997) 기반. 경험으로 시냅스 가중치가 실시간 재배선됨 |
| 환경 시뮬레이션 | TOXIC / FAMINE / AQUATIC / EXTREME / PARADISE 5개 프리셋 + 10+ 파라미터 슬라이더 |
| 온체인 기록 | Base(Coinbase L2) — Checkpoint.sol로 진화 증명, Brain Trade로 훈련된 신경회로 거래 |

**VC용 설명 구조:**

> "DeFi가 금융 계약을 프로그래밍 가능하게 만들었다면, Physical AI는 생물 진화를 프로그래밍 가능하게 만들고 그 출력물에 경제적 가치를 부여한다. ClawGene은 이 카테고리를 정의하는 첫 번째 프로젝트다."

**기존 카테고리와의 차별화:**

| 카테고리 | 기존 | ClawGene |
|----------|------|----------|
| DeSci | VitaDAO — IP 토큰화 | 유저가 직접 생물 데이터 생성 |
| GameFi | Axie — 임의 게임 메커닉 | 실제 커넥톰 기반 진화 |
| AI Agents | AIXBT — LLM 소셜 에이전트 | STDP + Genetic Algorithm (Transformer 아님) |
| Mining | BTC — 해시 계산 | 유용한 신경회로 계산 (Proof of Useful Evolution) |

**토크노믹스 구조 ($ECDYS, Virtuals Protocol Unicorn Launch):**

| 배분 | 비율 | 수량 |
|------|------|------|
| Unicorn Launch (Public) | 50% | 500,000,000 |
| Mining Reward Pool | 30% | 300,000,000 (6개월 halving) |
| Team & Partners | 10% | 100,000,000 (6개월 cliff + 12개월 linear) |
| Ecosystem Treasury | 10% | 100,000,000 |

**VC가 물어볼 리스크 — 사전 준비 필요:**

- *"왜 블록체인이 필요한가?"* → 진화 기록의 불변성(Checkpoint.sol), 훈련된 brain의 소유권 증명(BrainTrade.sol), 인센티브 레이어($ECDYS) — 세 가지가 블록체인 없이는 성립 안 함
- *"NFT 게임 아닌가?"* → 거래 단위가 스킨이 아니라 STDP로 훈련된 279×279 시냅스 가중치 행렬. ML 관점에서는 "pre-trained model weights 거래"와 구조적으로 동일
- *"OpenWorm이랑 뭐가 달라?"* → OpenWorm은 정적 커넥톰, Python CLI, 토큰 없음. ClawGene은 STDP 학습 + 브라우저 접근 + 경제 레이어

**향후 로드맵 (Neuromorphic Hardware):**

BrainScaleS 2 칩 = 512 뉴런. ClawGene = 279 뉴런. 스케일이 수렴하는 지점.  
→ 브라우저에서 훈련한 brain을 neuromorphic 칩에 이식하는 경로가 기술적으로 가장 자연스러운 다음 단계.  
[주의: graded potential STDP → spiking STDP 변환 레이어 필요. 현재 미검증. — [판단 불가]]

**현재 상태 및 리스크:**

- Free Play DAU 미확보 — Commit 60일 내 유저 유입이 핵심 검증 포인트
- Brain Trade 수요가 없으면 $ECDYS 소각 메커니즘 작동 안 함
- Virtuals Protocol 의존성 — $VIRTUAL이 ATH 대비 ~90% 하락 상태 [정보: Whitepaper v0.6.0 기준]

**VC 덱 배치 권장:**  
일반 AI/Web3 VC → 비중 축소 또는 후순위 (Physical AI 카테고리 이해도 낮음)  
DeSci / GameFi 특화 VC → 첫 번째 슬라이드로 배치 가능 (카테고리 정의자 포지션)

---

### Elemental

NFT 기반 카드 게임 — [정보 부족: 현재 자료 없음]. 일반 VC 덱에서는 후순위 배치 권장.

---

### 게임 AI (게임 VC 대상)

**포지셔닝:** Game AI Training Platform

구조:
1. 유저가 캐릭터 동작 평가
2. 해당 데이터 기반 모델 학습
3. 회사 선호 스타일에 맞게 파인튜닝

설명 구조:
> "유저 피드백 기반 AI 학습 시스템 — 게임 제작 자동화 파이프라인"

---

## Benchmark 데이터 확보 체크리스트

VC 설득에서 기능 설명보다 수치 근거가 훨씬 유효하다.

| 항목 | 데이터 유형 | 확보 여부 |
|------|------------|---------|
| StockClaw 백테스팅 | 전략 성능 수치 | 확인 필요 |
| MoltVC 평가 정확도 | 기존 모델 대비 비교 | 확인 필요 |
| PlayArts 이미지 일관성 | Similarity score | 미확보 |
| HOOT 온체인 거래 | 시연 가능 여부 | 확인 필요 |

---

*Generated: 2026-03-06*
