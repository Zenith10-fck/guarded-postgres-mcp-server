"""Database connection pool.

Fase 0 connected as the default superuser just to prove the plumbing
worked. Fase 2 swaps DATABASE_URL to `guarded_reader` -- a role created in
seed/03_roles.sql that only has SELECT on the allow-listed tables --
without changing any code here. That's the point of reading config from
the environment rather than hard-coding credentials: the same server code
runs against a locked-down role in every environment.
"""

import os

import asyncpg

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://guarded_reader:guarded_reader_password@localhost:55432/guarded_demo",
)

# Separate role/pool for the write path (fase 3). The read path never
# touches this pool, so a bug in read code physically cannot write.
WRITE_DATABASE_URL = os.environ.get(
    "WRITE_DATABASE_URL",
    "postgresql://guarded_writer:guarded_writer_password@localhost:55432/guarded_demo",
)

_pool: asyncpg.Pool | None = None
_write_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def get_write_pool() -> asyncpg.Pool:
    global _write_pool
    if _write_pool is None:
        _write_pool = await asyncpg.create_pool(WRITE_DATABASE_URL, min_size=1, max_size=3)
    return _write_pool
