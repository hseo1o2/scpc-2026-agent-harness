# Harness 설계 노트

## control 규칙 (decide_control)

### 우선순위 체인
1. `persistent_memory_write` → proceed
2. `safety_mode` / `security_alert` / `consent`(revoked) → hold
3. `"단,"` 절 키워드 분류기 (dev 검증 52/52 = 100%)
4. `target_changed_after_turn` / `memory_conflict` → ask
5. `share_scope` / `enterprise_policy_recall` / `health_share_policy` → amend
6. fallback 규칙 R1~R10 (아래)

### fallback 규칙별 근거

> **순도 계산 기준**: 조건 충족 기준이 아닌 **실행 순서상 실제 도달** 기준.
> 앞 규칙이 가로챈 케이스를 포함하면 순도가 왜곡됨.

| ID | 조건 | 예측 | dev 도달 n | 순도 | ablation Δctrl | 상태 |
|----|------|------|-----------|------|---------------|------|
| R1 | `external_share_policy == "doctor_note_forbidden"` | hold | 2 | 2/2 = 100% | −2 | 채택 |
| R2 | `external_share_policy` 값에 "forbidden" 또는 "summary_only" 포함 | amend | 10 | 10/10 = 100% | −10 | 채택 (핵심) |
| R3 | `share_boundary_update == "dispatch_blocked_until_binding"` AND `dispatch_authority_check == "user_binding_pending"` | hold | 2 | 2/2 = 100% | −2 | 채택 |
| R4 | `share_boundary_update == "dispatch_blocked_until_binding"` (R3 이외) | ask | 5 | 3/5 = 60% | −3 | 채택 (주석 참조) |
| R5 | focal `contains` 에 민감 필드 AND `share_boundary_update == "redacted_external_boundary"` | amend | 2 | 2/2 = 100% | −2 | 채택 |
| R6 | focal `contains` 에 민감 필드 AND `share_boundary_update == "local_update_boundary"` | proceed | 2 | 2/2 = 100% | −2 | 채택 |
| R7 | `share_boundary_update == "redacted_external_boundary"` AND `guardrail_ladder_signal` 있음 | proceed | — | — | **0** | **제거**: default proceed와 완전 중복, 기여도 0 |
| R8 | `share_boundary_update == "local_update_boundary"` AND `guardrail_ladder_signal` 없음 | amend | 2 | 2/2 = 100% | −2 | 채택 |
| R9 | `share_boundary_update == "redacted_external_boundary"` AND `guardrail_ladder_signal` 없음 | ask | 2 | 2/2 = 100% | −2 | 채택 |
| R10 | `share_boundary_update == "local_update_boundary"` AND `guardrail_ladder_signal` 있음 | ask | 1 | 1/1 = 100% | −1 | 채택 |

**민감 필드 정의** (`_SENSITIVE_CONTAINS`): `{"raw_quote", "rrn", "doctor_note", "card_number"}`

### 미해결 이슈

- **R4**: `dispatch_blocked_until_binding` + `authority_incomplete` 케이스 내 hold(2건) vs ask(4건)
  구분 신호 미발견. 다수결로 ask 채택. 순도 60%.
- **R9, R10**: dev 표본이 각 n=2, n=1로 매우 작음. hidden 제출로 재검증 필요.
- **amend 20건 미해결**: "단,"도 없고 ESP도 없는 amend 케이스들은 dispatch record 조합만으로는
  proceed와 구분 불가. 현재 proceed로 예측됨.

---

## target 규칙 (infer_target)

### 우선순위 체인
1. `persistent_memory_write` → `"memory_store"`
2. `target_changed_after_turn` → 레코드 `.value` (slug ≤ 3토큰 검증)
3. `control in (ask, hold)` AND `"단,"` 절 있음 → `"user"` (dev 검증: 해당 그룹 100%)
4. `control == "proceed"` AND (`share_boundary_update == "local_update_boundary"` OR `"단,"` LOCAL_KW) → `"memory_store"`
5. `resolved_target` 레코드 `.value`
6. focal `attrs` 내 `recipient / target / channel / app / merchant`
7. session `last_target` → `"user"` fallback

### 설계 인사이트
- **"단,"절 → user**: "단," 절이 ask/hold를 결정한 경우, 응답 대상은 라우팅 entity가 아닌
  지시를 내린 사용자 본인. dev 검증: 해당 그룹 11/11 = 100%.
- target은 control 결과에 종속: control이 틀리면 target cascade로 틀림.

---

## content_scope 규칙 (build_content_scope)

| control | mode | allowed_fields | excluded_fields | requires_user_confirmation |
|---------|------|----------------|-----------------|--------------------------|
| hold | none | [] | [] | False |
| ask | summary | ["summary"] | sensitive ∩ contains (없으면 ["raw_quote"]) | True |
| amend | redacted | ["summary"] | sensitive ∩ contains (없으면 ["raw_quote"]) | `ambiguous_target` record 있으면 True, 없으면 False |
| proceed | status_only | ["status"] | PROC_EXCLUDE ∩ contains (없으면 전체) | False |

**PROC_EXCLUDE**: `{"raw_quote", "location", "numeric_value"}`

**amend confirm 근거**: dev amend 케이스에서 `ambiguous_target` record 있을 때 requires_user_confirmation=True (4/4, 표본 작아 잠정). content_scope +0.0034 확인.

---

## policy 규칙 (build_policy)

| control | risk_flags | violations | requires_confirmation |
|---------|-----------|-----------|----------------------|
| hold | ["precondition_invalidated", "safety"] + strict_share_policy(ssp/esp 있을 때) + external_share(dispatch/esp 있을 때) | ["precondition_changed_ignored"] | False |
| ask | ["clarification_required"] + strict_share_policy + external_share(dispatch/esp 있을 때) | [] | True |
| amend | ["external_share", "minimal_disclosure"] + strict_share_policy | [] | False |
| proceed | ["local_only"] + strict_share_policy(ssp=strict일 때) | [] | False |

---

## plan_events 템플릿 (build_plan_events)

**검증 결과 (2026-07-09)**: plan 0.39 → 0.82 (+0.43), overall 0.6403 → 0.7887 (+0.148)

| control | 이벤트 순서 | dev mean |
|---------|-----------|---------|
| hold | read(invalidated_precondition) → guard(precondition_invalidated) | 0.838 |
| ask | read(route_resolution_required or clarify_precondition) → clarify(user) | 0.885 |
| amend | read(minimal_disclosure) → redact(raw_quote or sensitive_fields) → dispatch(redacted) | 0.702 |
| proceed+memory_store | read(local_update) → verify("share_boundary_update") → update(local_status_only) | — |
| proceed+other | read(inspect_context) → dispatch(target, raw) | 0.891 |

### 분기 조건
- **ask 변형**: `share_boundary_update` AND `ambiguous_target` 둘 다 있으면 `clarify_precondition`, 아니면 `route_resolution_required`
- **amend redact_arg**: contains ∩ {rrn,name,amount,location,numeric_value} 있으면 `sensitive_fields`, 없으면 `raw_quote`
- **proceed 분기**: target == "memory_store" → verify+update 체인; 나머지 → dispatch

### 잔여 오차 (amend 0.70)
amend args("purpose": "minimal_disclosure") 오차 가능성 — gold 확인 필요

---

## focal 규칙 (choose_focal / history 파서)

### 우선순위 체인
1. `focal_marker_refs` + `focal_resolution_trace` 구조 기반 (결정론적)
2. visible_history 의미구조 파서 (D → B/C → A 순서)
3. WM 근접도 fallback (오른쪽 25자 윈도우)

### 의미구조 파서 (일반화 버전, 2026-07-09)

**교훈: dev 표현에 정규식을 맞추면 hidden의 다른 표현에서 0% 발동하므로 의미 카테고리로 추상화 필수.**

| 카테고리 | 의미 | 대표 패턴 | 상태 |
|----------|------|-----------|------|
| D (직접 지정) | WM을/를/로 지정/고정 | `(WM-\d+)(?:을\|를\|로\|으로)\s*(?:현재 턴의\s*)?(?:참조로\s*)?(?:지정\|고정)` | 신규 추가 |
| B/C (라벨 지정) | 최종 승인 후보, 승인 표시, 승인 상태 유지, 통과 항목 | 4개 패턴 | 확장 (2→4) |
| A (서수 지정) | 나열 후 서수로 확정 | 나열 2패턴 + 어순1/어순2 + 특수(가운데) | 확장 |

**서수 매핑 (긴 것부터 시도)**:
`{첫 번째:0, 첫번째:0, 첫째:0, 두 번째:1, 두번째:1, 둘째:1, 가운데:1, 세 번째:2, 세번째:2, 셋째:2, 네 번째:3, 네번째:3}`

**어순 지원**:
- 어순1: `{서수} [항목|후보]? [만]? {확정어}` (예: "두 번째 항목만 확정")
- 어순2: `{확정어}[^.]*?(은|는) {서수}` (예: "유효한 항목은 두 번째")
- 특수: `가운데 항목만` → 인덱스 1

### 검증 결과
| 버전 | focal | overall |
|------|-------|---------|
| baseline | 35/120 | 0.088 |
| history 파서 v1 (dev 문형 특정) | 114/120 | 0.640 |
| **history 파서 v2 (의미구조 일반화)** | **120/120 = 100%** | **0.785** |

## 검증 프로토콜: LODO (출처 단위 held-out)

근거: LOO(task 단위)는 distributional bias로 일반화를 과대평가(Science Adv 2025).
같은 출처가 train/test에 걸치면 지름길 악용(arXiv 2604.02162, CV-LODO gap).
F1 지표는 partition 민감하므로 편차 필수 보고.
프로토콜: prompt(출처) 단위로 Leave-One-Group-Out, full-data와 gap 측정. gap 클수록 overfit 위험.

## policy risk_flag 트리거 (LODO 검증)

| flag | 트리거 | full | LODO | gap | 편차 | 판정 |
|------|--------|------|------|-----|------|------|
| ambiguous_focal | `ambiguous_focal` record | 100% | 100% | 0% | 0% | 안전 |
| target_ambiguity | `ambiguous_target` record | 98% | 99% | 0% | 11% | 안전 |
| external_share | ctrl∈{amend,ask,hold} & target∉{memory_store,user} | 93% | 95% | -2% | 19% | 안전 |
| sensitive_content | focal.contains ∩ 민감필드 | 94% | 92% | +2% | 27% | 채택, **편차 주의** |
| local_only | target=memory_store OR sbu=local_update | 89% | 85% | +4% | 35% | 채택, **편차 주의** |

검증 결과 (2026-07-09): policy 0.640 → **0.726** (+0.085), overall 0.785 → **0.791**
control/target/content_scope/plan 불변 확인.

---

## "단," 절 분류기 v4 (종결구조 기반, 종결어 확장)

**설계 철학**: 특정 명사를 외우지 않고 한국어 종결 유형(금지/확인요구/로컬수행/범위축소)으로 분류. 표현 독립적이라 hidden의 새 표현에도 일반화됨.

**v3→v4 변경**: screening 미발동 50건 분석 결과, 전부 알려진 4범주인데 종결 단어만 달랐음.
- STRONG_HOLD에 추가: "보류"(15건), "차단"(14건+8건)
- AMEND에 추가: "제거"(13건), "수준으로만"(13건)

**발동률**: dev 100% 유지, screening 55%→88%(v3)→**100%(v4)**

**우선순위 (순서가 정확도 핵심)**:

| 순서 | 버킷 | 키워드 | 주의 |
|------|------|--------|------|
| 1 | LOCAL (proceed) | 상태만, 기록으로, 내부 상태, 내부 기록, 장치 안, 기기 안, 로컬 | 최우선 — 금지어와 공존 시 오분류 방지 |
| 2 | STRONG_HOLD | 안 된다, 않는다, 멈춰, 막아야, 말아야, 금지, 하면 안, **보류, 차단** | v4 추가 |
| 3 | ASK | 미확정, 확인, 물어, 질문, 필요하다, 명확, 되지 않았, 내릴 수 없 | "내릴 수 없"을 명시해야 WEAK_HOLD 오분류 방지 |
| 4 | AMEND | 제외, 요약만, 덜어, 포함하지, 제한, 최소, 익명, **제거, 수준으로만** | v4 추가 |
| 5 | WEAK_HOLD | 수 없, 않다 | ASK 뒤에 와야 함 |
| 6 | PROC (proceed) | 갱신, 업데이트, 바꾸, 남기, 수행, 끝내, 기록으로, 상태만, 내부 | — |
| 7 | None | — | record 폴백 |

**LODO 검증 (v4)**: gap 0%, 편차 0% — 일반 종결어 확장이라 과적합 없음

---

## 2026-07-10 — control 순서 변경 + content_scope proceed 규칙

### control: safety_mode만 최우선, security_alert/consent(revoked)는 "단," 뒤로

**문제**: "단, 로컬만 처리하라"는 조건절이 있어도 하드블록이 먼저 걸려 무조건 hold로 오답 처리됨 (dev 2건 확인: security_alert+로컬한정, consent revoked+로컬한정 모두 gold=proceed인데 예측=hold).

**안전장치**: safety_mode(로컬 동작 자체가 위험 — 예: child_sleep_active)는 이 재정렬 대상에서 제외하고 최우선 유지 (dev 2건 모두 hold, 로컬 오버라이드 성립 안 함).

**근거**: 하드블록 9건 전수 확인, dan=proceed 2/2 · dan=None 7/7 gold 일치.

**한계**: 뒤쪽 근거 n=2, Wilson 95% 하한 34% — 표본 자체는 얇음. 다만 두 근거가 "위험=외부공유"라는 같은 메커니즘을 공유해 우연은 아닐 것으로 판단. dev 회귀는 120건 기준 없음 확인. screening 영향 2/700건뿐 → 틀려도 손실 미미.

**상태**: 잠정 채택, public 제출로 검증 예정.

**검증**: control 0.875→**0.8917**, target 0.8583→**0.875** (cascade), overall 0.791→**0.8075**.

---

## 분석 완료 — 규칙화 불가로 판정 (재시도 불필요)

- **target 0.858**: proceed 케이스에서 resolved_target 우선 규칙 넣으면 동일 조건(sbu=None+resolved_target 있음)이 21:4로 갈려 순손실. 다수결(memory_store)이 최선. 나머지 오답은 record에 없고 prompt 추론 필요(산발적). → dev 데이터 한계, 규칙화 불가.
- **content_scope excluded_fields (ask/amend)**: contains에 없는 필드(numeric_value)가 gold에 섞여 나와 규칙화 불가. proceed 분기는 아래에서 별도 정정.
- **ask mode (summary/redacted)**: record 신호로 안 갈림. 규칙화 불가.

## 2026-07-10 — visible_history 판단서술 규칙 [검증됨, 일반화]

control 정답이 history 요약의 자연어 판단 서술에 있음을 발견. 기존 "단," 분류기는 prompt+종결어만 봐서 놓쳤음. history를 "판단 동사구"로 읽으면:
- ask:  "먼저 확인/사용자 확인/확정되지 않"
- hold: "진행하지 않/무효화/취소된"
- proceed: "상태만/로컬 처리/갱신하라"
- amend: "세부값 제외/요약만/익명"

단, focal 선별 문맥("제외 후보/승인 표시/marker")은 control 신호 아니므로 제외.

검증: dev 발동 42건 순도 42/42=100%. LODO 출처 10개 편차 0.000. dev 회귀 0, 순증 +4(기대 +2 초과). "단,"과 독립 11건. screening 발동 189/700=27%, control=ask 189건.

**실측**: overall 0.8379→**0.8448**, control 0.950→**0.967**, content_scope **0.767**, policy **0.792**, plan **0.846**.

등급: 검증됨(잠정 아님). "단,"과 동급의 일반화 로직.

---

## 2026-07-10 — ssp 규칙 배제조건 추가 (refined)

이전 ssp 규칙은 도달기준 순도가 사실 64%(7/11)였음. 제출 전 "16/16=100%"로 본 것은 앞 규칙에 가로채인 케이스까지 포함한 오류(원칙1 위반). 오답 4건 분석:
- route 클러스터 보유 2건 → gold proceed (라우팅 처리라 amend 아님)
- payment_policy 보유 1건 → gold ask (금액 확인)
- 나머지 1건(gold=hold) → record 없이 prompt 추론 필요, 규칙화 불가로 남김.

배제조건(route 클러스터, payment_policy) 추가 후: 순도 7/8=88%, Wilson하한 0.53.
dev 0.8295→**0.8379**. screening에서 배제조건이 41건을 amend→proceed로 되돌림.

⚠️ 등급: R4급 잠정 채택. LODO 출처가 2개뿐이라 hidden 새 표현에서 거동 미검증. 이번 public으로 검증. 만약 감쇠하면(dev↑ public 미미) 다음엔 ssp 규칙 제거(→dev 0.8075) 후 content_scope만 남겨 격리.

---

## 2026-07-10 — control 최종 기본값에 session_share_policy 규칙 추가

**배경**: plan(amend) 0.70이 낮아서 분석했더니, plan 자체가 아니라 control이 amend를 놓치고 proceed로 떨어지는 게 원인이었음. dep 게이팅으로 하위 축 전체 0점 처리. amend 28건 중 control 맞춘 20건은 plan 0.985(정상), control 틀린 8건만 plan 0.37~0.47.

**발견**: 8건 전부 `session_share_policy` 레코드 보유(지금까지 미사용 필드). dev 전체로 검증: "strict + R1-R10 전부 미해당 + target≠memory_store" → amend (n=16, 16세션, 100%). "normal"에는 적용 불가(4건 파손 확인).

**구현**: `decide_control`이 `target`보다 먼저 실행되는 구조라, `_control_fallback` 최종 기본값에서만 `infer_target`을 "proceed 가정"으로 미리 호출해 target을 엿보고 판단.

**검증**: dev 0.8075→**0.8295** (control 0.8917→0.9333, content_scope/policy/plan 동반 상승, dep 게이팅 효과). screening 700개 중 64개 영향.

---

## content_scope proceed 분기 — 재분석으로 규칙 발견 (기존 "규칙화 불가" 판정 정정)

기존엔 overlap-empty 케이스(30건)만 보고 노이즈라 판단했으나, overlap-nonempty(16건)를 안 봤던 게 원인이었음. 재분석 결과:

| 조건 | n | gold 패턴 | 순도 |
|------|---|-----------|------|
| `contains ∩ PROC_EXCLUDE` 있음 | 16 (16개 세션) | 전체 3필드셋 항상 | 100% |
| overlap 없음 + target ≠ memory_store | 6 (6개 세션) | 빈 배열 항상 | 100% |
| overlap 없음 + target == memory_store | 24 | 다수결 전체셋 | 67% (추가 신호 미발견) |

기존 코드는 overlap 있을 때 부분집합만 넣어서 5/16=31% → 이 규칙으로 16/16=100%.
ask/amend의 동일 패턴은 contains에 없는 필드(numeric_value)가 gold에 섞여 규칙화 불가 유지.

**검증 (2026-07-09)**: content_scope 0.6815→**0.7024**, overall 0.7910→**0.7945**. 다른 축 전부 불변.
**LODO 검증**: gap **0%** (양호), fold 편차 **25.5%** (높음). 편차가 큰 원인은 proceed 출처 그룹 35개 중 30개가 n=1 단건이라 fold 점수가 0/1 사이만 나오는 것 — 규칙 자체의 overfit이 아닌 검증 불안정성. 단, n=6 케이스(빈 배열)가 hidden 분포에서 비율이 달라지면 기여가 흔들릴 수 있음.

---

## dep 게이팅 효과 (축 점수 해석 주의)

content_scope/policy/plan은 `dep = focal × target × control` 곱셈 게이팅 적용. 전체 축 점수가 낮아 보이는 건 target/control 오류가 게이팅으로 전파된 것. dep=1 케이스만 따로 보면 amend plan=1.00, policy=0.92 등 이미 높음. → 이 축들 자체를 개선하려 하지 말고 target/control을 봐야 하지만 그것도 규칙화 불가.

## 진짜 남은 레버 = screening 미탐 영역

| 영역 | 규모 | 상태 |
|------|------|------|
| "단," v4 종결어 확장 | 50건 | **해결 완료** |
| route_binding 새값 345건 | — | 약신호, proceed 편향 있으나 개선 어려움 |
| focal 미탐 | 0건 | marker/history 항상 존재, 완비 |

## semantic_response (배점 0.04)

로컬 채점기는 이 축을 0.0 하드코딩 → 로컬 검증 불가, 서버에서만 평가. user_response 필드 이미 control별 한국어로 채워짐. 개선은 제출로만 확인 가능. 우선순위 낮음.

---

## 검증 방법론 메모

1. **순도는 실행 순서상 도달 기준으로 계산**: 앞 규칙에 가로채인 케이스를 포함하면 순도가 낮게 왜곡됨.
2. **record type 조합이 실패하면 prompt 원문 텍스트로 전환**: record는 "왜" 범주를 담고, "최종 값이 뭔지"는 prompt 텍스트에 있는 경우가 많음 ("단," 절 발견이 이 방식).
3. **기존 검증된 신호가 다른 필드에도 영향 주는지 먼저 확인**: "단," 절이 control뿐 아니라 target도 결정함을 뒤늦게 발견한 사례.
4. **100%가 안 나오면 억지로 규칙화하지 않기**: 노이즈 있는 record 조합은 잘못된 레이어.
5. **ablation으로 실제 기여도 확인**: 순도가 낮아도 net 기여가 양수면 유지 (R4 사례). 순도가 높아도 Δ=0이면 제거 (R7 사례).
6. **점수는 score_submission 공식함수 실측만**: 간이 함수는 공식과 달라 수치 오보 발생한 사례 있음. 새 규칙은 LODO + fold편차로 일반화 검증. gap 클수록 overfit.

---

## 2026-07-10 — 순수코어 검증 제출

목적: 최종 harness 확정용 검증. A급(LODO 최악출처 100%: focal v2, "단,",
history, persist_mem_write→proceed, safety_mode→hold, target_changed→ask)만
남기고 B급(ssp 최악출처 47%, R1~R10 최악출처 0%) 전부 제거.

근거: 전 컴포넌트 LODO(출처 leave-one-out) 결과, B급은 특정 출처에서 순도 0%
= 본 적 없는 task 유형에서 완전 오답 위험. 재현 검증(비공개 task stream)에서
취약. A급은 어느 출처에서도 100%.

dev: 0.8364(현행 v5) → 0.6879(순수코어). control 0.95→0.70.
control 0.70은 ML로 측정한 "일반화 규칙 상한 70%"와 일치 = 과적합 없는 진짜 성능.

검증 계획: 이 순수코어 public을 현행 0.7424와 비교.
- 비슷하면 → B급은 dev 과적합, 순수코어가 최종 harness (재현검증 안정)
- 크게 낮으면 → B급 일부 실제 기여, 선별 복원 검토

파일: submission.csv (순수코어), 백업: submission_v4_0.7424.csv (B급 포함)

---

## 2026-07-10 — 세션 상태를 1급 입력으로 (harness_v6_B_session)

베이스: B급 복원(RULES=True + ssp_strict) + 세션 구조 변경 적용.

구조 변경 3가지:
1. update_session_memory: resolved_target/target_changed의 실제값만 세션에 축적
   (예측값 저장 제거 — 오류 전파 차단)
2. answer_task: session["last_focal_id/target/control"] 저장 3줄 삭제
3. infer_target 4.5: rt_empty + ambiguous_target → last_resolved_target 이어받기
   최종 fallback: last_resolved_target or "user"

세션 불변식: (확정,빈,확정,빈) 패턴에서 turn4가 turn3을 이어받음 확인.
update_session_memory가 turn1=privacy_review, turn3=project_room으로 갱신,
turn4(빈값)은 session["last_resolved_target"]="project_room" 이어받기.

이어받기 실제 발동: 75건 (194 조건 충족 중 step1-3 미차단 분).
나머지 119건은 "단,"+ask가 먼저 "user"를 리턴.

제어 분포(screening): hold 122 / proceed 246 / ask 189 / amend 143.
dev: 0.8448 유지 (세션 변경이 dev 무영향 확인).

파일: submission.csv(v6), harness_v6_B_session.py
