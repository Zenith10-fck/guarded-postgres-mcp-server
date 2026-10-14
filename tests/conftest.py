"""Shared pytest fixtures. Requires the demo Postgres to be running:
    docker compose up -d
"""

import pytest_asyncio

from guarded_mcp.db import get_pool, get_write_pool


@pytest_asyncio.fixture(scope="session")
async def read_pool():
    return await get_pool()


@pytest_asyncio.fixture(scope="session")
async def write_pool():
    return await get_write_pool()
