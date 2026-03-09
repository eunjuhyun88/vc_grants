# think tool — System Prompt 템플릿

아래 내용을 system prompt에 그대로 붙여넣기.
{YOUR_DOMAIN_EXAMPLE} 부분만 프로젝트에 맞게 수정.

---

## think 툴 정의 (tools 배열에 추가)

```json
{
  "name": "think",
  "description": "복잡한 툴 체인 작업 중 중간 사고 공간. 새 정보를 가져오거나 데이터를 변경하지 않음. 로그에만 기록됨. 다음 상황에서 사용: (1) 이전 툴 결과를 분석하고 다음 행동을 결정할 때 (2) 여러 규칙/제약 조건을 동시에 확인할 때 (3) 순차적 결정에서 실수가 비쌀 때.",
  "input_schema": {
    "type": "object",
    "properties": {
      "thought": {
        "type": "string",
        "description": "사고 내용"
      }
    },
    "required": ["thought"]
  }
}
```

---

## System Prompt에 추가할 내용

```
## think 툴 사용 가이드

툴 결과를 받은 후, 다음 행동 실행 전에 think 툴로:
- 지금 상황에 적용되는 규칙/제약 조건 목록 확인
- 필요한 정보가 모두 수집됐는지 확인
- 계획한 행동이 모든 제약을 준수하는지 검증
- 실수가 발생했을 때 복구 비용이 큰 경우 한 번 더 확인

### 사용하지 않아도 되는 경우
- 단일 툴 호출 (검색 한 번, 조회 한 번 등)
- 제약 조건이 없는 단순 작업

### 도메인 예시
<think_example_1>
{YOUR_DOMAIN_EXAMPLE_1}
예시 형식:
요청: 사용자가 [작업] 요청
- 필요 확인: [필요한 정보 목록]
- 규칙 체크:
  * [규칙 1]
  * [규칙 2]
- 계획: [단계별 실행 순서]
</think_example_1>

<think_example_2>
{YOUR_DOMAIN_EXAMPLE_2}
</think_example_2>
```

---

## 프로젝트별 예시 작성 가이드

아래 내용을 위 `{YOUR_DOMAIN_EXAMPLE_*}` 에 넣어라.
예시가 구체적일수록 성능이 높아짐 (Anthropic 측정: 54% 향상).

### StockClaw 예시
```
요청: 사용자가 특정 코인 알림 설정 변경 요청
- 필요 확인: user_id, coin_symbol, alert_type, threshold_value
- 규칙 체크:
  * alert_type이 허용 목록(price_above, price_below, volume_spike)에 있는가?
  * threshold_value가 해당 타입의 유효 범위인가?
  * 동일 코인에 동일 타입 알림이 이미 존재하는가?
  * 사용자의 알림 한도(최대 20개)를 초과하는가?
- 계획:
  1. 현재 사용자 알림 목록 조회
  2. 중복/한도 확인
  3. 유효성 검증 통과 시 업데이트 실행
  4. 실패 시 구체적인 이유와 함께 거절
```

### ClawGene 예시
```
요청: Brain NFT 마이닝 상태 업데이트 요청
- 필요 확인: wallet_address, nft_token_id, epoch_number
- 규칙 체크:
  * NFT가 해당 지갑 소유인가?
  * 현재 epoch이 마이닝 활성 상태인가?
  * 이미 이번 epoch에 클레임했는가?
  * Halving 계산: 현재 epoch의 보상량은?
- 계획:
  1. NFT 소유권 온체인 확인
  2. Epoch 상태 조회
  3. 클레임 이력 확인
  4. 보상량 계산 후 트랜잭션 실행
```

---

## API 호출 시 tools 배열 예시

```typescript
// TypeScript — API 직접 호출 시
const response = await anthropic.messages.create({
  model: "claude-sonnet-4-6",
  max_tokens: 8096,
  system: `[위 system prompt 내용]`,
  tools: [
    {
      name: "think",
      description: "...",  // 위 정의 참고
      input_schema: { ... }
    },
    // ... 기타 툴
  ],
  messages: [{ role: "user", content: userMessage }],
});
```

```python
# Python — API 직접 호출 시
response = anthropic.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8096,
    system="[위 system prompt 내용]",
    tools=[
        {
            "name": "think",
            "description": "...",
            "input_schema": { ... }
        },
        # ... 기타 툴
    ],
    messages=[{"role": "user", "content": user_message}],
)
```

---

## 언제 think 툴을 끄는가

다음 경우엔 tools 배열에서 제거해서 토큰 절약:
- 단순 텍스트 생성 작업
- 단일 툴 호출로 완결되는 작업
- 제약 조건이 없는 CRUD 작업
