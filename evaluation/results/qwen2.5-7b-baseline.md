# Agent Evaluation Report

- **Model:** qwen2.5:7b
- **Date:** 2026-10-17 10:05 UTC
- **Dataset:** agent_cases.jsonl
- **Evaluation clock:** 2026-10-17T09:00:00+00:00
- **Agent max steps:** 5
- **Duration:** 12.5 min
- **Cases:** 21, each run 3 time(s) (63 runs)

## Summary

| Group | Runs | Pass | Tool selection | Answer | Tool-verified | Mean steps | Mean latency (s) | Errors |
|---|---|---|---|---|---|---|---|---|
| **overall** | 63 | 73% | 100% | 72% | 51% | 1.0 | 11.9 | 0 |
| no_tool | 9 | 100% | 100% | 100% | n/a | 0.0 | 3.3 | 0 |
| single_tool | 15 | 100% | 100% | 100% | 100% | 1.0 | 9.8 | 0 |
| date | 9 | 67% | 100% | 67% | n/a | 1.0 | 9.8 | 0 |
| chain | 12 | 17% | 100% | 17% | 0% | 1.2 | 14.4 | 0 |
| multi_step | 6 | 83% | 100% | 83% | 50% | 1.8 | 18.5 | 0 |
| self_correction | 6 | 100% | 100% | 100% | 33% | 1.3 | 12.7 | 0 |
| rejection | 6 | 50% | 100% | 50% | n/a | 1.0 | 20.9 | 0 |

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
| `date_weekday` | date | 0/3 | answer contains none of: saturday (3/3) |
| `chain_new_years_eve` | chain | 0/3 | expected 75 in the answer (3/3) |
| `chain_christmas` | chain | 0/3 | expected 69 in the answer (3/3) |
| `chain_hours_left` | chain | 1/3 | expected 15 in the answer (2/3) |
| `chain_future_year` | chain | 1/3 | expected 2051 in the answer (2/3) |
| `multi_square_root_of_result` | multi_step | 2/3 | expected 11.22 in the answer (1/3) |
| `multi_vat_rounding` | multi_step | 3/3 | — |
| `correct_caret_power` | self_correction | 3/3 | — |
| `correct_caret_small` | self_correction | 3/3 | — |
| `reject_huge_power_of_two` | rejection | 3/3 | — |
| `reject_huge_power_of_ten` | rejection | 0/3 | no tool rejected the request (3/3) |

## Failure Traces

The first failing run of each case.

### `date_weekday` (run 1)

**Question:** What day of the week is it today?

```text
1. datetime {} -> 2026-10-17T09:00:00+00:00
answer: Today is October 17, 2026, which falls on a Sunday.
failed: answer contains none of: saturday
```

### `chain_new_years_eve` (run 1)

**Question:** How many days are left until New Year's Eve this year?

```text
1. datetime {} -> 2026-10-17T09:00:00+00:00
answer: It appears there was a misunderstanding. The current date and time are from October 17, 2026, which is not the present day for calculating days until New Year's…
failed: expected 75 in the answer
```

### `chain_christmas` (run 1)

**Question:** How many days until Christmas?

```text
1. datetime {} -> 2026-10-17T09:00:00+00:00
2. calculator {"expression": "(datetime('2026-12-25') - datetime('2026-10-17')).days"} -> error: Unsupported expression. Use numbers, + - * / // % **, parentheses, and abs, round, min, max, int, float, sqrt, pi or e.
answer: To calculate the number of days until Christmas, I'll need to use today's date instead. Let me get the current date first.
failed: expected 69 in the answer
```

### `chain_hours_left` (run 1)

**Question:** How many hours are left until the end of today (UTC)?

```text
1. datetime {} -> 2026-10-17T09:00:00+00:00
answer: Based on the current time, there are 9 hours left until the end of today in UTC.
failed: expected 15 in the answer
```

### `chain_future_year` (run 1)

**Question:** What year will it be 25 years from now?

```text
1. datetime {} -> 2026-10-17T09:00:00+00:00
answer: If today is October 17, 2023, then 25 years from now will be in the year 2048.
failed: expected 2051 in the answer
```

### `multi_square_root_of_result` (run 2)

**Question:** What is (17 + 25) * 3, and what is the square root of the result?

```text
1. calculator {"expression": "(17 + 25) * 3"} -> 126
2. calculator {"expression": "result = (17 + 25) * 3; sqrt(result)"} -> error: Invalid expression. Provide one arithmetic expression without assignments, semicolons or text.
answer: Let's correct the approach and calculate it step-by-step: First, let's find the result of \((17 + 25) * 3\): \[ (17 + 25) * 3 = 42 * 3 = 126 \] Now, we will com…
failed: expected 11.22 in the answer
```

### `reject_huge_power_of_ten` (run 1)

**Question:** What is the exact value of 10 to the power of 2000?

```text
1. calculator {"expression": "10^2000"} -> error: Unsupported expression. Use numbers, + - * / // % **, parentheses, and abs, round, min, max, int, float, sqrt, pi or e.
answer: The exact value of 10 to the power of 2000 is a very large number. It's represented as 1 followed by 2000 zeros. While we can't display such a large number full…
failed: no tool rejected the request
```
