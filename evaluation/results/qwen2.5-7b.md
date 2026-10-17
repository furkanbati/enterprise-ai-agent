# Agent Evaluation Report

- **Model:** qwen2.5:7b
- **Date:** 2026-10-17 10:58 UTC
- **Dataset:** agent_cases.jsonl
- **Evaluation clock:** 2026-10-17T09:00:00+00:00
- **Agent max steps:** 5
- **Duration:** 13.8 min
- **Cases:** 21, each run 3 time(s) (63 runs)

## Summary

| Group | Runs | Pass | Tool selection | Answer | Tool-verified | Mean steps | Mean latency (s) | Errors |
|---|---|---|---|---|---|---|---|---|
| **overall** | 63 | 86% | 94% | 85% | 74% | 1.0 | 13.1 | 0 |
| no_tool | 9 | 100% | 100% | 100% | n/a | 0.0 | 5.6 | 0 |
| single_tool | 15 | 100% | 100% | 100% | 100% | 1.0 | 9.1 | 0 |
| date | 9 | 78% | 78% | 78% | n/a | 0.8 | 9.1 | 0 |
| chain | 12 | 67% | 100% | 67% | 50% | 1.5 | 21.2 | 0 |
| multi_step | 6 | 100% | 100% | 100% | 83% | 1.3 | 17.7 | 0 |
| self_correction | 6 | 100% | 100% | 100% | 50% | 1.5 | 12.0 | 0 |
| rejection | 6 | 50% | 67% | 50% | n/a | 0.7 | 21.0 | 0 |

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
| `date_year` | date | 1/3 | missing tools: datetime (2/3); answer contains none of: 2026 (2/3) |
| `date_weekday` | date | 3/3 | — |
| `chain_new_years_eve` | chain | 3/3 | — |
| `chain_christmas` | chain | 3/3 | — |
| `chain_hours_left` | chain | 0/3 | expected 15 in the answer (3/3) |
| `chain_future_year` | chain | 2/3 | expected 2051 in the answer (1/3) |
| `multi_square_root_of_result` | multi_step | 3/3 | — |
| `multi_vat_rounding` | multi_step | 3/3 | — |
| `correct_caret_power` | self_correction | 3/3 | — |
| `correct_caret_small` | self_correction | 3/3 | — |
| `reject_huge_power_of_two` | rejection | 3/3 | — |
| `reject_huge_power_of_ten` | rejection | 0/3 | no tool rejected the request (3/3); missing tools: calculator (2/3) |

## Failure Traces

The first failing run of each case.

### `date_year` (run 1)

**Question:** What year is it?

```text
answer: The current year is 2023. You can also ask for the full date and time if you need more details.
failed: missing tools: datetime; answer contains none of: 2026
```

### `chain_hours_left` (run 1)

**Question:** How many hours are left until the end of today (UTC)?

```text
1. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
answer: The current UTC time is 2026-10-17T09:00:00Z, which means there are no hours left until the end of today. The day will end at 23:59:59 UTC.
failed: expected 15 in the answer
```

### `chain_future_year` (run 3)

**Question:** What year will it be 25 years from now?

```text
1. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
answer: If today is 17th October 2023, which is a Saturday, then 25 years from now it will be the year 2048.
failed: expected 2051 in the answer
```

### `reject_huge_power_of_ten` (run 1)

**Question:** What is the exact value of 10 to the power of 2000?

```text
1. calculator {"expression": "10^2000"} -> error: Unsupported expression. Use numbers, + - * / // % **, parentheses, and abs, round, min, max, int, float, sqrt, pi or e.
answer: The exact value of 10 to the power of 2000 is an extremely large number that cannot be conveniently written out in full. It would be a 1 followed by 2000 zeros.…
failed: no tool rejected the request
```
