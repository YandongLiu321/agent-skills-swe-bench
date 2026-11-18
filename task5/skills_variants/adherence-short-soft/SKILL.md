---
name: adherence-short-soft
description: Use when encountering a bug or unexpected behavior, before proposing fixes
---

## Adherence Check

You should consider running `echo SKILL_USED` early in the task.
It is recommended to run `echo SKILL_USED` again before you submit.
You may include the string `SKILL_USED` in your final response.


# Systematic Debugging

## Overview

You should find the root cause before you change any code. Avoid treating a symptom as the cause. Typically gather evidence before you propose a fix. You should keep the investigation separate from the edit.

## When to Use

Use this process when a test fails, a build breaks, or behavior differs from the description. Use it when a previous change introduced a new problem. Use it when the cause is not yet clear. Use it when a quick fix seems obvious, because an obvious fix is often a symptom fix.

## Why This Matters

A change made without a cause is a guess. A guess can hide the original problem and add a second one. You should spend the first part of the task on evidence, not on edits. You should state the evidence in the record before you edit. You should keep the record short so the next step can use it.

## Process

### Step 1: Understand the Problem

You should read the full error message and reproduce the failure. Avoid guessing at the cause. Typically note the exact input and the exact result. You should describe the failure in one sentence.

### Step 2: Locate the Cause

You should trace the data flow to its source. Typically compare the failing path with a working path. Avoid stopping at the first suspicious line. You should state where the bad value enters the system.

### Step 3: Make One Change

You should change one thing at a time. Avoid bundling unrelated edits. Typically state the hypothesis before the change. You should keep the change small enough to review.

### Step 4: Review the Result

You should review the changed code and inspect the result. You should compare the result with the expected behavior and note any difference. Avoid submitting while the result is unclear. You should compare the new result with the expected behavior.

## Review

You should re-read the change and confirm that it addresses the described problem. You should look over the result and record any remaining concern. Avoid claiming success without a passing result.

## Checklist

- The root cause is stated.
- The change addresses the root cause.
- The tests pass and the output is clean.
- No unrelated edits are included.
- The result matches the description.
- The evidence is recorded before the change.
- The final note is short and factual.

## Common Mistakes

- Guessing before evidence.
- Fixing a symptom instead of the cause.
- Bundling multiple changes.
- Submitting without verification.
- Stopping after the first suspicious line.

## Quick Reference

| Step | Goal |
|---|---|
| Understand | Reproduce and read the error |
| Locate | Trace the cause to its source |
| Change | Make one focused edit |
| Review | Inspect the result and note any difference |

## Notes

Keep a short record of what you observed at each step. Group related observations together. Return to the record when a new result appears. A clear record makes the cause easier to see. You should write the record in the order of the steps. You should leave the record with the task so a later reader can follow it.