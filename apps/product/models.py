from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, UploadFile, Form, File
from pydantic import BaseModel, Field, field_validator

from apps.category.models import CategorySchema
from db import db
from cache import cache_delete
from utils import create_slug, save_image, check_image_extension

cat_collection = db['category']
product_collection = db['product']


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProductSchema(BaseModel):
    category_id: str
    category_name: str
    name: str
    image: Optional[str] = Field(None, description="Image of the product")
    thumb: Optional[str] = Field(None, description="Thumbnail image")
    description: str
    price: float
    available: bool
    stock: int = Field(default=0, ge=0, description="Available stock quantity")
    external_links: Optional[dict] = Field(None, description="External platform links e.g. {'Amazon': 'https://...'}")
    created: datetime = Field(default_factory=_now)
    updated: datetime = Field(default_factory=_now)

    @field_validator('created', 'updated', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.strptime(v, '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "category_id": "64bb6098a13688d244e7c759",
                "category_name": "Electronics",
                "name": "Product Name",
                "description": "Product description",
                "price": 10.99,
                "available": True,
            },
            "description": "A product representation",
            "notes": "This schema represents a product object with various fields."
        }


class ProductCreateSchema(BaseModel):
    category_id: str
    name: str
    image: UploadFile
    description: str
    price: float
    available: Optional[bool] = Field(False)
    stock: int = Field(default=0, ge=0, description="Available stock quantity")
    external_etsy: Optional[str] = Field(None, description="Etsy listing URL")
    external_gumroad: Optional[str] = Field(None, description="Gumroad product URL")

    @classmethod
    def as_form(
            cls,
            category_id: str = Form(...),
            name: str = Form(...),
            description: str = Form(...),
            price: float = Form(...),
            available: Optional[bool] = Form(False),
            stock: int = Form(0),
            external_etsy: str = Form(default=""),
            external_gumroad: str = Form(default=""),
            image: UploadFile = File(...)
    ):
        return cls(
            category_id=category_id,
            name=name,
            image=image,
            description=description,
            price=price,
            available=available,
            stock=stock,
            external_etsy=external_etsy,
            external_gumroad=external_gumroad,
        )


def product_helper(product) -> dict:
    return {
        "_id": str(product["_id"]),
        "category_id": product["category_id"],
        "category_name": product["category_name"],
        "name": product["name"],
        "slug": product["slug"],
        "image": product["image"],
        "thumb": product.get("thumb"),
        "description": product["description"],
        "price": product["price"],
        "available": product["available"],
        "stock": product.get("stock", 0),
        "external_links": product.get("external_links"),
        "created": product["created"],
        "updated": product["updated"],
    }


async def create_product(product_data: dict):
    category = await cat_collection.find_one({"_id": ObjectId(product_data["category_id"])})
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    product_data["category_name"] = category["name"]

    slug = create_slug(product_data["name"])

    if product_data['image'].size != 0:
        check_image_extension(product_data['image'])
        image_path, thumb_path = await save_image(slug, product_data['image'].file.read())
    else:
        image_path = None
        thumb_path = None

    product_data["slug"] = slug
    product_data['available'] = product_data.get('available', True)
    product_data['stock'] = product_data.get('stock', 0)
    product_data["image"] = image_path
    product_data["thumb"] = thumb_path
    product_data["created"] = _now()
    product_data["updated"] = _now()
    external = {}
    if product_data.get('external_etsy'):
        external['Etsy'] = product_data.pop('external_etsy').strip()
    if product_data.get('external_gumroad'):
        external['Gumroad'] = product_data.pop('external_gumroad').strip()
    product_data['external_links'] = external if external else None

    new_product = await product_collection.insert_one(product_data)
    created_product = await product_collection.find_one({"_id": new_product.inserted_id})
    await cache_delete("products:*")
    return product_helper(created_product)


async def edit_product(_id: str, data: dict):
    category = await cat_collection.find_one({"_id": ObjectId(data["category_id"])})
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    data["category_name"] = category["name"]

    slug = create_slug(data['name'])

    if data['image'].filename:
        check_image_extension(data['image'])
        image_path, thumb_path = await save_image(slug, data['image'].file.read())
        data["image"] = image_path
        data["thumb"] = thumb_path
    else:
        del data['image']

    data['slug'] = slug
    data["updated"] = _now()
    external = {}
    if data.get('external_etsy'):
        external['Etsy'] = data['external_etsy'].strip()
    if data.get('external_gumroad'):
        external['Gumroad'] = data['external_gumroad'].strip()
    data.pop('external_etsy', None)
    data.pop('external_gumroad', None)
    data['external_links'] = external if external else None
    await product_collection.update_one({"_id": ObjectId(_id)}, {"$set": data})
    await cache_delete("products:*")
    product = await get_product_by_id(_id)
    return product


async def get_all_products():
    products = []
    async for product in product_collection.find():
        products.append(product_helper(product))
    return products


SORT_MAP = {
    "price_asc": ("price", 1),
    "price_desc": ("price", -1),
    "name_asc": ("name", 1),
    "name_desc": ("name", -1),
    "newest": ("created", -1),
    "oldest": ("created", 1),
}


def _apply_sort(cursor, sort: str = None):
    if sort and sort in SORT_MAP:
        field, direction = SORT_MAP[sort]
        cursor = cursor.sort(field, direction)
    return cursor


async def get_available_products(sort: str = None):
    products = []
    cursor = product_collection.find({"available": True})
    cursor = _apply_sort(cursor, sort)
    async for product in cursor:
        products.append(product_helper(product))
    return products


async def search_products(query: str, limit: int = 20):
    products = []
    async for product in product_collection.find(
        {"$text": {"$search": query}, "available": True},
        {"score": {"$meta": "textScore"}},
    ).sort([("score", {"$meta": "textScore"})]).limit(limit):
        products.append(product_helper(product))
    return products


async def suggest_products(query: str, limit: int = 6):
    suggestions = []
    async for product in product_collection.find(
        {"$text": {"$search": query}, "available": True},
        {"score": {"$meta": "textScore"}},
    ).sort([("score", {"$meta": "textScore"})]).limit(limit):
        suggestions.append({
            "_id": str(product["_id"]),
            "name": product["name"],
            "slug": product["slug"],
            "price": product["price"],
            "image": product.get("image"),
            "thumb": product.get("thumb"),
        })
    return suggestions


async def get_products_by_category(category: CategorySchema, sort: str = None):
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    products = []
    cursor = product_collection.find({"category_id": category["_id"], "available": True})
    cursor = _apply_sort(cursor, sort)
    async for product in cursor:
        products.append(product_helper(product))
    return products


async def get_category_product_counts():
    pipeline = [
        {"$match": {"available": True}},
        {"$group": {"_id": "$category_id", "count": {"$sum": 1}}},
    ]
    counts = {}
    async for doc in product_collection.aggregate(pipeline):
        counts[doc["_id"]] = doc["count"]
    return counts


async def get_product_by_slug(_id: ObjectId, slug: str):
    product = await product_collection.find_one({"_id": ObjectId(_id), "slug": slug})
    if product:
        return product_helper(product)


async def get_product_by_id(_id: str):
    try:
        oid = ObjectId(_id)
    except InvalidId:
        return None
    product = await product_collection.find_one({"_id": oid})
    if product:
        return product_helper(product)
