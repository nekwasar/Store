import ast
import os

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

client = AsyncIOMotorClient(
    os.environ.get('MONGODB_URL', 'mongodb://mongo:27017'),
    maxPoolSize=int(os.environ.get('MONGODB_MAX_POOL', '20')),
    minPoolSize=int(os.environ.get('MONGODB_MIN_POOL', '2')),
    serverSelectionTimeoutMS=int(os.environ.get('MONGODB_TIMEOUT_MS', '5000')),
    connectTimeoutMS=int(os.environ.get('MONGODB_TIMEOUT_MS', '5000')),
)
db = client[os.environ.get('MONGODB_DB', 'fastapi_shop')]


# SOME COMMON OPERATIONS

async def delete_product_image(_id: str):
    try:
        oid = ObjectId(_id)
    except InvalidId:
        return
    product = await db["product"].find_one({"_id": oid})
    image_path = product.get("image", "")
    if not image_path:
        return
    path_in_static_dir = f'static/{image_path}'
    import aiofiles.os
    try:
        await aiofiles.os.remove(path_in_static_dir)
    except FileNotFoundError:
        pass


async def delete_object(_id: str, model: str):
    try:
        oid = ObjectId(_id)
    except ObjectId.InvalidId:
        return None
    if model == 'product':
        await delete_product_image(_id)
    result = await db[model].delete_one({"_id": oid})
    return result


async def delete_objects(delete: str, model: str):
    delete_list = ast.literal_eval(delete)
    if model == "category":
        await db["product"].delete_many({"category_id": {"$in": delete_list}})
    if model == "product":
        for _id in delete_list:
            await delete_product_image(_id)
    await db[model].delete_many({"_id": {"$in": [ObjectId(_id) for _id in delete_list]}})
