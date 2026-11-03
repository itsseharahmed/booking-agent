from unittest.mock import Mock

from redis.exceptions import ConnectionError

from optometry.cache.redis_client import redis_is_available


# confirms a successful redis ping
def test_redis_is_available() -> None:
    client = Mock()
    client.ping.return_value = True

    assert redis_is_available(client) is True


# confirms redis failures are handled
def test_redis_is_unavailable() -> None:
    client = Mock()
    client.ping.side_effect = ConnectionError("Redis unavailable")

    assert redis_is_available(client) is False
