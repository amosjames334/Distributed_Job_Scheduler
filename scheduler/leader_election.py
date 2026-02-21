import asyncio
import os
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
LEADER_KEY = "scheduler:leader"
LEASE_TTL_MS = 10000
HEARTBEAT_INTERVAL = 5
SCHEDULER_CONSUMER = os.getenv("HOSTNAME", "scheduler-1")

REFRESH_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('pexpire', KEYS[1], ARGV[2])
else
    return 0
end
"""


class RedisLeaderElection:
    def __init__(self, redis_url: str = None, instance_id: str = None):
        self.redis_url = redis_url or REDIS_URL
        self.instance_id = instance_id or SCHEDULER_CONSUMER
        self._r = None
        self._is_leader = False

    async def _get_redis(self) -> redis.Redis:
        if self._r is None:
            self._r = redis.from_url(self.redis_url)
        return self._r

    async def acquire(self) -> bool:
        r = await self._get_redis()
        result = await r.set(
            LEADER_KEY,
            self.instance_id,
            nx=True,
            px=LEASE_TTL_MS,
        )
        if result:
            self._is_leader = True
            return True

        current = await r.get(LEADER_KEY)
        if current and current.decode("utf-8") == self.instance_id:
            self._is_leader = True
            return True

        self._is_leader = False
        return False

    async def refresh(self) -> bool:
        r = await self._get_redis()
        result = await r.eval(
            REFRESH_LUA, 1, LEADER_KEY, self.instance_id, str(LEASE_TTL_MS)
        )
        if result == 0:
            self._is_leader = False
            return False
        return True

    @property
    def is_leader(self) -> bool:
        return self._is_leader
