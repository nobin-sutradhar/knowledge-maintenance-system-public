Yes. Since the current system is actually **v0.5 + the modular `kmaint/` architecture**, I would update the README to reflect the system as it exists now rather than calling it simply v0.5.

Copy-paste this entire content into:

```text
~/knowledge-maintenance-system-v0.3/README.md
```

````markdown
# Knowledge Maintenance System

A terminal-based personal knowledge maintenance system.

It treats knowledge as a **maintained object** rather than a static note.

The system is designed around a simple problem:

> Knowing something once is not the same as being able to reliably recall, explain, or apply it later.

Instead of only storing notes, the system captures knowledge, deliberately lets it be forgotten, resurfaces it for review, records how well it was recalled, and allows the knowledge itself to evolve through immutable versions.

---

## Core Philosophy

The system separates several things that are normally mixed together:

- **Knowledge** — what is currently believed to be correct.
- **Understanding** — whether the concept is actually understood.
- **Recall** — whether the knowledge can be retrieved without looking.
- **Confidence** — how confident the user is in the answer.
- **Verification** — whether the information has been objectively checked.
- **Version** — how the understanding of the knowledge has evolved over time.
- **Review** — an attempt to recall, explain, or apply existing knowledge.

The goal is not to create a larger collection of notes.

The goal is to maintain a smaller collection of **reliable knowledge**.

---

# Core Loop

```text
capture
   ↓
forget
   ↓
review / recall
   ↓
correct / partial / wrong / don't know
   ↓
correct / refine understanding
   ↓
review again
````

The system intentionally introduces retrieval rather than allowing knowledge to remain passive.

---

# Knowledge Model

Each knowledge item has:

```text
Knowledge
├── Identity
├── Display number
├── Title
├── Claim
├── Explanation
├── Source
├── Version
├── Status
├── Confidence
├── Priority
├── Review mode
├── Created time
├── Last reviewed time
└── Next automatic review
```

## Identity

Every knowledge item has an internal immutable identity.

The displayed number, such as:

```text
0001
0002
0003
```

is only a human-friendly reference.

Display numbers may change after deletion.

The internal identity does not.

---

# Versioning

Knowledge is allowed to change.

Versions represent the evolution of understanding.

```text
v1.0
v1.1
v1.2
v2.0
v2.1
```

General convention:

```text
v1.0 → initial knowledge

v1.1, v1.2, ... → minor refinement

v2.0 → major conceptual correction
```

Previous versions are immutable.

Editing knowledge creates a new version rather than silently overwriting the previous understanding.

This preserves the evolution of the user's knowledge.

---

# Review Modes

Every knowledge item has one review mode.

```text
recall
explain
apply
```

## Recall

```text
Can I remember the knowledge?
```

The challenge is to retrieve the knowledge without looking at the reference.

## Explain

```text
Can I explain how and why it works?
```

The challenge requires the user to explain the concept in their own words.

## Apply

```text
Can I use it on a concrete problem or scenario?
```

The challenge requires applying the knowledge rather than merely describing it.

---

# Review Flow

The reference is deliberately hidden initially.

A review follows this sequence:

```text
1. Attempt the challenge without looking at the reference.
2. Reveal the original claim and explanation.
3. Compare your answer with the reference.
4. Record the result.
5. The result determines confidence, status, and next automatic review.
```

The four possible results are:

```text
Correct
Partial
Wrong
Don't know
```

---

# Review Results

The current default scheduling behavior is:

| Result     | Confidence | Status     | Next review |
| ---------- | ---------: | ---------- | ----------: |
| Correct    |        90% | VERIFIED   |     +5 days |
| Partial    |        65% | UNVERIFIED |     +2 days |
| Wrong      |        30% | CONFUSED   |      +1 day |
| Don't know |        15% | CONFUSED   |      +1 day |

These intervals are configurable through `config.toml`.

The system does not permanently assume that a knowledge item is safe simply because it was once answered correctly.

---

# Status

Knowledge can have one of the following statuses:

```text
CAPTURED
UNVERIFIED
CONFUSED
VERIFIED
MASTERED
```

## CAPTURED

The knowledge has been recorded but has not yet gone through sufficient review.

## UNVERIFIED

The knowledge is incomplete, uncertain, or only partially recalled.

## CONFUSED

The user's understanding or recall is currently unreliable.

## VERIFIED

The information has been objectively checked.

Verification and mastery are separate concepts.

## MASTERED

The knowledge can be reliably recalled.

Mastery does **not** automatically mean the knowledge is permanently correct.

---

# Confidence

Confidence is tracked separately from status.

For example:

```text
Status:     VERIFIED
Confidence: 90%
```

or:

```text
Status:     CONFUSED
Confidence: 15%
```

This distinction matters because:

```text
"I think this is correct"
```

is not equivalent to:

```text
"This has been verified and I can reliably recall it."
```

---

# Review History

Every review is preserved as a separate historical event.

A review stores:

* user's answer
* exact knowledge version reviewed
* result
* confidence
* review timestamp
* reference information used for comparison

Example:

```text
Review #1
Version:    v1.0
Result:     Partial
Confidence: 65%
Answer:     ...
Reviewed:   ...

Review #2
Version:    v1.1
Result:     Correct
Confidence: 90%
Answer:     ...
Reviewed:   ...
```

Review history is different from version history.

### Version history

Shows how the knowledge itself changed.

```text
v1.0 → v1.1 → v2.0 → v2.1
```

### Review history

Shows how the user performed against those versions.

```text
Review #1 → Review #2 → Review #3 → ...
```

Use:

```bash
know history <number>
```

to view both.

---

# Scheduling

The system has two kinds of review:

```text
Automatic reviews
Custom reviews
```

## Automatic reviews

Automatic scheduling uses:

```text
next_review
```

Each review result determines when the knowledge should next become due.

The automatic review queue is limited by:

```toml
daily_limit = 2
```

Automatic reviews are prioritized using the knowledge priority and due/overdue state.

---

## Custom Reviews

A custom review can be scheduled for a specific date.

```bash
know schedule <number>
```

Custom reviews are additional review events and are separate from the automatic queue.

They are not intended to replace automatic scheduling.

A custom review can therefore be used when the user explicitly wants to revisit something on a particular date.

After the custom review is completed, the knowledge's automatic `next_review` is also updated according to the review result.

---

# Review Configuration

Review behavior is configured through `config.toml`.

Current defaults:

```toml
[review]
daily_limit = 2
default_review_days = 1
review_mode = "recall"
correct_review_days = 5
partial_review_days = 2
wrong_review_days = 1
dont_know_review_days = 1
```

Meaning:

```text
daily_limit
    Maximum number of automatically selected reviews per review run.

default_review_days
    Number of days before a newly captured knowledge item receives
    its first automatic review.

review_mode
    Default challenge mode for new knowledge.

correct_review_days
    Delay after a Correct result.

partial_review_days
    Delay after a Partial result.

wrong_review_days
    Delay after a Wrong result.

dont_know_review_days
    Delay after a Don't know result.
```

The intervals are configurable rather than hard-coded into the review logic.

---

# Priority

Each knowledge item has a priority.

```text
1 → lowest
10 → highest
```

Higher-priority knowledge is surfaced earlier when selecting automatic reviews.

Priority is useful for distinguishing:

```text
important knowledge
```

from:

```text
interesting but low-value knowledge
```

---

# Archiving

`MASTERED` does **not** automatically archive knowledge.

Mastery means:

```text
"I can reliably recall this."
```

It does not mean:

```text
"I will never forget this."
```

Archiving is therefore an explicit decision.

```bash
know archive <number>
```

Restore archived knowledge with:

```bash
know restore <number>
```

Archived knowledge:

* remains searchable
* retains all versions
* retains all review history
* does not enter active review queues

---

# Search

Search supports multiple words:

```bash
know search javascript scope
```

The search ranks matches based on where the terms occur.

Conceptually:

```text
title
  >
claim
  >
explanation
  >
source
```

Multi-word coverage is also considered.

The current search is lexical rather than semantic.

Semantic/conceptual search can be added later without changing the core knowledge model.

---

# Commands

## Dashboard

```bash
know
```

Shows the current knowledge/review dashboard.

---

## Capture knowledge

```bash
know add
```

Captures a new knowledge item.

The system records the knowledge and allows review configuration such as:

```text
review mode
priority
optional custom review date
```

---

## List knowledge

```bash
know list
```

Browse stored knowledge.

---

## Search

```bash
know search <words...>
```

Search using one or more words.

Example:

```bash
know search javascript promise
```

---

## Show knowledge

```bash
know show <number>
```

Display a knowledge item and its current state.

---

## Edit knowledge

```bash
know edit <number>
```

Edit knowledge.

Editing creates a new immutable version.

Example:

```text
v1.0
  ↓
v1.1
```

or, after a major conceptual correction:

```text
v1.1
  ↓
v2.0
```

---

## History

```bash
know history <number>
```

Shows:

```text
Version history
+
Review history
```

including the version reviewed, result, confidence, answer, and reference information.

---

## Review

```bash
know review
```

Starts the review process.

The system:

```text
selects due knowledge
        ↓
presents challenge
        ↓
waits for user's answer
        ↓
reveals reference
        ↓
records result
        ↓
updates confidence/status
        ↓
calculates next review
```

---

## Custom review

```bash
know schedule <number>
```

Schedule an additional review for a specific date.

---

## Archive

```bash
know archive <number>
```

Remove knowledge from active review.

The knowledge remains stored.

---

## Restore

```bash
know restore <number>
```

Return archived knowledge to active review.

---

## Delete

```bash
know delete <number>
```

Delete a knowledge item.

Deletion affects the human-facing display numbering, but internal knowledge identity is designed to remain immutable for existing records.

---

# Knowledge Card

The terminal interface presents knowledge in a structured card.

Conceptually:

```text
╭────────────────────────────────────────────────────────────────────────────╮
│ KNOWLEDGE 0001                                                             │
├────────────────────────────────────────────────────────────────────────────┤
│ Title:       ...                                                           │
│ Claim:       ...                                                           │
│                                                                            │
│ Explanation: ...                                                           │
│ Version:     v2.1                                                          │
│ Status:      CONFUSED                                                      │
│ Confidence:  15%                                                           │
│ Priority:    5                                                             │
│ Review mode: RECALL                                                        │
│ Created:     ...                                                           │
│ Last review: ...                                                           │
│ Next review: ...                                                           │
╰────────────────────────────────────────────────────────────────────────────╯
```

Long claims and explanations are wrapped automatically while preserving the box layout.

---

# Architecture

The application is intentionally divided into modules so individual responsibilities can evolve independently.

```text
main.py
    ↓
kmaint.cli
    ↓
┌──────────────────────────────────────────────┐
│                Application                   │
├──────────────────────────────────────────────┤
│ cli.py       → command-line interface        │
│ knowledge.py → knowledge operations           │
│ review.py    → review and scheduling logic   │
│ db.py        → SQLite persistence             │
│ config.py    → configuration                  │
│ ui.py        → terminal rendering/prompts     │
└──────────────────────────────────────────────┘
```

### `main.py`

Minimal executable entry point.

Its responsibility is only to start the CLI.

### `kmaint/cli.py`

Handles:

* argument parsing
* command dispatch
* dashboard
* CLI-level orchestration

### `kmaint/knowledge.py`

Handles knowledge operations such as:

* capture
* list
* search
* show
* edit
* archive
* restore
* delete
* knowledge selection

### `kmaint/review.py`

Handles:

* review flow
* review modes
* review results
* confidence updates
* status updates
* automatic scheduling
* custom review scheduling
* review history

### `kmaint/db.py`

Handles:

* SQLite connection
* schema
* database initialization
* migrations
* persistence queries

### `kmaint/config.py`

Handles:

* configuration loading
* default configuration
* review settings

### `kmaint/ui.py`

Handles:

* terminal formatting
* ANSI colors
* knowledge cards
* prompts
* visual presentation

---

# Data Persistence

The system uses SQLite.

Main database:

```text
knowledge.db
```

The database stores knowledge, versions, reviews, and custom review scheduling information.

The database is local to the application.

---

# Design Principles

The project follows several principles.

## 1. Knowledge is mutable, history is not

Current understanding can change.

Historical versions should not.

---

## 2. Review is not editing

A review records how the user performed against existing knowledge.

An edit changes the knowledge itself and creates a new version.

---

## 3. Confidence is not correctness

Confidence describes the user's belief.

Verification describes whether information has been checked.

They are separate.

---

## 4. Mastery is not archiving

Being able to recall something reliably does not mean it should disappear from the review system forever.

Archiving is explicit.

---

## 5. Retrieval before reference

The user should attempt to retrieve knowledge before seeing the stored explanation.

This makes review an active process rather than passive rereading.

---

## 6. Preserve the evolution of understanding

The system should make it possible to answer:

```text
What did I originally believe?
What changed?
Why did it change?
How well could I recall it at each point?
```

---

## 7. Keep the core model independent of the interface

The CLI is currently the primary interface.

The underlying knowledge, review, versioning, and persistence model should not depend on the terminal interface.

This allows future interfaces to be added without redesigning the core system.

---

# Current Scope

The current system provides:

```text
✓ Knowledge capture
✓ Knowledge versioning
✓ Immutable historical versions
✓ Review modes
✓ Recall-first review flow
✓ User answer recording
✓ Review history
✓ Version history
✓ Confidence tracking
✓ Knowledge status
✓ Priority
✓ Automatic review scheduling
✓ Custom review scheduling
✓ Configurable review intervals
✓ Search
✓ Archive / restore
✓ Delete
✓ Terminal knowledge cards
✓ Modular architecture
✓ SQLite persistence
```

---

# Future Direction

Potential future capabilities include:

```text
semantic search
application-question generation
smarter review selection
knowledge relationships
topic/graph navigation
source verification workflows
knowledge dependency tracking
review analytics
forgetting-curve analysis
knowledge conflict detection
```

These are deliberately outside the current core implementation.

The primary goal is to keep the fundamental loop reliable:

```text
capture
→ forget
→ retrieve
→ evaluate
→ correct
→ retain
```

---

# Project Philosophy

This is not intended to become another note-taking application.

The distinction is:

```text
Note-taking system
    → stores what you wrote.

Knowledge Maintenance System
    → maintains what you know.
```

The system is therefore optimized around:

```text
retrieval
verification
correction
versioning
review
retention
```

rather than simply maximizing the amount of stored information.

```

One correction to the old README is especially important: **don't describe `default_review_days = 1` as a recurring one-day interval.** It represents the delay before the first automatic review; subsequent timing comes from the review result and its configured interval.
```
