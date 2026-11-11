import re
import sys
import textwrap
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_MAGENTA = "\033[95m"


# ---------------------------------------------------------------------------
# Terminal output
# ---------------------------------------------------------------------------

def colorize(text, color):
    return str(text) if not sys.stdout.isatty() else f"{color}{text}{C.RESET}"


def bold(text):
    return colorize(text, C.BOLD)


def dim(text):
    return colorize(text, C.DIM)


def status_color(status):
    return {
        "CAPTURED": C.BLUE,
        "UNVERIFIED": C.YELLOW,
        "CONFUSED": C.RED,
        "VERIFIED": C.GREEN,
        "MASTERED": C.BRIGHT_GREEN,
    }.get(status, C.WHITE)


def result_color(result):
    return {
        "CORRECT": C.GREEN,
        "PARTIAL": C.YELLOW,
        "WRONG": C.RED,
        "DONT_KNOW": C.RED,
    }.get(result, C.WHITE)


def mode_color(mode):
    return {
        "recall": C.CYAN,
        "explain": C.BLUE,
        "apply": C.MAGENTA,
    }.get(mode, C.WHITE)


def fmt_status(status):
    return colorize(status, status_color(status))


def fmt_result(result):
    return colorize(result, result_color(result))


def fmt_mode(mode):
    return colorize(mode.upper(), mode_color(mode))


# ---------------------------------------------------------------------------
# Terminal input
# ---------------------------------------------------------------------------

def _build_key_bindings():
    """
    Application-level terminal editing behavior.

    Normal Backspace/Delete and cursor movement are provided by
    prompt_toolkit itself.

    We only add word-deletion shortcuts that do not interfere with
    normal Backspace.
    """

    bindings = KeyBindings()

    @bindings.add("c-w")
    def delete_previous_word(event):
        buffer = event.current_buffer
        text_before = buffer.document.text_before_cursor

        match = re.search(r"\S+\s*$", text_before)

        if match:
            buffer.delete_before_cursor(
                len(match.group(0))
            )

    @bindings.add("escape", "backspace")
    def delete_previous_word_alt(event):
        buffer = event.current_buffer
        text_before = buffer.document.text_before_cursor

        match = re.search(r"\S+\s*$", text_before)

        if match:
            buffer.delete_before_cursor(
                len(match.group(0))
            )

    return bindings


_PROMPT_SESSION = None
_KEY_BINDINGS = _build_key_bindings()


def show_app_header():
    width = 72
    title = "UPDATE & UPGRADE YOUR MENTAL OS"

    print()
    print(colorize("╭" + "─" * width + "╮", C.CYAN))
    print(
        "│"
        + pad_visible(
            title.center(width),
            width,
        )
        + "│"
    )
    print(colorize("╰" + "─" * width + "╯", C.CYAN))
    print()


def _get_prompt_session():
    global _PROMPT_SESSION

    if _PROMPT_SESSION is None:
        _PROMPT_SESSION = PromptSession(
            key_bindings=_KEY_BINDINGS,
        )

    return _PROMPT_SESSION


def prompt(label, default=None, required=False, multiline=False):
    """
    Read user input through the terminal UI boundary.

    Single-line input:
        - Arrow keys
        - Home / End
        - Backspace / Delete
        - word movement
        - word deletion

    Multiline input:
        - Enter inserts a newline
        - Alt+Enter accepts/submits the field

    Non-interactive stdin/stdout falls back to Python input(), which keeps
    the function usable in tests and piped/non-TTY environments.
    """

    if multiline:
        # For multiline fields, the existing value must live inside
        # the editor rather than being displayed as part of the label.
        message = f"{label}:\n"
    else:
        suffix = f" [{default}]" if default is not None else ""
        message = f"{label}{suffix}: "

    while True:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            value = input(message)
        else:
            session = _get_prompt_session()

            value = session.prompt(
                message,
                default="" if default is None else str(default),
                multiline=multiline,
            )

        if not value and default is not None:
            return default

        if value or not required:
            return value.strip()

        print(colorize("This field is required.", C.RED))


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def parse_priority(default=5):
    try:
        return max(
            1,
            min(
                10,
                int(prompt("Priority 1-10", default=str(default))),
            ),
        )
    except ValueError:
        print(colorize("Invalid priority; using 5.", C.YELLOW))
        return 5


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def relative_days(value):
    target = datetime.fromisoformat(value).date()
    today = datetime.now().astimezone().date()
    days = (target - today).days

    if days == 0:
        return "today"

    if days > 0:
        return f"in {days} day{'s' if days != 1 else ''}"

    return f"{abs(days)} day(s) overdue"


def fmt_version(row):
    return f"v{row['major']}.{row['minor']}"


# ---------------------------------------------------------------------------
# Knowledge list rendering
# ---------------------------------------------------------------------------

def print_result_row(conn, knowledge, version, index=None):
    from .db import display_number

    number = display_number(conn, knowledge["internal_id"])
    prefix = f"[{index}] " if index is not None else ""

    archived = (
        colorize(" ARCHIVED", C.DIM)
        if knowledge["archived"]
        else ""
    )

    print(
        f"{prefix}"
        f"{colorize(number, C.CYAN)}  "
        f"{colorize(fmt_version(version), C.MAGENTA)}  "
        f"{fmt_status(knowledge['status'])}  "
        f"{knowledge['confidence']:>3}%  "
        f"P{knowledge['priority']}  "
        f"{bold(version['title'])}"
        f"{archived}"
    )

    print(f"     {dim(version['claim'])}")


# ---------------------------------------------------------------------------
# Knowledge card formatting
# ---------------------------------------------------------------------------

def visible_len(value):
    return len(
        re.sub(
            r"\x1b\[[0-?]*[ -/]*[@-~]",
            "",
            str(value),
        )
    )


def pad_visible(value, width):
    return str(value) + " " * max(
        0,
        width - visible_len(value),
    )


def wrap_text(value, width):
    """
    Wrap text while preserving explicit newlines.

    Each newline represents a real line entered by the user.
    Long individual lines are wrapped to the available width.
    """

    text = str(value or "—")

    output = []

    for logical_line in text.splitlines():
        if not logical_line:
            output.append("")
            continue

        wrapped = textwrap.wrap(
            logical_line,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
        )

        output.extend(wrapped or [""])

    return output or ["—"]


def card_lines(
    label,
    value,
    label_color=C.WHITE,
    value_color=None,
    width=76,
):
    label_width = 12
    value_width = width - label_width - 2

    label_text = colorize(
        label + ":",
        label_color,
    )

    output = []

    for index, part in enumerate(
        wrap_text(value, value_width)
    ):
        rendered = (
            colorize(part, value_color)
            if value_color
            else part
        )

        if index == 0:
            left = (
                " "
                + pad_visible(label_text, label_width)
                + " "
                + pad_visible(rendered, value_width)
            )
        else:
            left = (
                " "
                + " " * label_width
                + " "
                + pad_visible(rendered, value_width)
            )

        output.append("│" + left + "│")

    return output


def show_card(conn, internal_id, version=None):
    from .db import display_number, latest_version

    knowledge = conn.execute(
        "SELECT * FROM knowledge WHERE internal_id=?",
        (internal_id,),
    ).fetchone()

    if not knowledge:
        print(
            colorize(
                "Knowledge item not found.",
                C.RED,
            )
        )
        return False

    if version is None:
        current_version = latest_version(
            conn,
            internal_id,
        )
    else:
        major, minor = map(
            int,
            version.lower()
            .lstrip("v")
            .split("."),
        )

        current_version = conn.execute(
            """
            SELECT *
            FROM knowledge_versions
            WHERE knowledge_id=?
              AND major=?
              AND minor=?
            """,
            (
                internal_id,
                major,
                minor,
            ),
        ).fetchone()

    if not current_version:
        print(
            colorize(
                "Version not found.",
                C.RED,
            )
        )
        return False

    width = 76
    line = "─" * width
    number = display_number(
        conn,
        internal_id,
    )

    print(
        "\n"
        + colorize(
            "╭" + line + "╮",
            C.CYAN,
        )
    )

    heading = colorize(
        f"KNOWLEDGE {number}",
        C.BRIGHT_CYAN + C.BOLD,
    )

    print(
        "│"
        + pad_visible(
            " " + heading,
            width,
        )
        + "│"
    )

    print(
        colorize(
            "├" + line + "┤",
            C.CYAN,
        )
    )

    rows = (
        card_lines(
            "Title",
            current_version["title"],
            C.WHITE,
            C.BOLD,
        )
        + card_lines(
            "Claim",
            current_version["claim"],
            C.CYAN,
        )
    )

    if current_version["explanation"]:
        rows.append(
            "│"
            + " " * width
            + "│"
        )

        rows += card_lines(
            "Explanation",
            current_version["explanation"],
            C.CYAN,
        )

    rows += card_lines(
        "Version",
        fmt_version(current_version),
        C.MAGENTA,
    )

    rows += card_lines(
        "Source",
        current_version["source"] or "—",
        C.DIM,
    )

    rows += card_lines(
        "Status",
        knowledge["status"],
        status_color(knowledge["status"]),
        status_color(knowledge["status"]),
    )

    rows += card_lines(
        "Confidence",
        str(knowledge["confidence"]) + "%",
        C.GREEN,
    )

    rows += card_lines(
        "Priority",
        str(knowledge["priority"]) + "/10",
        C.YELLOW,
    )

    rows += card_lines(
        "Review mode",
        knowledge["review_mode"].upper(),
        C.CYAN,
        mode_color(knowledge["review_mode"]),
    )

    if knowledge["archived"]:
        rows += card_lines(
            "Archived",
            "YES",
            C.DIM,
            C.DIM,
        )

    rows += card_lines(
        "Created",
        knowledge["created_at"],
        C.DIM,
    )

    rows += card_lines(
        "Last review",
        knowledge["last_reviewed"] or "Never",
        C.DIM,
    )

    rows += card_lines(
        "Next review",
        knowledge["next_review"],
        C.BRIGHT_GREEN,
        C.BRIGHT_GREEN,
    )

    for row in rows:
        print(row)

    print(
        colorize(
            "╰" + line + "╯",
            C.CYAN,
        )
    )

    return True