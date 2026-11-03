from redis import Redis
from redis.exceptions import RedisError

from optometry.core.config import get_redis_url


# creates a redis client with short connection timeouts
def create_redis_client() -> Redis:
    return Redis.from_url(
        get_redis_url(),
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


# checks whether redis is reachable
def redis_is_available(client: Redis) -> bool:
    try:
        return bool(client.ping())
    except RedisError:
        return False
