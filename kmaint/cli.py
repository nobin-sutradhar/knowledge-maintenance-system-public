import argparse

from . import db
from .config import load_config
from .ui import (
    C,
    bold,
    colorize,
    dim,
    now,
    show_app_header,
)
from . import knowledge
from .review import (
    review,
    schedule,
    history,
    edit_history,
)


def dashboard(conn, config):
    total = conn.execute(
        "SELECT COUNT(*) FROM knowledge"
    ).fetchone()[0]

    active = conn.execute(
        "SELECT COUNT(*) FROM knowledge WHERE archived=0"
    ).fetchone()[0]

    archived = total - active

    due = len(
        db.due_automatic_reviews(
            conn,
            now(),
            config["daily_limit"],
        )
    )

    custom_due = len(
        db.due_custom_reviews(
            conn,
            now()[:10],
        )
    )

    print(
        "\n"
        + colorize(
            "=== KNOWLEDGE MAINTENANCE SYSTEM ===",
            C.CYAN + C.BOLD,
        )
        + "\n"
    )

    print(
        f"Knowledge:       {bold(str(active))}\n"
        f"Archived:        {dim(str(archived))}\n"
        f"Due today:       {colorize(str(due), C.YELLOW)}\n"
        f"Custom due:      {colorize(str(custom_due), C.MAGENTA)}"
    )

    print(
        "\n"
        + dim(
            "Use 'know --help' to see available commands."
        )
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="know",
        description="Knowledge Maintenance System",
    )

    subparsers = parser.add_subparsers(
        dest="command"
    )

    # ------------------------------------------------------------
    # add
    # ------------------------------------------------------------

    subparsers.add_parser(
        "add",
        help="Add new knowledge",
    )

    # ------------------------------------------------------------
    # list
    # ------------------------------------------------------------

    parser_list = subparsers.add_parser(
        "list",
        help="List knowledge",
    )

    parser_list.add_argument(
        "--archived",
        action="store_true",
        help="Include archived knowledge",
    )

    # ------------------------------------------------------------
    # search
    # ------------------------------------------------------------

    parser_search = subparsers.add_parser(
        "search",
        help="Search knowledge",
    )

    parser_search.add_argument(
        "terms",
        nargs="+",
        help="Search terms",
    )

    # ------------------------------------------------------------
    # show
    # ------------------------------------------------------------

    parser_show = subparsers.add_parser(
        "show",
        help="Show knowledge",
    )

    parser_show.add_argument(
        "number",
        nargs="?",
    )

    # ------------------------------------------------------------
    # edit
    # ------------------------------------------------------------

    parser_edit = subparsers.add_parser(
        "edit",
        help="Edit knowledge",
    )

    parser_edit.add_argument(
        "number",
        nargs="?",
    )

    # ------------------------------------------------------------
    # delete
    # ------------------------------------------------------------

    parser_delete = subparsers.add_parser(
        "delete",
        help="Delete knowledge",
    )

    parser_delete.add_argument(
        "number",
        nargs="?",
    )

    # ------------------------------------------------------------
    # review
    # ------------------------------------------------------------

    subparsers.add_parser(
        "review",
        help="Review due knowledge",
    )

    # ------------------------------------------------------------
    # history
    # ------------------------------------------------------------

    parser_history = subparsers.add_parser(
        "history",
        help="Show knowledge and review history",
    )

    parser_history.add_argument(
        "number",
        nargs="?",
    )

    # ------------------------------------------------------------
    # edit-history
    # ------------------------------------------------------------

    parser_edit_history = subparsers.add_parser(
        "edit-history",
        help="Edit an existing review",
    )

    parser_edit_history.add_argument(
        "number",
        nargs="?",
    )

    # ------------------------------------------------------------
    # clear-history
    # ------------------------------------------------------------

    parser_clear_history = subparsers.add_parser(
        "clear-history",
        help="Clear review history for knowledge",
    )

    parser_clear_history.add_argument(
        "number",
        nargs="?",
    )

    # ------------------------------------------------------------
    # schedule
    # ------------------------------------------------------------

    parser_schedule = subparsers.add_parser(
        "schedule",
        help="Schedule a custom review",
    )

    parser_schedule.add_argument(
        "number",
        nargs="?",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    show_app_header()

    conn = db.connect()
    db.init_db(conn)

    config = load_config()

    try:

        # --------------------------------------------------------
        # Dashboard
        # --------------------------------------------------------

        if args.command is None:
            dashboard(
                conn,
                config,
            )

        # --------------------------------------------------------
        # Knowledge
        # --------------------------------------------------------

        elif args.command == "add":
            knowledge.add(
                conn,
                config,
            )

        elif args.command == "list":
            knowledge.list_items(conn)

        elif args.command == "search":
            knowledge.search(
                conn,
                args.terms,
            )

        elif args.command == "show":
            internal_id = (
                db.resolve_number(
                    conn,
                    args.number,
                )
                if args.number
                else knowledge.choose_item(
                    conn,
                    "show",
                )
            )

            if internal_id:
                k, v = db.get_item(
                    conn,
                    internal_id,
                )

                if k:
                    from .ui import show_card

                    show_card(
                        conn,
                        k,
                        v,
                    )

        elif args.command == "edit":
            internal_id = (
                db.resolve_number(
                    conn,
                    args.number,
                )
                if args.number
                else knowledge.choose_item(
                    conn,
                    "edit",
                )
            )

            if internal_id:
                knowledge.edit(
                    conn,
                    internal_id,
                )

        elif args.command == "delete":
            if args.number:
                internal_id = db.resolve_number(
                    conn,
                    args.number,
                )

                if internal_id:
                    knowledge.delete(
                        conn,
                        internal_id,
                    )
            else:
                knowledge.delete_many(
                    conn,
                )

        # --------------------------------------------------------
        # Review
        # --------------------------------------------------------

        elif args.command == "review":
            review(
                conn,
                config,
            )

        elif args.command == "history":
            internal_id = (
                db.resolve_number(
                    conn,
                    args.number,
                )
                if args.number
                else knowledge.choose_item(
                    conn,
                    "show history for",
                )
            )

            if internal_id:
                history(
                    conn,
                    internal_id,
                )

        elif args.command == "edit-history":
            internal_id = (
                db.resolve_number(
                    conn,
                    args.number,
                )
                if args.number
                else knowledge.choose_item(
                    conn,
                    "edit review history for",
                )
            )

            if internal_id:
                edit_history(
                    conn,
                    internal_id,
                )

        elif args.command == "clear-history":
            internal_id = (
                db.resolve_number(
                    conn,
                    args.number,
                )
                if args.number
                else knowledge.choose_item(
                    conn,
                    "clear review history for",
                )
            )

            if internal_id:
                knowledge.clear_review_history(
                    conn,
                    internal_id,
                )

        elif args.command == "schedule":
            internal_id = (
                db.resolve_number(
                    conn,
                    args.number,
                )
                if args.number
                else None
            )

            schedule(
                conn,
                internal_id,
            )

    finally:
        conn.close()