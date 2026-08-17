"""SQLite storage layer for per-user bot configuration and whitelists."""

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id            INTEGER PRIMARY KEY,
    connection_id      TEXT,
    connection_enabled INTEGER NOT NULL DEFAULT 0,
    mode               TEXT NOT NULL DEFAULT 'ignore'
);
CREATE TABLE IF NOT EXISTS known_senders (
    owner_id  INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    name      TEXT NOT NULL,
    PRIMARY KEY (owner_id, sender_id)
);
CREATE TABLE IF NOT EXISTS whitelist (
    owner_id  INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    name      TEXT NOT NULL,
    PRIMARY KEY (owner_id, sender_id)
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()

    async def _fetchone(self, query: str, params: tuple):
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(query, params)
            return await cur.fetchone()

    async def _fetchall(self, query: str, params: tuple):
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(query, params)
            return await cur.fetchall()

    async def _execute(self, query: str, params: tuple):
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(query, params)
            await conn.commit()

    # --- user config -------------------------------------------------------

    async def upsert_user(self, user_id: int):
        await self._execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )

    async def upsert_connection(self, user_id: int, connection_id: str, enabled: bool):
        await self._execute(
            """
            INSERT INTO users (user_id, connection_id, connection_enabled)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                connection_id = excluded.connection_id,
                connection_enabled = excluded.connection_enabled
            """,
            (user_id, connection_id, int(enabled)),
        )

    async def get_user(self, user_id: int):
        return await self._fetchone(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )

    async def get_by_connection(self, connection_id: str):
        return await self._fetchone(
            "SELECT * FROM users WHERE connection_id = ?", (connection_id,)
        )

    async def set_mode(self, user_id: int, mode: str):
        await self.upsert_user(user_id)
        await self._execute(
            "UPDATE users SET mode = ? WHERE user_id = ?", (mode, user_id)
        )

    # --- senders / whitelist ----------------------------------------------

    async def remember_sender(self, owner_id: int, sender_id: int, name: str):
        await self._execute(
            """
            INSERT INTO known_senders (owner_id, sender_id, name) VALUES (?, ?, ?)
            ON CONFLICT(owner_id, sender_id) DO UPDATE SET name = excluded.name
            """,
            (owner_id, sender_id, name),
        )

    async def get_sender_name(self, owner_id: int, sender_id: int) -> str | None:
        row = await self._fetchone(
            "SELECT name FROM known_senders WHERE owner_id = ? AND sender_id = ?",
            (owner_id, sender_id),
        )
        return row["name"] if row else None

    async def add_to_whitelist(self, owner_id: int, sender_id: int, name: str):
        await self._execute(
            "INSERT OR REPLACE INTO whitelist (owner_id, sender_id, name) VALUES (?, ?, ?)",
            (owner_id, sender_id, name),
        )

    async def remove_from_whitelist(self, owner_id: int, sender_id: int):
        await self._execute(
            "DELETE FROM whitelist WHERE owner_id = ? AND sender_id = ?",
            (owner_id, sender_id),
        )

    async def is_whitelisted(self, owner_id: int, sender_id: int) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM whitelist WHERE owner_id = ? AND sender_id = ?",
            (owner_id, sender_id),
        )
        return row is not None

    async def list_whitelist(self, owner_id: int):
        return await self._fetchall(
            "SELECT sender_id, name FROM whitelist WHERE owner_id = ? ORDER BY name",
            (owner_id,),
        )
