# SCPC 2026 AI Agent Harness

> 2026 Samsung Collegiate Programming Challenge: AI Challenge  
> Round 1 participant · Best public leaderboard score: **0.8054**

사용자 요청, 기기 상태, 대화 이력, 메모리와 안전 신호를 해석해 실행 계획을
구조화된 JSON으로 생성하는 결정론적 AI Agent Harness입니다.

A deterministic AI Agent Harness that interprets user requests, device state,
conversation history, memory, and safety signals to produce structured action
plans.

## Problem

The harness must consistently answer six questions without external APIs or a
large language model:

1. Which object is the current focus?
2. Where should the action be routed?
3. Should it proceed, be amended, be held, or ask for clarification?
4. Which information may be used or must be excluded?
5. Which safety and privacy policies apply?
6. In what order should the agent read, verify, redact, dispatch, or update?

## Approach

- **Context-grounded focal resolution** — resolves marker chains and semantic
  references in visible history instead of relying on object order.
- **Safety-aware control policy** — separates local updates from external
  disclosure and distinguishes `proceed`, `amend`, `hold`, and `ask`.
- **Deterministic routing** — combines explicit target changes, resolved
  targets, and session state with conservative fallbacks.
- **Minimal-disclosure planning** — builds content scopes, risk flags, and
  ordered plan events for sensitive operations.
- **Session memory** — carries forward only confirmed state to limit error
  propagation.
- **Generalization checks** — used ablation tests and leave-one-source-out
  validation to detect rules that only memorized public examples.

## Result

| Evaluation | Result |
|---|---:|
| SCPC 2026 Round 1 best public leaderboard score | **0.8054** |
| Public score improvement across iterations | **0.5506 → 0.8054 (+0.2548)** |
| External model/API calls at inference | **0** |
| Implementation | Python standard library |

The best public leaderboard score is not a final or private ranking. I participated
in Round 1 and did not advance to the next round.

## Repository Structure

```text
.
├── src/
│   └── harness.py                 # Final submitted harness
├── experiments/
│   ├── harness_v5_pure_core.py    # Reduced rule-core experiment
│   ├── harness_v6_B_session.py    # Session-state experiment
│   └── harness_v8_carryover_precond.py
├── docs/
│   └── design_notes.md            # Ablations, failure analysis, decisions
└── tests/
    └── test_harness_smoke.py       # Synthetic schema smoke test
```

## Validation

Run the repository-safe smoke test:

```bash
python -m unittest discover -s tests -v
```

The official competition dataset, reference answers, baseline notebook, and
submission CSV files are intentionally not redistributed. Reproducing the
competition evaluation requires the official data package from the organizer.

## What I Learned · 배운 점

이 프로젝트를 통해 에이전트 성능이 모델 크기만으로 결정되지 않는다는 점을
실험했습니다. 모호한 참조 해소, 동의 상태, 외부 공유 경계, 최소 공개 원칙과
실행 순서를 명시적으로 모델링하면서 안전한 에이전트 로직을 설계했습니다.

This work showed me that reliable agent behavior depends on the surrounding
control system, not only on model size. The implementation makes reference
resolution, consent state, external-sharing boundaries, minimal disclosure,
and action ordering explicit and auditable.

## Limitations

- Some semantic rules remain tailored to Korean instruction patterns.
- Public-development examples may not represent the hidden evaluation
  distribution.
- A deterministic policy improves auditability but can miss novel language
  outside its rule coverage.

## Attribution

Designed and implemented independently by
[Jang Hyeonseo](https://github.com/hseo1o2). Competition names and trademarks
belong to their respective owners.
