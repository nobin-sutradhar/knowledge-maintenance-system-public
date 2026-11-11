import re

from datetime import datetime, timedelta

from . import db

from .config import VALID_MODES

from .ui import (
    C,
    bold,
    colorize,
    dim,
    prompt,
    parse_priority,
    fmt_version,
    print_result_row,
    show_card,
)


def choose_item(conn, action="select", include_archived=True):

    rows = db.all_items_with_latest(conn, include_archived)

    if not rows:
        print(colorize("\nNo knowledge captured yet.", C.YELLOW))
        return None

    print(f"\n{bold('=== SELECT KNOWLEDGE TO ' + action.upper() + ' ===')}")

    term = input("Search (press Enter to browse all): ").strip()

    rows = (
        db.search_items(conn, term.split(), include_archived)
        if term
        else rows
    )

    if not rows:
        print(colorize("No matching knowledge found.", C.YELLOW))
        return None

    for i, row in enumerate(rows, 1):
        print_result_row(conn, row, row, i)

    while True:

        raw = input("\nSelect result [q to cancel]: ").strip().lower()

        if raw == "q":
            return None

        try:
            if 1 <= int(raw) <= len(rows):
                return rows[int(raw) - 1]["internal_id"]

        except ValueError:
            pass

        print(colorize("Invalid selection.", C.RED))


def add(conn, config):

    print("\n" + bold("=== NEW KNOWLEDGE ==="))

    title = prompt("Title", required=True)
    claim = prompt("\nClaim", required=True, multiline=True)
    explanation = prompt("Explanation (optional)", multiline=True)
    source = prompt("Source (optional)")

    try:
        confidence = max(
            0,
            min(
                100,
                int(prompt("Confidence 0-100", default="40"))
            )
        )
    except ValueError:
        confidence = 40

    priority = parse_priority()

    mode = prompt(
        "Review mode [recall/explain/apply]",
        default=config["review_mode"]
    ).lower()

    mode = (
        mode
        if mode in VALID_MODES
        else config["review_mode"]
    )

    custom = prompt(
        "Custom review date YYYY-MM-DD (optional)"
    )

    internal = db.make_internal_id(conn)

    created = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    first = (
        datetime.now()
        .astimezone()
        + timedelta(days=config["default_review_days"])
    ).isoformat(timespec="seconds")

    conn.execute(
        """
        INSERT INTO knowledge
        (
            internal_id,
            status,
            confidence,
            priority,
            review_mode,
            archived,
            created_at,
            next_review
        )
        VALUES (?, 'UNVERIFIED', ?, ?, ?, 0, ?, ?)
        """,
        (
            internal,
            confidence,
            priority,
            mode,
            created,
            first,
        ),
    )

    # Initial knowledge version is v1.0.
    #
    # knowledge_versions has 9 columns:
    #   knowledge_id
    #   major
    #   minor
    #   title
    #   claim
    #   explanation
    #   source
    #   change_reason
    #   created_at
    #
    # major=1 and minor=0 are literal values, so six
    # placeholders are required for the remaining fields.
    conn.execute(
        """
        INSERT INTO knowledge_versions
        (
            knowledge_id,
            major,
            minor,
            title,
            claim,
            explanation,
            source,
            change_reason,
            created_at
        )
        VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?)
        """,
        (
            internal,
            title,
            claim,
            explanation,
            source,
            "Initial capture",
            created,
        ),
    )

    if custom and re.fullmatch(r"\d{4}-\d{2}-\d{2}", custom):

        conn.execute(
            """
            INSERT INTO custom_reviews
            (
                knowledge_id,
                scheduled_for
            )
            VALUES (?, ?)
            """,
            (
                internal,
                custom,
            ),
        )

    elif custom:

        print(
            colorize(
                "Invalid custom review date; skipped.",
                C.YELLOW,
            )
        )

    conn.commit()

    print(
        f"\n"
        f"{colorize('✓', C.GREEN)} "
        f"Created knowledge "
        f"{colorize(db.display_number(conn, internal), C.CYAN)} "
        f"— "
        f"{colorize('v1.0', C.MAGENTA)}"
    )

    show_card(conn, internal)


def edit(conn, internal):

    k, v = db.get_item(conn, internal)

    if not k:
        print(colorize("Knowledge item not found.", C.RED))
        return

    print(
        f"\n"
        f"{bold(f'=== EDIT KNOWLEDGE {db.display_number(conn, internal)} ({fmt_version(v)}) ===')}"
    )

    title = prompt("Title", v["title"])
    claim = prompt(
        "\nClaim",
        default=v["claim"],
        required=True,
        multiline=True,
    )

    explanation = prompt(
        "Explanation",
        default=v["explanation"],
        multiline=True,
    )
    source = prompt(
        "Source",
        v["source"] or ""
    )

    print(
        "\nVersion type:"
        "\n  [1] Minor — refinement / clarification"
        "\n  [2] Major — fundamental correction"
    )

    choice = input("Choose [1]: ").strip() or "1"

    if choice == "2":
        major, minor = v["major"] + 1, 0
    else:
        major, minor = v["major"], v["minor"] + 1

    reason = prompt(
        "Why is the knowledge changing?",
        required=True
    )

    created = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    conn.execute(
        """
        INSERT INTO knowledge_versions
        (
            knowledge_id,
            major,
            minor,
            title,
            claim,
            explanation,
            source,
            change_reason,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            internal,
            major,
            minor,
            title,
            claim,
            explanation,
            source,
            reason,
            created,
        ),
    )

    conn.commit()

    print(
        f"\n"
        f"{colorize('✓', C.GREEN)} "
        f"Created "
        f"{colorize(db.display_number(conn, internal), C.CYAN)} "
        f"— "
        f"{colorize(f'v{major}.{minor}', C.MAGENTA)}"
    )

    show_card(conn, internal)


def list_items(conn):

    rows = db.all_items_with_latest(conn)

    if not rows:
        print(
            colorize(
                "\nNo knowledge captured yet.",
                C.YELLOW,
            )
        )
        return

    print("\n" + bold("=== KNOWLEDGE ===") + "\n")

    for row in rows:
        print_result_row(conn, row, row)
        print()


def search(conn, terms):

    rows = db.search_items(conn, terms)

    print(
        f"\n"
        f"{bold('=== SEARCH: ' + ' '.join(terms) + ' ===')}"
        f"\n"
    )

    if not rows:
        print(
            colorize(
                "No matching knowledge found.",
                C.YELLOW,
            )
        )
        return

    for i, row in enumerate(rows, 1):
        print_result_row(conn, row, row, i)
        print()


def archive(conn, internal):

    k, v = db.get_item(conn, internal)

    if not k:
        print(
            colorize(
                "Knowledge item not found.",
                C.RED,
            )
        )
        return

    if k["archived"]:
        print(
            colorize(
                "Knowledge is already archived.",
                C.YELLOW,
            )
        )
        return

    print(
        f"\n"
        f"Archive "
        f"{colorize(db.display_number(conn, internal), C.CYAN)} "
        f"— "
        f"{bold(v['title'])}"
    )

    print(
        "Archived knowledge stays searchable and keeps its full history, "
        "but leaves active review queues."
    )

    if input("Type ARCHIVE to confirm: ").strip() != "ARCHIVE":
        print("Archive cancelled.")
        return

    conn.execute(
        "UPDATE knowledge SET archived=1 WHERE internal_id=?",
        (internal,),
    )

    conn.commit()

    print(
        colorize(
            "✓ Knowledge archived.",
            C.GREEN,
        )
    )


def restore(conn, internal):

    k, v = db.get_item(conn, internal)

    if not k:
        print(
            colorize(
                "Knowledge item not found.",
                C.RED,
            )
        )
        return

    if not k["archived"]:
        print(
            colorize(
                "Knowledge is not archived.",
                C.YELLOW,
            )
        )
        return

    conn.execute(
        "UPDATE knowledge SET archived=0 WHERE internal_id=?",
        (internal,),
    )

    conn.commit()

    print(
        colorize(
            "✓ Knowledge restored to active maintenance.",
            C.GREEN,
        )
    )


def delete(conn, internal):

    k, v = db.get_item(conn, internal)

    if not k:
        print(
            colorize(
                "Knowledge item not found.",
                C.RED,
            )
        )
        return

    number = db.display_number(conn, internal)

    print(
        f"\n"
        f"You are about to delete knowledge {number}:"
        f"\n  {v['title']}"
        f"\n  {v['claim']}"
    )

    print(
        colorize(
            "\nThis permanently removes its versions, reviews, and custom reviews.",
            C.RED,
        )
    )

    if input("Type DELETE to confirm: ").strip() != "DELETE":
        print("Deletion cancelled.")
        return

    conn.execute(
        "DELETE FROM knowledge WHERE internal_id=?",
        (internal,),
    )

    conn.commit()

    print(
        colorize(
            f"✓ Deleted knowledge {number}.",
            C.GREEN,
        )
    )

def delete_many(conn):
    """
    Interactively select and permanently delete multiple knowledge items.

    Selection uses the currently displayed knowledge list numbers.

    Supported input:
        1
        1 3 5
        1,3,5
        1-4
        1 3-5 8
    """

    rows = db.all_items_with_latest(conn)

    if not rows:
        print(
            colorize(
                "\nNo knowledge captured yet.",
                C.YELLOW,
            )
        )
        return

    print(
        "\n"
        + bold("=== SELECT KNOWLEDGE TO DELETE ===")
        + "\n"
    )

    for i, row in enumerate(rows, 1):
        print_result_row(
            conn,
            row,
            row,
            i,
        )
        print()

    print(
        dim(
            "Enter numbers separated by spaces or commas."
        )
    )

    print(
        dim(
            "Ranges are supported, e.g. 1-4 or 1 3-5 8."
        )
    )

    print()

    while True:
        raw = prompt(
            "Select knowledge [q to cancel]"
        ).strip()

        if raw.lower() == "q":
            print("Deletion cancelled.")
            return

        try:
            selected_indexes = _parse_delete_selection(
                raw,
                len(rows),
            )
        except ValueError as exc:
            print(
                colorize(
                    str(exc),
                    C.RED,
                )
            )
            continue

        if not selected_indexes:
            print(
                colorize(
                    "No knowledge selected.",
                    C.RED,
                )
            )
            continue

        break

    selected_rows = [
        rows[index - 1]
        for index in selected_indexes
    ]

    print(
        "\n"
        + colorize(
            "=== KNOWLEDGE TO DELETE ===",
            C.RED + C.BOLD,
        )
        + "\n"
    )

    for row in selected_rows:
        number = db.display_number(
            conn,
            row["internal_id"],
        )

        print(
            f"  {colorize(number, C.CYAN)}  "
            f"{colorize(fmt_version(row), C.MAGENTA)}  "
            f"{bold(row['title'])}"
        )

    count = len(selected_rows)

    print(
        "\n"
        + colorize(
            f"This will permanently delete {count} "
            f"knowledge item{'s' if count != 1 else ''}, "
            f"including versions, reviews, and custom reviews.",
            C.RED,
        )
    )

    confirmation = prompt(
        "Type DELETE to confirm"
    ).strip()

    if confirmation != "DELETE":
        print("Deletion cancelled.")
        return

    internal_ids = [
        row["internal_id"]
        for row in selected_rows
    ]

    try:
        placeholders = ",".join(
            "?"
            for _ in internal_ids
        )

        conn.execute("BEGIN")

        conn.execute(
            f"""
            DELETE FROM knowledge
            WHERE internal_id IN ({placeholders})
            """,
            internal_ids,
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    print(
        colorize(
            f"\n✓ Deleted {count} knowledge "
            f"item{'s' if count != 1 else ''}.",
            C.GREEN,
        )
    )


def _parse_delete_selection(raw, maximum):
    """
    Convert selection syntax into sorted unique indexes.

    Examples:
        1
        1 3 5
        1,3,5
        1-4
        1 3-5 8
    """

    tokens = re.split(
        r"[,\s]+",
        raw.strip(),
    )

    selected = set()

    for token in tokens:
        if not token:
            continue

        if re.fullmatch(r"\d+", token):
            number = int(token)

            if not 1 <= number <= maximum:
                raise ValueError(
                    f"Selection {number} is outside the available "
                    f"range 1-{maximum}."
                )

            selected.add(number)
            continue

        match = re.fullmatch(
            r"(\d+)-(\d+)",
            token,
        )

        if match:
            start = int(match.group(1))
            end = int(match.group(2))

            if start > end:
                raise ValueError(
                    f"Invalid range '{token}'. "
                    "The first number must be <= the second."
                )

            if start < 1 or end > maximum:
                raise ValueError(
                    f"Range '{token}' is outside the available "
                    f"range 1-{maximum}."
                )

            selected.update(
                range(start, end + 1)
            )
            continue

        raise ValueError(
            f"Invalid selection '{token}'. "
            "Use numbers or ranges such as 1 3-5 8."
        )

    return sorted(selected)



def clear_review_history(conn, internal):
    """
    Permanently remove review history for one knowledge item.

    Knowledge, versions, and the current knowledge state remain intact.
    """

    k, v = db.get_item(conn, internal)

    if not k:
        print(
            colorize(
                "Knowledge item not found.",
                C.RED,
            )
        )
        return

    number = db.display_number(conn, internal)

    review_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM reviews
        WHERE knowledge_id=?
        """,
        (internal,),
    ).fetchone()[0]

    print(
        f"\n"
        f"{bold('=== CLEAR REVIEW HISTORY ===')}\n\n"
        f"Knowledge: {colorize(number, C.CYAN)} — {bold(v['title'])}\n"
        f"Reviews:   {review_count}"
    )

    if review_count == 0:
        print(
            colorize(
                "\nNo review history exists for this knowledge.",
                C.YELLOW,
            )
        )
        return

    print(
        colorize(
            "\nThis permanently removes only the review history.",
            C.RED,
        )
    )

    print(
        "The knowledge, versions, status, confidence, and other "
        "knowledge data will NOT be deleted."
    )

    confirmation = prompt(
        "\nType CLEAR HISTORY to confirm"
    ).strip()

    if confirmation != "CLEAR HISTORY":
        print("History clearing cancelled.")
        return

    try:
        conn.execute("BEGIN")

        conn.execute(
            """
            DELETE FROM reviews
            WHERE knowledge_id=?
            """,
            (internal,),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    print(
        colorize(
            f"\n✓ Cleared {review_count} review "
            f"record{'s' if review_count != 1 else ''} "
            f"from knowledge {number}.",
            C.GREEN,
        )
    )