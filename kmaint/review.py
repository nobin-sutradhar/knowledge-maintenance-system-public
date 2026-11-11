from datetime import datetime, timedelta

from . import db
from .ui import (
    C,
    bold,
    colorize,
    dim,
    fmt_mode,
    fmt_result,
    fmt_status,
    fmt_version,
    print_result_row,
    relative_days,
    now,
    prompt
)


def challenge_text(mode):
    return {
        "recall": (
            "RECALL: Remember the knowledge without looking at "
            "the reference."
        ),
        "explain": (
            "EXPLAIN: Explain how and why the knowledge works "
            "in your own words."
        ),
        "apply": (
            "APPLY: Use the knowledge on a concrete problem, "
            "scenario, or task."
        ),
    }.get(
        mode,
        "RECALL: Remember the knowledge without looking at the reference.",
    )


def schedule(conn, internal_id=None):
    from .knowledge import choose_item

    if internal_id is None:
        internal_id = choose_item(
            conn,
            "schedule custom review",
            False,
        )

    if not internal_id:
        return

    k, v = db.get_item(conn, internal_id)

    if not k:
        print(colorize("Knowledge item not found.", C.RED))
        return

    date = input("Review date YYYY-MM-DD: ").strip()

    import re

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        print(colorize("Invalid date.", C.RED))
        return

    existing = conn.execute(
        """
        SELECT id
        FROM custom_reviews
        WHERE knowledge_id=?
          AND scheduled_for=?
          AND completed_at IS NULL
        """,
        (internal_id, date),
    ).fetchone()

    if existing:
        print(
            colorize(
                "A pending custom review is already scheduled "
                "for this knowledge on that date.",
                C.YELLOW,
            )
        )
        return

    conn.execute(
        """
        INSERT INTO custom_reviews
        (knowledge_id, scheduled_for)
        VALUES (?,?)
        """,
        (internal_id, date),
    )

    conn.commit()

    current = conn.execute(
        """
        SELECT next_review
        FROM knowledge
        WHERE internal_id=?
        """,
        (internal_id,),
    ).fetchone()

    print(
        f"\n"
        f"{colorize('✓', C.GREEN)} "
        f"{bold('Custom review scheduled')}\n"
        f"Knowledge:                 "
        f"{colorize(db.display_number(conn, internal_id), C.CYAN)}"
        f" — {v['title']}\n"
        f"Custom review:             "
        f"{colorize(date, C.MAGENTA)}\n"
        f"Current automatic review:  "
        f"{colorize(current['next_review'], C.BRIGHT_GREEN) if current and current['next_review'] else 'not scheduled'}"
    )


def _edit_during_review(conn, internal_id):
    """
    Enter the normal knowledge editing flow from inside a review.

    The edit operation itself lives in knowledge.py so version creation
    remains centralized in one place.
    """

    from .knowledge import edit

    print(
        "\n"
        + colorize(
            "EDITING KNOWLEDGE",
            C.MAGENTA + C.BOLD,
        )
    )

    edit(conn, internal_id)


def _show_claim_for_challenge(v):
    """
    Show the current claim before explain/apply challenges.

    The claim is the proposition being explained or applied. It must
    therefore be visible before the user produces their response.
    """

    print(
        "\n"
        + colorize("CURRENT CLAIM", C.CYAN + C.BOLD)
        + "\n"
        + colorize("─" * 72, C.CYAN)
    )

    print(v["claim"])


def _show_reference(v):
    """
    Reveal the exact version that is being reviewed.

    This version is captured before any review-time edit occurs, so the
    review remains historically tied to the knowledge that was actually
    reviewed.
    """

    print(
        "\n"
        + colorize("─" * 72, C.MAGENTA)
        + "\n"
        + colorize(
            "REFERENCE — compare against your attempt",
            C.MAGENTA + C.BOLD,
        )
        + "\n"
        + colorize("─" * 72, C.MAGENTA)
    )

    print(
        f"\n"
        f"{colorize('CLAIM', C.CYAN)}\n"
        f"{v['claim']}\n\n"
        f"{colorize('ORIGINAL EXPLANATION', C.CYAN)}\n"
        f"{v['explanation'] or dim('(no explanation recorded)')}"
        + (
            f"\n\n{dim('SOURCE')}  {v['source']}"
            if v["source"]
            else ""
        )
    )


def _show_attempt(mode, answer):
    if mode in ("explain", "apply") and answer:
        print(
            f"\n\n"
            f"{colorize('YOUR ANSWER', C.CYAN)}\n"
            f"{answer}"
        )

    else:
        print(
            f"\n\n"
            f"{colorize('YOUR ATTEMPT', C.CYAN)}\n"
            f"{dim('(mental recall — no written answer)')}"
        )


def _get_result(config):
    """
    Ask the user to evaluate the review.

    Editing the knowledge and evaluating the review are deliberately
    separate operations. Editing creates a new knowledge version;
    evaluation records what happened during the current review.
    """

    while True:
        print(
            "\n\n"
            + colorize("─" * 72, C.YELLOW)
            + "\n"
            + colorize(
                "COMPARE",
                C.YELLOW + C.BOLD,
            )
            + "\n"
            "  [1] Correct\n"
            "  [2] Partial\n"
            "  [3] Wrong\n"
            "  [4] Don't know\n"
            "  [e] Edit knowledge"
        )

        choice = input("Choice: ").strip().lower()

        if choice == "e":
            return "EDIT"

        mapping = {
            "1": (
                "CORRECT",
                90,
                config["correct_review_days"],
            ),
            "2": (
                "PARTIAL",
                65,
                config["partial_review_days"],
            ),
            "3": (
                "WRONG",
                30,
                config["wrong_review_days"],
            ),
            "4": (
                "DONT_KNOW",
                15,
                config["dont_know_review_days"],
            ),
        }

        if choice in mapping:
            return mapping[choice]

        print(
            colorize(
                "Invalid choice. Select 1, 2, 3, 4, or e.",
                C.RED,
            )
        )


def perform(conn, k, config, custom_review_id=None):
    """
    Perform one review.

    Review modes:

        recall
            User recalls the knowledge mentally.
            No written answer is collected.

        explain
            The current claim is shown first.
            User writes an explanation in their own words.

        apply
            The current claim is shown first.
            User writes how they would apply the knowledge.

    After the challenge, the exact version being reviewed is revealed.

    The user can revise the knowledge directly from the review. A
    revision creates a new immutable version through knowledge.edit().
    The review itself remains attached to the version that was reviewed.
    """

    # Capture the version at the beginning of the review.
    #
    # This is important: if the user edits the knowledge during the
    # review, that edit creates a new version. The current review must
    # still refer to the version the user originally reviewed.
    v = db.latest_version(conn, k["internal_id"])
    number = db.display_number(conn, k["internal_id"])

    mode = (
        k["review_mode"]
        if "review_mode" in k.keys()
        else "recall"
    )

    # ------------------------------------------------------------
    # Review header
    # ------------------------------------------------------------

    print(
        "\n"
        + colorize("═" * 72, C.CYAN)
        + "\n"
        + colorize(
            f"REVIEW  {number}  {fmt_version(v)} — {v['title']}",
            C.BRIGHT_CYAN + C.BOLD,
        )
        + "\n"
        + colorize("═" * 72, C.CYAN)
    )

    print(
        f"\n"
        f"{colorize('MODE', C.CYAN)}  {fmt_mode(mode)}"
    )

    print(f"\n{challenge_text(mode)}")

    # ------------------------------------------------------------
    # Mode-specific challenge
    # ------------------------------------------------------------

    answer = None

    if mode == "recall":
        print(
            "\n"
            + colorize(
                "Recall the knowledge mentally before revealing "
                "the reference.",
                C.YELLOW,
            )
        )

        input(
            "\nPress Enter when you are ready to reveal "
            "the reference..."
        )

    elif mode == "explain":
        _show_claim_for_challenge(v)

        answer = prompt(
            "Your explanation",
            multiline=True,
        )

        if not answer.strip():
            print(
                "\n"
                + colorize(
                    "Review skipped — no explanation provided. "
                    "Nothing changed.",
                    C.YELLOW,
                )
            )
            return

    elif mode == "apply":
        _show_claim_for_challenge(v)

        answer = prompt(
            "\nYour application / solution",
            multiline=True,
        )

        if not answer.strip():
            print(
                "\n"
                + colorize(
                    "Review skipped — no application provided. "
                    "Nothing changed.",
                    C.YELLOW,
                )
            )
            return

    else:
        print(
            "\n"
            + colorize(
                "Unknown review mode. Falling back to recall.",
                C.YELLOW,
            )
        )

        input(
            "\nPress Enter when you are ready to reveal "
            "the reference..."
        )

        mode = "recall"

    # ------------------------------------------------------------
    # Reveal exact version being reviewed
    # ------------------------------------------------------------

    _show_reference(v)

    # ------------------------------------------------------------
    # Show user's attempt
    # ------------------------------------------------------------

    _show_attempt(mode, answer)

    # ------------------------------------------------------------
    # Self-evaluation / optional revision
    # ------------------------------------------------------------

    while True:
        evaluation = _get_result(config)

        if evaluation != "EDIT":
            result, confidence, days = evaluation
            break

        # Revision is deliberately separate from the review result.
        #
        # knowledge.edit() creates a new immutable version. The local
        # variable `v` remains the version originally reviewed.
        _edit_during_review(
            conn,
            k["internal_id"],
        )

        print(
            "\n"
            + colorize(
                "Knowledge revised.",
                C.MAGENTA,
            )
            + "\n"
            + dim(
                "The review will still be recorded against "
                f"{fmt_version(v)}, the version you reviewed."
            )
        )

    # ------------------------------------------------------------
    # Determine status
    # ------------------------------------------------------------

    status = (
        "CONFUSED"
        if result in ("WRONG", "DONT_KNOW")
        else "UNVERIFIED"
        if result == "PARTIAL"
        else "VERIFIED"
    )

    reviewed = now()

    next_review = (
        datetime.now().astimezone()
        + timedelta(days=days)
    ).isoformat(timespec="seconds")

    # ------------------------------------------------------------
    # Store review
    # ------------------------------------------------------------

    conn.execute(
        """
        INSERT INTO reviews
        (
            knowledge_id,
            major,
            minor,
            mode,
            result,
            confidence,
            answer,
            reviewed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
       (
        k["internal_id"],
        v["major"],
        v["minor"],
        mode,
        result,
        confidence,
        answer,
        reviewed,
    ),
    )

    # ------------------------------------------------------------
    # Update current knowledge state
    # ------------------------------------------------------------

    conn.execute(
        """
        UPDATE knowledge
        SET
            status=?,
            confidence=?,
            last_reviewed=?,
            next_review=?
        WHERE internal_id=?
        """,
        (
            status,
            confidence,
            reviewed,
            next_review,
            k["internal_id"],
        ),
    )

    # ------------------------------------------------------------
    # Complete custom review if applicable
    # ------------------------------------------------------------

    if custom_review_id is not None:
        conn.execute(
            """
            UPDATE custom_reviews
            SET completed_at=?
            WHERE id=?
            """,
            (
                reviewed,
                custom_review_id,
            ),
        )

    conn.commit()

    # ------------------------------------------------------------
    # Completion summary
    # ------------------------------------------------------------

    kind = (
        "CUSTOM"
        if custom_review_id is not None
        else "AUTOMATIC"
    )

    print(
        "\n"
        + colorize(
            "╭" + "─" * 72 + "╮",
            C.GREEN,
        )
        + "\n"
        + colorize(
            "│ REVIEW COMPLETED" + " " * 55 + "│",
            C.GREEN + C.BOLD,
        )
        + "\n"
        + colorize(
            "╰" + "─" * 72 + "╯",
            C.GREEN,
        )
    )

    print(
        f"\n"
        f"Review type: "
        f"{colorize(kind, C.MAGENTA if custom_review_id is not None else C.CYAN)}\n"
        f"Mode:        {fmt_mode(mode)}\n"
        f"Reviewed:    {colorize(fmt_version(v), C.MAGENTA)}\n"
        f"Result:      {fmt_result(result)}\n"
        f"Status:      {fmt_status(status)}\n"
        f"Confidence:  {confidence}%\n\n"
        f"{colorize('NEXT REVIEW', C.BRIGHT_GREEN + C.BOLD)}\n"
        f"{colorize(next_review, C.BRIGHT_GREEN)}\n"
        f"{dim(relative_days(next_review))}"
    )


def review(conn, config):
    today = (
        datetime.now()
        .astimezone()
        .date()
        .isoformat()
    )

    automatic = db.due_automatic_reviews(
        conn,
        now(),
        config["daily_limit"],
    )

    custom = db.due_custom_reviews(
        conn,
        today,
    )

    total = len(automatic) + len(custom)

    if not total:
        print(
            colorize(
                "\nNo knowledge is due for review.",
                C.GREEN,
            )
        )
        return

    print(
        "\n"
        + colorize(
            "╭" + "─" * 72 + "╮",
            C.CYAN,
        )
        + "\n"
        + colorize(
            "│ TODAY'S KNOWLEDGE MAINTENANCE" + " " * 42 + "│",
            C.BRIGHT_CYAN + C.BOLD,
        )
        + "\n"
        + colorize(
            "╰" + "─" * 72 + "╯",
            C.CYAN,
        )
    )

    print(
        f"\n"
        f"Automatic: "
        f"{colorize(str(len(automatic)) + ' / ' + str(config['daily_limit']), C.CYAN)}\n"
        f"Custom:    "
        f"{colorize(str(len(custom)), C.MAGENTA)}\n"
        f"Total:     "
        f"{bold(str(total))}"
    )

    if automatic:
        print(
            "\n"
            + colorize(
                "── AUTOMATIC QUEUE "
                "───────────────────────────────────────────────",
                C.CYAN,
            )
        )

        for k in automatic:
            print_result_row(
                conn,
                k,
                db.latest_version(
                    conn,
                    k["internal_id"],
                ),
            )

    if custom:
        print(
            "\n"
            + colorize(
                "── CUSTOM QUEUE "
                "──────────────────────────────────────────────────",
                C.MAGENTA,
            )
        )

        for row in custom:
            print(
                f"{colorize(db.display_number(conn, row['internal_id']), C.CYAN)}  "
                f"{fmt_version(row)}  "
                f"P{row['priority']}  "
                f"{bold(row['title'])}  "
                f"({colorize('scheduled ' + row['scheduled_for'], C.MAGENTA)})"
            )

    # ------------------------------------------------------------
    # Automatic reviews
    # ------------------------------------------------------------

    for k in automatic:
        perform(
            conn,
            k,
            config,
        )

        if (
            input("\nContinue? [Y/n]: ")
            .strip()
            .lower()
            == "n"
        ):
            return

    # ------------------------------------------------------------
    # Custom reviews
    # ------------------------------------------------------------

    for row in custom:
        k = conn.execute(
            """
            SELECT *
            FROM knowledge
            WHERE internal_id=?
            """,
            (row["internal_id"],),
        ).fetchone()

        perform(
            conn,
            k,
            config,
            row["id"],
        )

        if (
            input("\nContinue? [Y/n]: ")
            .strip()
            .lower()
            == "n"
        ):
            return


def history(conn, internal_id):
    rows = conn.execute(
        """
        SELECT *
        FROM knowledge_versions
        WHERE knowledge_id=?
        ORDER BY major, minor
        """,
        (internal_id,),
    ).fetchall()

    number = db.display_number(
        conn,
        internal_id,
    )

    if not rows:
        print(
            colorize(
                "Knowledge item not found.",
                C.RED,
            )
        )
        return

    print(
        f"\n"
        f"{bold(f'=== VERSION HISTORY: {number} ===')}\n"
    )

    for v in rows:
        print(
            f"{colorize(fmt_version(v), C.MAGENTA + C.BOLD)}  "
            f"{dim(v['created_at'])}\n"
            f"  Title:  {v['title']}\n"
            f"  Claim:  {v['claim']}"
        )

        if v["explanation"]:
            print(
                f"  \nExplanation: {v['explanation']}"
            )

        if v["change_reason"]:
            print(
                f"  \nChange: {v['change_reason']}"
            )

        if v["source"]:
            print(
                f"  \nSource: {v['source']}"
            )

        print()

    reviews = conn.execute(
        """
        SELECT
            r.*,
            v.title,
            v.claim,
            v.explanation
        FROM reviews r
        LEFT JOIN knowledge_versions v
            ON v.knowledge_id = r.knowledge_id
            AND v.major = r.major
            AND v.minor = r.minor
        WHERE r.knowledge_id=?
        ORDER BY r.reviewed_at, r.id
        """,
        (internal_id,),
    ).fetchall()

    print(
        f"\n{bold('=== REVIEW HISTORY ===')}\n"
    )

    if not reviews:
        print(
            colorize(
                "No review history yet.",
                C.YELLOW,
            )
        )
        return

    for i, r in enumerate(reviews, 1):
        print(
            colorize(
                f"\nREVIEW #{i}  "
                f"{r['reviewed_at']}  "
                f"v{r['major']}.{r['minor']}",
                C.CYAN + C.BOLD,
            )
        )

        print(
            f"  Mode:        {fmt_mode(r['mode'])}\n"
            f"  Result:      {fmt_result(r['result'])}\n"
            f"  Confidence:  {r['confidence']}%"
        )

        if r["answer"]:
            print(
                f"  Your answer: {r['answer']}"
            )

        if r["explanation"]:
            print(
                f"  Reference explanation: {r['explanation']}"
            )

        print()

        if r["answer"]:
            print(
                f"  Your answer: {r['answer']}"
            )

        if r["explanation"]:
            print(
                f"  Reference explanation: {r['explanation']}"
            )

        print()

def edit_history(conn, internal_id):
    """
    Edit an existing review record.

    The review remains permanently associated with the exact
    knowledge version that was reviewed.

    Editable:
        - mode
        - result
        - answer
        - reviewed_at

    Not editable:
        - review id
        - knowledge_id
        - reviewed version

    Confidence is derived from the result and therefore is not
    edited independently.
    """

    k, current_version = db.get_item(
        conn,
        internal_id,
    )

    if not k:
        print(
            colorize(
                "Knowledge item not found.",
                C.RED,
            )
        )
        return

    number = db.display_number(
        conn,
        internal_id,
    )

    reviews = conn.execute(
        """
        SELECT *
        FROM reviews
        WHERE knowledge_id=?
        ORDER BY reviewed_at, id
        """,
        (internal_id,),
    ).fetchall()

    if not reviews:
        print(
            colorize(
                "No review history exists for this knowledge.",
                C.YELLOW,
            )
        )
        return

    print(
        f"\n"
        f"{bold('=== EDIT REVIEW HISTORY ===')}\n\n"
        f"Knowledge: "
        f"{colorize(number, C.CYAN)} — "
        f"{bold(current_version['title'])}\n"
    )

    for i, r in enumerate(reviews, 1):
        print(
            f"{colorize(str(i), C.CYAN)}  "
            f"{r['reviewed_at']}  "
            f"v{r['major']}.{r['minor']}  "
            f"{fmt_mode(r['mode'])}  "
            f"{fmt_result(r['result'])}"
        )

    while True:
        choice = prompt(
            "\nSelect review number [q to cancel]"
        ).strip()

        if choice.lower() == "q":
            print("Review editing cancelled.")
            return

        if not choice.isdigit():
            print(
                colorize(
                    "Enter a valid review number.",
                    C.RED,
                )
            )
            continue

        index = int(choice)

        if not 1 <= index <= len(reviews):
            print(
                colorize(
                    f"Select a number from 1-{len(reviews)}.",
                    C.RED,
                )
            )
            continue

        break

    review_row = reviews[index - 1]

    current_mode = review_row["mode"]
    current_result = review_row["result"]
    current_answer = review_row["answer"] or ""
    current_reviewed_at = review_row["reviewed_at"]

    print(
        f"\n"
        f"{colorize('=== EDIT REVIEW #' + str(index) + ' ===', C.CYAN + C.BOLD)}\n\n"
        f"Review ID:  {review_row['id']}\n"
        f"Version:    {fmt_version(review_row)}\n"
        f"Mode:       {fmt_mode(current_mode)}\n"
        f"Result:     {fmt_result(current_result)}\n"
        f"Confidence: {review_row['confidence']}%\n"
        f"Reviewed:   {current_reviewed_at}"
    )

    print(
        "\n"
        + dim(
            "The review ID, knowledge item, and reviewed version "
            "cannot be changed."
        )
    )

    # ------------------------------------------------------------
    # Edit mode
    # ------------------------------------------------------------

    while True:
        print(
            "\n"
            + colorize("MODE", C.CYAN + C.BOLD)
            + "\n"
            "  [1] Recall\n"
            "  [2] Explain\n"
            "  [3] Apply\n"
            "  [Enter] Keep current"
        )

        mode_choice = prompt(
            f"Mode [{current_mode}]"
        ).strip().lower()

        if not mode_choice:
            new_mode = current_mode
            break

        mode_mapping = {
            "1": "recall",
            "2": "explain",
            "3": "apply",
            "recall": "recall",
            "explain": "explain",
            "apply": "apply",
        }

        if mode_choice in mode_mapping:
            new_mode = mode_mapping[mode_choice]
            break

        print(
            colorize(
                "Invalid mode.",
                C.RED,
            )
        )

    # ------------------------------------------------------------
    # Edit result
    # ------------------------------------------------------------

    while True:
        print(
            "\n"
            + colorize("RESULT", C.CYAN + C.BOLD)
            + "\n"
            "  [1] Correct\n"
            "  [2] Partial\n"
            "  [3] Wrong\n"
            "  [4] Don't know\n"
            "  [Enter] Keep current"
        )

        result_choice = prompt(
            f"Result [{current_result}]"
        ).strip().lower()

        if not result_choice:
            new_result = current_result
            break

        result_mapping = {
            "1": ("CORRECT", 90),
            "2": ("PARTIAL", 65),
            "3": ("WRONG", 30),
            "4": ("DONT_KNOW", 15),
            "correct": ("CORRECT", 90),
            "partial": ("PARTIAL", 65),
            "wrong": ("WRONG", 30),
            "dont_know": ("DONT_KNOW", 15),
        }

        if result_choice in result_mapping:
            new_result, new_confidence = result_mapping[
                result_choice
            ]
            break

        print(
            colorize(
                "Invalid result.",
                C.RED,
            )
        )

    if not result_choice:
        confidence_mapping = {
            "CORRECT": 90,
            "PARTIAL": 65,
            "WRONG": 30,
            "DONT_KNOW": 15,
        }

        new_confidence = confidence_mapping[
            current_result
        ]

    # ------------------------------------------------------------
    # Edit answer
    # ------------------------------------------------------------

    print(
        "\n"
        + colorize(
            "ANSWER",
            C.CYAN + C.BOLD,
        )
    )

    new_answer = prompt(
        "Your answer",
        default=current_answer,
        multiline=True,
    )

    # ------------------------------------------------------------
    # Edit timestamp
    # ------------------------------------------------------------

    new_reviewed_at = prompt(
        "Reviewed at",
        default=current_reviewed_at,
    ).strip()

    if not new_reviewed_at:
        print(
            colorize(
                "Reviewed timestamp cannot be empty.",
                C.RED,
            )
        )
        return

    # ------------------------------------------------------------
    # Show changes
    # ------------------------------------------------------------

    print(
        "\n"
        + colorize(
            "=== REVIEW CHANGES ===",
            C.YELLOW + C.BOLD,
        )
        + "\n"
        f"Mode:       {fmt_mode(current_mode)} → "
        f"{fmt_mode(new_mode)}\n"
        f"Result:     {fmt_result(current_result)} → "
        f"{fmt_result(new_result)}\n"
        f"Confidence: {review_row['confidence']}% → "
        f"{new_confidence}%\n"
        f"Reviewed:   {current_reviewed_at} → "
        f"{new_reviewed_at}"
    )

    if current_answer != new_answer:
        print(
            f"\n"
            f"{colorize('Answer changed.', C.YELLOW)}"
        )

    confirmation = prompt(
        "\nType SAVE to confirm"
    ).strip()

    if confirmation != "SAVE":
        print("Review editing cancelled.")
        return

    # ------------------------------------------------------------
    # Update review
    # ------------------------------------------------------------

    try:
        conn.execute("BEGIN")

        conn.execute(
            """
            UPDATE reviews
            SET
                mode=?,
                result=?,
                confidence=?,
                answer=?,
                reviewed_at=?
            WHERE id=?
            """,
            (
                new_mode,
                new_result,
                new_confidence,
                new_answer or None,
                new_reviewed_at,
                review_row["id"],
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    print(
        colorize(
            f"\n✓ Review #{index} updated.",
            C.GREEN,
        )
    )