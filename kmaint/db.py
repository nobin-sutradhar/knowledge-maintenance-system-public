import sqlite3
import uuid

from .config import DB_PATH


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS knowledge (
            internal_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'UNVERIFIED',
            confidence INTEGER NOT NULL DEFAULT 40,
            priority INTEGER NOT NULL DEFAULT 5,
            review_mode TEXT NOT NULL DEFAULT 'recall',
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            last_reviewed TEXT,
            next_review TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_id TEXT NOT NULL,
            major INTEGER NOT NULL,
            minor INTEGER NOT NULL,
            title TEXT NOT NULL,
            claim TEXT NOT NULL,
            explanation TEXT,
            source TEXT,
            change_reason TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (knowledge_id)
                REFERENCES knowledge(internal_id)
                ON DELETE CASCADE,
            UNIQUE (knowledge_id, major, minor)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_id TEXT NOT NULL,
            major INTEGER NOT NULL,
            minor INTEGER NOT NULL,
            mode TEXT NOT NULL DEFAULT 'recall',
            result TEXT NOT NULL,
            confidence INTEGER NOT NULL,
            answer TEXT,
            reviewed_at TEXT NOT NULL,
            FOREIGN KEY (knowledge_id)
                REFERENCES knowledge(internal_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS custom_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_id TEXT NOT NULL,
            scheduled_for TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY (knowledge_id)
                REFERENCES knowledge(internal_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_review_due
            ON knowledge(next_review);

        CREATE INDEX IF NOT EXISTS idx_custom_review_due
            ON custom_reviews(scheduled_for, completed_at);

        CREATE INDEX IF NOT EXISTS idx_versions_knowledge
            ON knowledge_versions(knowledge_id);

        CREATE INDEX IF NOT EXISTS idx_reviews_knowledge
            ON reviews(knowledge_id, reviewed_at);
        """
    )

    conn.commit()

    # ------------------------------------------------------------
    # Knowledge table migrations
    # ------------------------------------------------------------

    columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(knowledge)"
        ).fetchall()
    }

    if "review_mode" not in columns:
        conn.execute(
            """
            ALTER TABLE knowledge
            ADD COLUMN review_mode TEXT NOT NULL DEFAULT 'recall'
            """
        )

    if "archived" not in columns:
        conn.execute(
            """
            ALTER TABLE knowledge
            ADD COLUMN archived INTEGER NOT NULL DEFAULT 0
            """
        )

    # ------------------------------------------------------------
    # Reviews table migrations
    # ------------------------------------------------------------

    review_columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(reviews)"
        ).fetchall()
    }

    if "mode" not in review_columns:
        conn.execute(
            """
            ALTER TABLE reviews
            ADD COLUMN mode TEXT NOT NULL DEFAULT 'recall'
            """
        )

    conn.commit()


def make_internal_id(conn):
    while True:
        candidate = uuid.uuid4().hex

        if (
            conn.execute(
                "SELECT 1 FROM knowledge WHERE internal_id=?",
                (candidate,),
            ).fetchone()
            is None
        ):
            return candidate


def all_items(conn, include_archived=True):
    where = "" if include_archived else "WHERE archived=0"

    return conn.execute(
        f"""
        SELECT *
        FROM knowledge
        {where}
        ORDER BY created_at ASC, internal_id ASC
        """
    ).fetchall()


def display_number(conn, internal_id):
    for i, row in enumerate(all_items(conn), 1):
        if row["internal_id"] == internal_id:
            return f"{i:04d}"

    return None


def resolve_number(conn, value):
    if (
        value is None
        or not str(value).isdigit()
        or int(value) < 1
    ):
        return None

    rows = all_items(conn)
    number = int(value)

    if number <= len(rows):
        return rows[number - 1]["internal_id"]

    return None


def latest_version(conn, internal_id):
    return conn.execute(
        """
        SELECT *
        FROM knowledge_versions
        WHERE knowledge_id=?
        ORDER BY major DESC, minor DESC
        LIMIT 1
        """,
        (internal_id,),
    ).fetchone()


def get_item(conn, internal_id):
    knowledge = conn.execute(
        """
        SELECT *
        FROM knowledge
        WHERE internal_id=?
        """,
        (internal_id,),
    ).fetchone()

    return (
        (knowledge, latest_version(conn, internal_id))
        if knowledge
        else (None, None)
    )


def all_items_with_latest(conn, include_archived=True):
    where = "" if include_archived else "WHERE k.archived=0"

    return conn.execute(
        f"""
        SELECT
            k.*,
            v.major,
            v.minor,
            v.title,
            v.claim,
            v.explanation,
            v.source,
            v.change_reason,
            v.created_at AS version_created_at
        FROM knowledge k
        JOIN knowledge_versions v
            ON v.id=(
                SELECT v2.id
                FROM knowledge_versions v2
                WHERE v2.knowledge_id=k.internal_id
                ORDER BY v2.major DESC, v2.minor DESC
                LIMIT 1
            )
        {where}
        ORDER BY k.created_at ASC, k.internal_id ASC
        """
    ).fetchall()


def search_items(conn, terms, include_archived=True):
    terms = [
        term.strip().lower()
        for term in terms
        if term.strip()
    ]

    rows = all_items_with_latest(
        conn,
        include_archived,
    )

    if not terms:
        return rows

    scored = []

    for row in rows:
        fields = {
            key: (row[key] or "").lower()
            for key in (
                "title",
                "claim",
                "explanation",
                "source",
            )
        }

        score = 0
        matched = []

        for term in terms:
            score_for_term = (
                8 * int(term in fields["title"])
                + 6 * int(term in fields["claim"])
                + 3 * int(term in fields["explanation"])
                + 2 * int(term in fields["source"])
            )

            if score_for_term:
                score += score_for_term
                matched.append(term)

        if matched:
            coverage = (
                len(set(matched))
                / len(set(terms))
            )

            score += int(coverage * 10)

            scored.append(
                (
                    score,
                    coverage,
                    row,
                )
            )

    scored.sort(
        key=lambda x: (
            -x[0],
            -x[1],
            -x[2]["priority"],
            x[2]["created_at"],
        )
    )

    return [
        row
        for _, _, row in scored
    ]


def due_custom_reviews(conn, date_string):
    return conn.execute(
        """
        SELECT
            cr.*,
            k.internal_id,
            k.status,
            k.confidence,
            k.priority,
            k.review_mode,
            k.last_reviewed,
            k.next_review,
            k.archived,
            v.major,
            v.minor,
            v.title,
            v.claim,
            v.explanation,
            v.source
        FROM custom_reviews cr
        JOIN knowledge k
            ON k.internal_id=cr.knowledge_id
        JOIN knowledge_versions v
            ON v.id=(
                SELECT v2.id
                FROM knowledge_versions v2
                WHERE v2.knowledge_id=k.internal_id
                ORDER BY v2.major DESC, v2.minor DESC
                LIMIT 1
            )
        WHERE cr.scheduled_for<=?
          AND cr.completed_at IS NULL
          AND k.archived=0
        ORDER BY
            cr.scheduled_for ASC,
            k.priority DESC,
            k.created_at ASC
        """,
        (date_string,),
    ).fetchall()


def due_automatic_reviews(conn, cutoff, daily_limit):
    if daily_limit <= 0:
        return []

    return conn.execute(
        """
        SELECT
            k.*,
            v.major,
            v.minor,
            v.title,
            v.claim,
            v.explanation,
            v.source
        FROM knowledge k
        JOIN knowledge_versions v
            ON v.id=(
                SELECT v2.id
                FROM knowledge_versions v2
                WHERE v2.knowledge_id=k.internal_id
                ORDER BY v2.major DESC, v2.minor DESC
                LIMIT 1
            )
        WHERE k.next_review<=?
          AND k.archived=0
        ORDER BY
            k.priority DESC,
            k.next_review ASC,
            k.created_at ASC
        LIMIT ?
        """,
        (
            cutoff,
            daily_limit,
        ),
    ).fetchall()