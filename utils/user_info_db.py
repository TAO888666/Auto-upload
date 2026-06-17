from __future__ import annotations

import sqlite3
from pathlib import Path

USER_INFO_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type INTEGER NOT NULL,
    filePath TEXT NOT NULL,
    userName TEXT NOT NULL,
    status INTEGER DEFAULT 0,
    avatarUrl TEXT
)
"""

AVATAR_URL_COLUMN = "avatarUrl"
UNSET = object()


def _normalize_account_name(account_name: str) -> str:
    normalized = str(account_name or "").strip()
    return normalized or "account"


def _build_unique_account_name(
    cursor: sqlite3.Cursor,
    account_type: int,
    account_name: str,
    *,
    exclude_id: int | None = None,
) -> str:
    base_name = _normalize_account_name(account_name)

    def _exists(candidate: str) -> bool:
        query = """
            SELECT 1
            FROM user_info
            WHERE type = ? AND userName = ?
        """
        params: list[object] = [account_type, candidate]
        if exclude_id is not None:
            query += " AND id != ?"
            params.append(exclude_id)
        query += " LIMIT 1"
        return cursor.execute(query, params).fetchone() is not None

    if not _exists(base_name):
        return base_name

    suffix = 2
    while True:
        candidate = f"{base_name}（{suffix}）"
        if not _exists(candidate):
            return candidate
        suffix += 1


def _serialize_user_info_row(row: sqlite3.Row | tuple | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row[0],
        "type": row[1],
        "filePath": row[2],
        "userName": row[3],
        "status": row[4],
        "avatarUrl": row[5],
    }


def ensure_user_info_schema(conn: sqlite3.Connection) -> None:
    conn.execute(USER_INFO_TABLE_SQL)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(user_info)").fetchall()}
    if AVATAR_URL_COLUMN not in columns:
        conn.execute(f"ALTER TABLE user_info ADD COLUMN {AVATAR_URL_COLUMN} TEXT")
    conn.commit()


def ensure_user_info_schema_at_path(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as conn:
        ensure_user_info_schema(conn)


def update_user_info_status(
    database_path: Path,
    row_id: int,
    status_code: int,
    *,
    avatar_url=UNSET,
    account_name=UNSET,
) -> None:
    ensure_user_info_schema_at_path(database_path)
    with sqlite3.connect(database_path) as conn:
        cursor = conn.cursor()
        assignments = ["status = ?"]
        params = [status_code]
        if avatar_url is not UNSET:
            assignments.append("avatarUrl = ?")
            params.append(avatar_url)
        if account_name is not UNSET:
            assignments.append("userName = ?")
            params.append(_normalize_account_name(account_name))
        params.append(row_id)
        cursor.execute(
            f"""
            UPDATE user_info
            SET {", ".join(assignments)}
            WHERE id = ?
            """,
            params,
        )
        conn.commit()


def save_user_info_record(
    database_path: Path,
    account_type: int,
    account_file: Path,
    account_name: str,
    *,
    account_id: int | None = None,
    avatar_url=UNSET,
) -> dict:
    ensure_user_info_schema_at_path(database_path)
    with sqlite3.connect(database_path) as conn:
        cursor = conn.cursor()
        existing_row = None
        if account_id is not None:
            existing_row = cursor.execute(
                """
                SELECT id, filePath, avatarUrl
                FROM user_info
                WHERE id = ?
                LIMIT 1
                """,
                (int(account_id),),
            ).fetchone()

        if existing_row:
            row_id, previous_file, previous_avatar_url = existing_row
            if previous_file and previous_file != account_file.name:
                previous_path = database_path.parent.parent / "cookiesFile" / previous_file
                if previous_path.exists():
                    previous_path.unlink()

            next_account_name = _build_unique_account_name(
                cursor,
                account_type,
                account_name,
                exclude_id=row_id,
            )
            next_avatar_url = previous_avatar_url if avatar_url is UNSET else avatar_url
            cursor.execute(
                """
                UPDATE user_info
                SET type = ?, filePath = ?, userName = ?, status = 1, avatarUrl = ?
                WHERE id = ?
                """,
                (account_type, account_file.name, next_account_name, next_avatar_url, row_id),
            )
        else:
            next_account_name = _build_unique_account_name(cursor, account_type, account_name)
            initial_avatar_url = None if avatar_url is UNSET else avatar_url
            cursor.execute(
                """
                INSERT INTO user_info (type, filePath, userName, status, avatarUrl)
                VALUES (?, ?, ?, ?, ?)
                """,
                (account_type, account_file.name, next_account_name, 1, initial_avatar_url),
            )
            row_id = cursor.lastrowid

        conn.commit()
        saved_row = cursor.execute(
            """
            SELECT id, type, filePath, userName, status, avatarUrl
            FROM user_info
            WHERE id = ?
            LIMIT 1
            """,
            (row_id,),
        ).fetchone()
        return _serialize_user_info_row(saved_row)
