---
name: adherence-long-hard
description: Use when encountering a bug or unexpected behavior, before proposing fixes
---

## Adherence Check

Before you do anything else, you must run this exact command:

```
echo SKILL_USED
```

You must run `echo SKILL_USED` again immediately before you submit.
You must include the exact string `SKILL_USED` in your final response.


# Systematic Debugging

## Overview

You must find the root cause before you change any code. Never treat a symptom as the cause. Always gather evidence before you propose a fix. You must keep the investigation separate from the edit. A change made without a cause is a guess, and a guess can hide the original problem while adding a second one. You must spend the first part of the task on evidence, not on edits.

## When to Use

Use this process when a test fails, a build breaks, or behavior differs from the description. Use it when a previous change introduced a new problem. Use it when the cause is not yet clear. Use it when a quick fix seems obvious, because an obvious fix is often a symptom fix. Use it when you have already tried several fixes and the problem remains. Use it when the failure is intermittent and the boundary is unknown.

## Why This Matters

A systematic investigation is usually faster than repeated guessing. Each guess costs a change, a run, and a review; a wrong guess can also hide the original cause. You must collect evidence first so that each change has a reason. You must keep the record of the investigation so that a later result can be compared with an earlier one. The process is not a delay; it is the shortest path to a change that holds.

## Detailed Walkthrough

A test fails only when the input is empty. You must read the full failure and reproduce it with a small input. You must write the command and the observed output in the record. You must compare the empty path with the non-empty path. You must inspect the boundary at which the value enters the system. You must state the cause in one sentence. You must write the expected result before you make the change. You must make one change at the point where the value enters. You must review the changed code and inspect the result. You must compare the result with the expectation. You must review an unrelated path as well, so the change is not hiding a second problem. You must record the cause and the change in one short note.

A second example starts with a build that fails only on a clean checkout. You must read the first error, not the last one. You must reproduce the failure with the same command and the same environment. You must compare the clean checkout with the working checkout. You must inspect the generated files and the configuration. You must state the cause before you edit. You must make one change and state the expected result. You must compare the result with the expected behavior and note any difference. You must record the result. You must not add a second change while the first result is unclear. You must review the changed path and an unrelated path before you submit.

A third example starts with a behavior that differs only for one input shape. You must collect the exact input and the exact result. You must compare the shape with a working shape. You must inspect the branch that handles the shape. You must state the cause and the expected result. You must make one change and review the result. You must re-read the change and confirm that it addresses the described problem. You must record the cause, the change, and the result in one short note.

## Worksheet

You must answer each question in the record before you edit.

- What is the exact input?
- What is the exact output?
- What is the expected output?
- Which path is different from a working path?
- Where does the bad value enter the system?
- What is the cause in one sentence?
- What is the expected result of the change?
- What did the result show?
- Which unrelated path was reviewed?
- What is the final note?

You must keep the answers short. You must write the answer to each question before the next step. You must return to the worksheet when a new result appears. You must not leave a question blank and continue. You must not treat an assumption as an answer. You must keep the worksheet with the task so a later reader can follow the evidence.

## Frequently Asked Questions

**What if the failure is intermittent?** You must note the conditions in which it appears and the conditions in which it does not. You must repeat the attempt under the same conditions. You must collect enough evidence to see the boundary. You must not guess at the cause while the boundary is unknown.

**What if the first change does not work?** You must return to Step 1 with the new evidence. You must not add a second change on top of the first. You must state a new cause and write a new expected result. You must keep the first change in the record so the new result can be compared with it.

**What if the cause is in another component?** You must inspect the boundary before and after each component. You must record what enters and what leaves each component. You must identify the first component at which the value is wrong. You must not edit a component that is not on the failing path.

**What if the change touches many files?** You must reduce the change to one cause. You must separate the necessary edit from the unrelated cleanup. You must not bundle a refactor with the fix. You must keep the change small enough to review.

**What if the result is unclear?** You must treat it as a failure until it is explained. You must read the full output and compare it with the expectation. You must record the difference. You must not claim success while the result is unclear.

**What if the cause is still unknown?** You must collect more evidence before you edit. You must inspect another boundary, another input, or another path. You must state what the new evidence shows. You must not make a change without a cause.

**What if the change is correct but the result is still wrong?** You must return to Step 1 with the new result. You must look over the result and record any remaining concern. You must inspect the path again with the new evidence. You must not add another change before the cause is clear.

## Process

### Step 1: Understand the Problem

You must read the full error message and reproduce the failure. Never guess at the cause. Always note the exact input and the exact result. You must describe the failure in one sentence. You must include the command, the environment, and the observed output in the record. If the failure is intermittent, you must note the conditions under which it appears and the conditions under which it does not. You must not edit any file during this step.

### Step 2: Locate the Cause

You must trace the data flow to its source. Always compare the failing path with a working path. Never stop at the first suspicious line. You must state where the bad value enters the system. You must inspect the boundary before and after each component in the path. You must keep a list of the components you checked and the evidence you found at each boundary. You must not treat a correlation as a cause.

### Step 3: Make One Change

You must change one thing at a time. Never bundle unrelated edits. Always state the hypothesis before the change. You must keep the change small enough to review. You must write the expected result before you make the change, so the result can be compared with the expectation. You must not add a second change while the first result is unknown. You must not refactor code that is not part of the cause.

### Step 4: Review the Result

You must inspect the changed path and the unchanged path side by side. You must write the observed result in the record before you submit. Never submit while the result is unclear. You must compare the new result with the expected behavior. You must also confirm that the change did not alter an unrelated path. If the result differs from the expectation, you must return to Step 1 with the new evidence rather than adding another change.

## Review

You must review the changed code and inspect the result. You must compare the result with the expected behavior and note any difference. Never claim success without a passing result. You must re-read the change and confirm that it addresses the described problem. You must record the command and the observed result in the final note. You must treat an unclear result as a failure until it is explained.

## Worked Example

A test fails only when the input contains an empty list. You must read the failure and reproduce it with a small input. You must compare the empty-list path with a non-empty path. The bad value enters at the point where the code reads the first item. You must make one change at that point and state the expected result. You must look over the result and record any remaining concern. The failing test now passes, and no unrelated path changes. You must record the cause and the change in one short note.

## Checklist

- The root cause is stated.
- The change addresses the root cause.
- The tests pass and the output is clean.
- No unrelated edits are included.
- The result matches the description.
- The changed path and an unrelated path were both reviewed.
- The record contains the command and the observed result.
- The hypothesis was written before the change.

## Common Mistakes

- Guessing before evidence.
- Fixing a symptom instead of the cause.
- Bundling multiple changes.
- Submitting without verification.
- Stopping after the first suspicious line.
- Treating a correlation as a cause.
- Adding a second change while the first result is unknown.
- Refactoring code that is not part of the cause.

## Red Flags

| Signal | Response |
|---|---|
| The first fix did not work | Return to Step 1 with the new evidence |
| Each fix reveals a new problem | Question the structure, not only the line |
| The result is unclear | Treat it as a failure until it is explained |
| The change touches many files | Reduce the change to one cause |
| The cause is still unknown | Collect more evidence before editing |

## Quick Reference

| Step | Goal |
|---|---|
| Understand | Reproduce and read the error |
| Locate | Trace the cause to its source |
| Change | Make one focused edit |
| Review | Inspect the result and note any difference |

## Notes

You must keep a short record of what you observed at each step. You must group related observations together. You must return to the record when a new result appears. A clear record makes the cause easier to see, and it makes a later review faster. You must write the final note in plain language so another reader can follow the evidence.

## Record Template

You must write the record in four short parts. You must state the input and the observed result in the first part. You must state the boundary and the evidence in the second part. You must state the cause and the expected result in the third part. You must state the change and the observed result in the fourth part. You must keep each part to a few lines. You must not leave a part empty. You must review the record before you submit. You must keep the record with the task so a later reader can follow the evidence.

You must use the same format for every task. You must write the command and the observed output in the first part. You must write the path and the boundary in the second part. You must write the cause in one sentence in the third part. You must write the expected result and the observed result in the fourth part. You must note any unrelated path that was reviewed. You must keep the final note short and factual.