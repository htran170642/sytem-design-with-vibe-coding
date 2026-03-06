"""
Redis Lua script registry.

Scripts are loaded once at startup with SCRIPT LOAD and then called via
EVALSHA.  This avoids sending the full script body on every hot-path call.
"""

from pathlib import Path

from redis.asyncio import Redis

_LUA_DIR = Path(__file__).parent.parent / "infrastructure" / "redis"


class LuaScripts:
    """Holds pre-loaded SHA digests for all Lua scripts."""

    def __init__(self) -> None:
        self._decrement_sha: str | None = None

    async def load(self, redis: Redis) -> None:  # type: ignore[type-arg]
        """Load all scripts into Redis and cache their SHAs.  Call once on startup."""
        script = (_LUA_DIR / "decrement_stock.lua").read_text()
        self._decrement_sha = await redis.script_load(script)  # type: ignore[assignment]

    async def decrement_stock(self, redis: Redis, stock_key: str) -> int:  # type: ignore[type-arg]
        """
        Atomically decrement stock.

        Returns:
            1   unit reserved
            0   sold out
           -1   key missing (product not initialised)
        """
        if self._decrement_sha is None:
            raise RuntimeError("LuaScripts not loaded — call load() first")
        result: int = await redis.evalsha(self._decrement_sha, 1, stock_key)  # type: ignore[misc]
        return result


# Module-level singleton — shared across the process
lua_scripts = LuaScripts()
