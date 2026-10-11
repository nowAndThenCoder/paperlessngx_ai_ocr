import redis

from .config import settings


class RedisClient:
    def __init__(self):
        # Removed decode_responses=True to allow binary data (blobs) to be stored and retrieved
        self.pool = redis.ConnectionPool(
            host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, decode_responses=False
        )

    def get_connection(self) -> redis.Redis:
        return redis.Redis(connection_pool=self.pool)


redis_client = RedisClient()
