# Funding Autoresearch Program

이 파일은 `karpathy/autoresearch`의 `program.md`를 Funding Intelligence Agent에 맞게 옮긴 사람-편집 제어 파일이다.

목표는 단순히 더 많은 후보를 찾는 것이 아니라, 아래 user-facing output이 실제로 채워질 때까지 search/runtime을 계속 돌리는 것이다.

- `/funding_for_project HOOT`
- `/funding_map HOOT`
- `/org Monad`

고정 truth는 바꾸지 않는다.

- deadline / funding_amount / apply_url 생성 금지
- social-only candidate를 verified로 승격 금지
- Organization -> Program -> Opportunity hierarchy 유지

자동 개선 대상은 아래로 제한한다.

- search hint expansion
- official/apply bootstrap 강화
- ecosystem/partner/mentor query family 확장
- goal-specific recovery action 조합
- round reflection에서 승격된 search policy seed 재사용

## Active Goals

- HOOT actionable strategy output을 사람이 바로 읽고 지원할 수 있는 수준으로 끌어올린다.
- HOOT funding map에서 Monad / NEAR / Ethereum / Solana / Arbitrum 축을 안정적으로 잡는다.
- Monad dossier에서 Nitro / Momentum / founder/residency 계열 program context를 충분히 모은다.

## Machine Config

```json
{
  "name": "funding-autoresearch",
  "benchmark": "eval/funding_benchmark.yaml",
  "default_cases": [
    "hoot_actionable_strategy",
    "hoot_funding_map",
    "org_dossier_monad"
  ],
  "seed_actions": [
    "fallback_to_reference_registry",
    "bias_official_domains_and_reference_sources"
  ],
  "continuous": {
    "max_cycles": 4,
    "plateau_cycles": 2,
    "min_progress_delta": 0.01
  },
  "reflection": {
    "load_path": "data/curated_autoresearch_reflection.json",
    "latest_path": "output/research-evals/latest-reflection.json",
    "promote_path": "data/curated_autoresearch_reflection.json",
    "max_search_hints": 12,
    "max_bootstrap_terms": 8
  },
  "goal_overrides": {
    "actionable_strategy": {
      "seed_actions": [
        "recover_actionable_mix",
        "recover_builder_and_cohort_mix",
        "improve_reason_and_next_action_coverage"
      ]
    },
    "funding_map": {
      "seed_actions": [
        "expand_ecosystem_graph_queries",
        "recover_missing_ecosystems"
      ]
    },
    "org_dossier": {
      "seed_actions": [
        "expand_org_program_queries",
        "expand_partner_and_mentor_queries",
        "expand_official_docs_queries"
      ]
    }
  }
}
```
