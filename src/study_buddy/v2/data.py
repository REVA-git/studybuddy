import sqlite3
from functools import lru_cache

import sqlite_vec
from langgraph.checkpoint.sqlite import SqliteSaver

from study_buddy.v2.config import Config


@lru_cache(maxsize=1)
def create_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(Config.Path.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


@lru_cache(maxsize=1)
def create_checkpointer() -> SqliteSaver:
    return SqliteSaver(create_db_connection())
