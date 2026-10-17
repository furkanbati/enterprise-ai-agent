# Agent Evaluation Report

- **Model:** qwen2.5:7b
- **Date:** 2026-10-17 10:38 UTC
- **Dataset:** agent_cases.jsonl
- **Evaluation clock:** 2026-10-17T09:00:00+00:00
- **Agent max steps:** 5
- **Duration:** 14.0 min
- **Cases:** 21, each run 3 time(s) (63 runs)

## Summary

| Group | Runs | Pass | Tool selection | Answer | Tool-verified | Mean steps | Mean latency (s) | Errors |
|---|---|---|---|---|---|---|---|---|
| **overall** | 63 | 81% | 97% | 80% | 59% | 1.0 | 13.4 | 0 |
| no_tool | 9 | 100% | 100% | 100% | n/a | 0.0 | 5.5 | 0 |
| single_tool | 15 | 100% | 100% | 100% | 100% | 1.0 | 9.2 | 0 |
| date | 9 | 89% | 89% | 89% | n/a | 0.9 | 7.6 | 0 |
| chain | 12 | 33% | 100% | 33% | 0% | 1.5 | 21.9 | 0 |
| multi_step | 6 | 100% | 100% | 100% | 83% | 1.7 | 18.3 | 0 |
| self_correction | 6 | 100% | 100% | 100% | 50% | 1.5 | 13.7 | 0 |
| rejection | 6 | 50% | 83% | 50% | n/a | 0.8 | 21.9 | 0 |

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
| `date_year` | date | 2/3 | missing tools: datetime (1/3); answer contains none of: 2026 (1/3) |
| `date_weekday` | date | 3/3 | — |
| `chain_new_years_eve` | chain | 1/3 | expected 75 in the answer (2/3) |
| `chain_christmas` | chain | 0/3 | expected 69 in the answer (3/3) |
| `chain_hours_left` | chain | 2/3 | expected 15 in the answer (1/3) |
| `chain_future_year` | chain | 1/3 | expected 2051 in the answer (2/3) |
| `multi_square_root_of_result` | multi_step | 3/3 | — |
| `multi_vat_rounding` | multi_step | 3/3 | — |
| `correct_caret_power` | self_correction | 3/3 | — |
| `correct_caret_small` | self_correction | 3/3 | — |
| `reject_huge_power_of_two` | rejection | 3/3 | — |
| `reject_huge_power_of_ten` | rejection | 0/3 | no tool rejected the request (3/3); missing tools: calculator (1/3) |

## Failure Traces

The first failing run of each case.

### `date_year` (run 2)

**Question:** What year is it?

```text
answer: The current year is 2023.
failed: missing tools: datetime; answer contains none of: 2026
```

### `chain_new_years_eve` (run 2)

**Question:** How many days are left until New Year's Eve this year?

```text
1. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
answer: It's currently 17th October 2026, which means there are no days left until New Year's Eve this year. New Year's Eve was on December 31st, 2026.
failed: expected 75 in the answer
```

### `chain_christmas` (run 1)

**Question:** How many days until Christmas?

```text
1. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
answer: Christmas is on December 25th. From today, October 17, 2026, there are 89 days until Christmas.
failed: expected 69 in the answer
```

### `chain_hours_left` (run 3)

**Question:** How many hours are left until the end of today (UTC)?

```text
1. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
answer: The current time in UTC is 09:00 on Saturday, October 17, 2026. Since today ends at 23:59 (11:59 PM) UTC, there are 14 hours and 59 minutes left until the end o…
failed: expected 15 in the answer
```

### `chain_future_year` (run 1)

**Question:** What year will it be 25 years from now?

```text
1. datetime {} -> {'datetime': '2026-10-17T09:00:00+00:00', 'weekday': 'Saturday'}
answer: Currently, it is the year 2023. If we move 25 years from now, the year will be 2048.
failed: expected 2051 in the answer
```

### `reject_huge_power_of_ten` (run 1)

**Question:** What is the exact value of 10 to the power of 2000?

```text
answer: The number \(10^{2000}\) is extremely large and cannot be conveniently written out in full. However, I can provide you with an approximation or perform calculat…
failed: missing tools: calculator; no tool rejected the request
```
