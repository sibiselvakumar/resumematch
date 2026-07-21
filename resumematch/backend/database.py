import json
import uuid
import aiosqlite
from pathlib import Path
from typing import Optional

DB_PATH = Path("resumematch.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                jd_text TEXT,
                role_title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                candidate_name TEXT,
                overall_score INTEGER,
                recommendation TEXT,
                result_json TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jd_analysis_cache (
                jd_hash TEXT PRIMARY KEY,
                jd_requirements_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def get_cached_jd_requirements(jd_hash: str) -> Optional[dict]:
    """Look up a previously extracted JD requirements JSON by its text hash."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT jd_requirements_json FROM jd_analysis_cache WHERE jd_hash = ?", (jd_hash,)
        ) as cursor:
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None


async def save_jd_requirements(jd_hash: str, jd_requirements: dict):
    """Cache extracted JD requirements so repeat screenings of the same JD text stay consistent."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO jd_analysis_cache (jd_hash, jd_requirements_json) VALUES (?, ?)",
            (jd_hash, json.dumps(jd_requirements)),
        )
        await db.commit()


async def save_session(session_id: str, jd_text: str, role_title: str, results: list):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (id, jd_text, role_title) VALUES (?, ?, ?)",
            (session_id, jd_text, role_title)
        )
        for result in results:
            await db.execute(
                """INSERT INTO results
                   (session_id, candidate_name, overall_score, recommendation, result_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    session_id,
                    result["candidate_name"],
                    result["overall_score"],
                    result["recommendation"],
                    json.dumps(result),
                )
            )
        await db.commit()


async def get_sessions():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, role_title, created_at FROM sessions ORDER BY created_at DESC LIMIT 50"
        ) as cursor:
            rows = await cursor.fetchall()
            sessions = []
            for row in rows:
                s = dict(row)
                # Count candidates
                async with db.execute(
                    "SELECT COUNT(*) as cnt FROM results WHERE session_id = ?", (s["id"],)
                ) as c:
                    cnt_row = await c.fetchone()
                    s["candidate_count"] = cnt_row["cnt"] if cnt_row else 0
                sessions.append(s)
            return sessions


async def get_session(session_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            session = await cursor.fetchone()
        if not session:
            return None
        async with db.execute(
            "SELECT result_json FROM results WHERE session_id = ? ORDER BY overall_score DESC",
            (session_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            results = [json.loads(row["result_json"]) for row in rows]
        return {"session": dict(session), "results": results}
