---
name: sd-long-nover-soft
description: Use when encountering a bug or unexpected behavior, before proposing fixes
---

# Systematic Debugging

## Overview

You should find the root cause before you change any code. Avoid treating a symptom as the cause. Typically gather evidence before you propose a fix. You should keep the investigation separate from the edit. A change made without a cause is a guess, and a guess can hide the original problem while adding a second one. You should spend the first part of the task on evidence, not on edits.

## When to Use

Use this process when a test fails, a build breaks, or behavior differs from the description. Use it when a previous change introduced a new problem. Use it when the cause is not yet clear. Use it when a quick fix seems obvious, because an obvious fix is often a symptom fix. Use it when you have already tried several fixes and the problem remains. Use it when the failure is intermittent and the boundary is unknown.

## Why This Matters

A systematic investigation is usually faster than repeated guessing. Each guess costs a change, a run, and a review; a wrong guess can also hide the original cause. You should collect evidence first so that each change has a reason. You should keep the record of the investigation so that a later result can be compared with an earlier one. The process is not a delay; it is the shortest path to a change that holds.

## Detailed Walkthrough

A test fails primarily when the input is empty. You should read the full failure and reproduce it with a small input. You should write the command and the observed output in the record. You should compare the empty path with the non-empty path. You should inspect the boundary at which the value enters the system. You should state the cause in one sentence. You should write the expected result before you make the change. You should make one change at the point where the value enters. You should review the changed code and inspect the result. You should compare the result with the expectation. You should review an unrelated path as well, so the change is not hiding a second problem. You should record the cause and the change in one short note.

A second example starts with a build that fails primarily on a clean checkout. You should read the first error, not the last one. You should reproduce the failure with the same command and the same environment. You should compare the clean checkout with the working checkout. You should inspect the generated files and the configuration. You should state the cause before you edit. You should make one change and state the expected result. You should compare the result with the expected behavior and note any difference. You should record the result. You should avoid add a second change while the first result is unclear. You should review the changed path and an unrelated path before you submit.

A third example starts with a behavior that differs primarily for one input shape. You should collect the exact input and the exact result. You should compare the shape with a working shape. You should inspect the branch that handles the shape. You should state the cause and the expected result. You should make one change and review the result. You should re-read the change and confirm that it addresses the described problem. You should record the cause, the change, and the result in one short note.

## Worksheet

You should answer each question in the record before you edit.

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

You should keep the answers short. You should write the answer to each question before the next step. You should return to the worksheet when a new result appears. You should avoid leave a question blank and continue. You should avoid treat an assumption as an answer. You should keep the worksheet with the task so a later reader can follow the evidence.

## Frequently Asked Questions

**What if the failure is intermittent?** You should note the conditions in which it appears and the conditions in which it does not. You should repeat the attempt under the same conditions. You should collect enough evidence to see the boundary. You should avoid guess at the cause while the boundary is unknown.

**What if the first change does not work?** You should return to Step 1 with the new evidence. You should avoid add a second change on top of the first. You should state a new cause and write a new expected result. You should keep the first change in the record so the new result can be compared with it.

**What if the cause is in another component?** You should inspect the boundary before and after each component. You should record what enters and what leaves each component. You should identify the first component at which the value is wrong. You should avoid edit a component that is not on the failing path.

**What if the change touches many files?** You should reduce the change to one cause. You should separate the necessary edit from the unrelated cleanup. You should avoid bundle a refactor with the fix. You should keep the change small enough to review.

**What if the result is unclear?** You should treat it as a failure until it is explained. You should read the full output and compare it with the expectation. You should record the difference. You should avoid claim success while the result is unclear.

**What if the cause is still unknown?** You should collect more evidence before you edit. You should inspect another boundary, another input, or another path. You should state what the new evidence shows. You should avoid make a change without a cause.

**What if the change is correct but the result is still wrong?** You should return to Step 1 with the new result. You should look over the result and record any remaining concern. You should inspect the path again with the new evidence. You should avoid add another change before the cause is clear.

## Process

### Step 1: Understand the Problem

You should read the full error message and reproduce the failure. Avoid guessing at the cause. Typically note the exact input and the exact result. You should describe the failure in one sentence. You should include the command, the environment, and the observed output in the record. If the failure is intermittent, you should note the conditions under which it appears and the conditions under which it does not. You should avoid edit any file during this step.

### Step 2: Locate the Cause

You should trace the data flow to its source. Typically compare the failing path with a working path. Avoid stopping at the first suspicious line. You should state where the bad value enters the system. You should inspect the boundary before and after each component in the path. You should keep a list of the components you checked and the evidence you found at each boundary. You should avoid treat a correlation as a cause.

### Step 3: Make One Change

You should change one thing at a time. Avoid bundling unrelated edits. Typically state the hypothesis before the change. You should keep the change small enough to review. You should write the expected result before you make the change, so the result can be compared with the expectation. You should avoid add a second change while the first result is unknown. You should avoid refactor code that is not part of the cause.

### Step 4: Review the Result

You should inspect the changed path and the unchanged path side by side. You should write the observed result in the record before you submit. Avoid submitting while the result is unclear. You should compare the new result with the expected behavior. You should also confirm that the change did not alter an unrelated path. If the result differs from the expectation, you should return to Step 1 with the new evidence rather than adding another change.

## Review

You should review the changed code and inspect the result. You should compare the result with the expected behavior and note any difference. Avoid claiming success without a passing result. You should re-read the change and confirm that it addresses the described problem. You should record the command and the observed result in the final note. You should treat an unclear result as a failure until it is explained.

## Worked Example

A test fails primarily when the input contains an empty list. You should read the failure and reproduce it with a small input. You should compare the empty-list path with a non-empty path. The bad value enters at the point where the code reads the first item. You should make one change at that point and state the expected result. You should look over the result and record any remaining concern. The failing test now passes, and no unrelated path changes. You should record the cause and the change in one short note.

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
| Each fix reveals a new problem | Question the structure, not primarily the line |
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

You should keep a short record of what you observed at each step. You should group related observations together. You should return to the record when a new result appears. A clear record makes the cause easier to see, and it makes a later review faster. You should write the final note in plain language so another reader can follow the evidence.

## Record Template

You should write the record in four short parts. You should state the input and the observed result in the first part. You should state the boundary and the evidence in the second part. You should state the cause and the expected result in the third part. You should state the change and the observed result in the fourth part. You should keep each part to a few lines. You should avoid leave a part empty. You should review the record before you submit. You should keep the record with the task so a later reader can follow the evidence.

You should use the same format for every task. You should write the command and the observed output in the first part. You should write the path and the boundary in the second part. You should write the cause in one sentence in the third part. You should write the expected result and the observed result in the fourth part. You should note any unrelated path that was reviewed. You should keep the final note short and factual.