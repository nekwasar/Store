import os

from redis import asyncio as aioredis

from apps.product.models import get_product_by_id

_REDIS_TIMEOUT = int(os.environ.get('REDIS_TIMEOUT', '5'))

_redis = aioredis.Redis(
    host=os.environ.get('REDIS_HOST', 'redis'),
    port=int(os.environ.get('REDIS_PORT', '6379')),
    db=int(os.environ.get('REDIS_DB', '0')),
    socket_connect_timeout=_REDIS_TIMEOUT,
    socket_timeout=_REDIS_TIMEOUT,
    retry_on_timeout=True,
)


class Recommender:
    def __init__(self, product_ids):
        self.product_ids = product_ids

    def get_product_key(self, id):
        return f'product:{id}:purchased_with'

    async def products_bought(self):
        for product_id in self.product_ids:
            for with_id in self.product_ids:
                if product_id != with_id:
                    await _redis.zincrby(self.get_product_key(product_id), 1, with_id)

    async def suggest_products_for(self, max_results=6):
        if len(self.product_ids) == 1:
            suggestions = await _redis.zrange(
                self.get_product_key(self.product_ids[0]), 0, -1, desc=True,
            )
            suggestions = suggestions[:max_results]
        else:
            flat_ids = ''.join([_id for _id in self.product_ids])
            tmp_key = f'tmp_{flat_ids}'
            product_keys = [self.get_product_key(id) for id in self.product_ids]
            await _redis.zunionstore(tmp_key, product_keys)
            await _redis.zrem(tmp_key, *self.product_ids)
            suggestions = await _redis.zrange(tmp_key, 0, -1, desc=True)
            suggestions = suggestions[:max_results]
            await _redis.delete(tmp_key)

        suggested_products = [await get_product_by_id(_id.decode()) for _id in suggestions]
        return suggested_products
