# HOOT — Funding Priority List

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-03-08 | 초기 작성 |

---

## Company Profile: Holo Studio / HOOT

| 항목 | 값 |
|------|-----|
| 회사 | Holo Studio Co., Ltd. |
| 위치 | Korea |
| 단계 | Seed (MVP) |
| 주력 프로젝트 | HOOT |
| HOOT 설명 | 개인 데이터 기반 소형모델(Qwen 등) 학습 + 분산 컴퓨팅(토렌트 개념) + 블록체인 coordination |
| 섹터 태그 | ai_infra, decentralized_ai, crypto_infra, distributed_compute, personal_model_training |

**프로젝트 우선순위:** HOOT > StockClaw > MoltVC > PlayArts > ClawGene

---

## Top 10 Priority Funding (HOOT 기준)

priority_score = fit(0.35) + urgency(0.25) + actionability(0.20) + expected_value(0.10) + confidence(0.10)

| 순위 | 기관 | 프로그램 | priority_score | apply_url |
|------|------|---------|---------------|-----------|
| 1 | Alliance DAO | Alliance Accelerator | 0.82 | https://alliance.xyz/apply |
| 2 | Ethereum Foundation | ESP (Ecosystem Support) | 0.79 | https://esp.ethereum.foundation |
| 3 | NEAR Foundation | NEAR Ecosystem Grants | 0.77 | https://near.org/funding |
| 4 | Bittensor | Subnet Grant | 0.75 | https://bittensor.ai/subnets |
| 5 | Solana Foundation | Solana Grants | 0.73 | https://solana.org/grants-funding |
| 6 | Arbitrum Foundation | Arbitrum Grants | 0.71 | https://arbitrum.foundation/grants |
| 7 | Outlier Ventures | Base Camp Accelerator | 0.69 | https://outlierventures.io/apply |
| 8 | Avalanche | infraBUIDL(9) Program | 0.67 | https://build.avax.network/grants/infrabuidl |
| 9 | Cosmos | Interchain Foundation Grants | 0.66 | https://cosmosgrants.org |
| 10 | Polygon | Ecosystem Grants | 0.65 | https://polygon.technology/ecosystem-grants |

**[주의]** priority_score는 2026-03-08 기준 추정값. fit_score는 실제 DB matching_agent 결과로 갱신 필요.  
urgency_score는 실제 deadline 확인 후 재계산 필요. 현재 값은 [추정].

---

## Additional Accelerators (MVP 단계 적합)

| 기관 | 프로그램 | 특징 | apply_url |
|------|---------|------|-----------|
| HF0 | HF0 Residency | no equity, SF | https://hf0.com/apply |
| Antler | Antler Korea/Global | early stage | https://antler.co/apply |
| Pioneer | Pioneer Tournament | 온라인, weekly | https://pioneer.app |
| Berkeley SkyDeck | SkyDeck Accelerator | $100K+, BDSA | https://skydeck.berkeley.edu/apply |
| a16z | Speedrun | crypto-native | https://speedrun.a16z.com/apply |
| Monad | Mach Accelerator | Monad ecosystem | https://monad.xyz |

---

## Monad Programs (별도 추적)

| 프로그램 | URL | 특징 |
|---------|-----|------|
| Momentum | https://momentum.monad.xyz | 지속적 builder 지원 |
| Mach Accelerator | https://monad.xyz/mach | 공식 accelerator |
| Founder Residency | https://monad.xyz | 상주 프로그램 |
| Monad Madness | https://monad.xyz | 해커톤 |

**Monad 정책:** MVP 단계 선호. 마감일 주기적 확인 필요.

---

## Fit 판단 기준 (HOOT)

Matching Agent가 이 기준으로 fit_score 계산:

```
High fit (≥ 0.75):
  - sector_tags 2개 이상 overlap
  - AI infra / decentralized compute 명시적 지원
  - MVP/Seed 단계 허용

Medium fit (0.50~0.74):
  - Web3 일반 지원 + AI 언급
  - 단계 제한 없음

Low fit (< 0.50):
  - DeFi/NFT/Gaming 특화
  - Series A 이상 요구
  - 특정 체인 exclusive (HOOT와 무관한 체인)
```

---

## 업데이트 필요 항목

- [ ] 각 프로그램의 실제 deadline 확인 및 DB 입력
- [ ] priority_score → matching_agent 실행 후 실측값으로 교체
- [ ] Monad Mach Accelerator 2026 cohort 모집 일정 확인
- [ ] Alliance Accelerator 현재 cohort 모집 여부 확인
