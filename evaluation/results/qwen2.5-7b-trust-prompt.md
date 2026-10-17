# Agent Evaluation Report

- **Model:** qwen2.5:7b
- **Date:** 2026-10-17 11:17 UTC
- **Dataset:** agent_cases.jsonl
- **Evaluation clock:** 2026-10-17T09:00:00+00:00
- **Agent max steps:** 5
- **Duration:** 14.9 min
- **Cases:** 21, each run 3 time(s) (63 runs)

## Summary

| Group | Runs | Pass | Tool selection | Answer | Tool-verified | Mean steps | Mean latency (s) | Errors |
|---|---|---|---|---|---|---|---|---|
| **overall** | 63 | 89% | 95% | 88% | 64% | 1.0 | 14.2 | 0 |
| no_tool | 9 | 100% | 100% | 100% | n/a | 0.0 | 4.6 | 0 |
| single_tool | 15 | 100% | 100% | 100% | 100% | 1.0 | 10.2 | 0 |
| date | 9 | 100% | 100% | 100% | n/a | 1.0 | 7.7 | 0 |
| chain | 12 | 67% | 100% | 67% | 33% | 1.8 | 26.2 | 0 |
| multi_step | 6 | 100% | 100% | 100% | 67% | 1.3 | 16.1 | 0 |
| self_correction | 6 | 100% | 100% | 100% | 33% | 1.3 | 12.6 | 0 |
| rejection | 6 | 50% | 50% | 50% | n/a | 0.5 | 24.4 | 0 |

- **Pass:** tool selection and answer checks both passed.
- **Answer:** answer accuracy, over runs whose case defines an answer check.
- **Tool-verified:** the expected number was produced by a tool rather than stated by the model, over cases with a numeric answer.

## Cases

| Case | Category | Passed | Failure reasons |
|---|---|---|---|
| `no_tool_greeting` | no_tool | 3/3 | — |
| `no_tool_capital` | no_tool | 3/3 | — |
| `no_tool_definition` | no_tool | 3/3 | — |
| `calc_percentage` | single_tool | 3/3 | — |
| `calc_multiplication` | single_tool | 3/3 | — |
| `calc_square_root` | single_tool | 3/3 | — |
| `calc_parentheses` | single_tool | 3/3 | — |
| `calc_division` | single_tool | 3/3 | — |
| `date_today` | date | 3/3 | — |
| `date_year` | date | 3/3 | — |
| `date_weekday` | date | 3/3 | — |
| `chain_new_years_eve` | chain | 3/3 | — |
| `chain_christmas` | chain | 1/3 | expected 69 in the answer (2/3) |
| `chain_hours_left` | chain | 1/3 | expected 15 in the answer (2/3) |
| `chain_future_year` | chain | 3/3 | — |
| `multi_square_root_of_result` | multi_step | 3/3 | — |
| `multi_vat_rounding` | multi_step | 3/3 | — |
| `correct_caret_power` | self_correction | 3/3 | — |
| `correct_caret_small` | self_correction | 3/3 | — |
| `reject_huge_power_of_two` | rejection | 3/3 | — |
| `reject_huge_power_of_ten` | rejection | 0/3 | missing tools: calculator (3/3); no tool rejected the request (3/3) |

## Failure Traces

The first failing run of each case.

### `chain_christmas` (run 1)

**Question:** How many days until Christmas?

```text
1. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
2. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
3. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
4. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
5. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
answer: It seems there was an issue with the tool call. The last response from the datetime tool indicates that today's date is 2026-10-17 (Saturday). Since Christmas i…
failed: expected 69 in the answer
```

### `chain_hours_left` (run 2)

**Question:** How many hours are left until the end of today (UTC)?

```text
1. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
answer: According to the current UTC time, there are 3 hours left until the end of today. The exact timestamp is 2026-10-17T09:00:00+00:00, which means it will be 12:00…
failed: expected 15 in the answer
```

### `reject_huge_power_of_ten` (run 1)

**Question:** What is the exact value of 10 to the power of 2000?

```text
answer: The number \(10^{2000}\) is extremely large and cannot be practically represented in standard numerical formats due to its size. However, I can provide you with…
failed: missing tools: calculator; no tool rejected the request
```
