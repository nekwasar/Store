import os
from math import ceil
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, Query, Request
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler: GetCoreSchemaHandler):
        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def create_slug(name):
    return name.lower().replace(" ", "-")


async def save_image(product_slug: str, file: bytes):
    import aiofiles
    from PIL import Image
    from io import BytesIO

    image_path_static = f"img/{product_slug}.png"
    thumb_path_static = f"img/{product_slug}_thumb.png"

    img = Image.open(BytesIO(file))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Save full-size
    img.save(f'static/{image_path_static}', "PNG", optimize=True)

    # Save thumbnail (300x300 max)
    img.thumbnail((300, 300))
    img.save(f'static/{thumb_path_static}', "PNG", optimize=True)

    return image_path_static, thumb_path_static


def get_value_from_cookies(request: Request, cookie_name: str) -> Any:
    return request.cookies.get(cookie_name)


def get_stripe_url(stripe_id):
    stripe_key = os.environ.get('STRIPE_SECRET_KEY', '')
    if '_test_' in stripe_key:
        path = '/test/'
    else:
        path = '/'
    return f'https://dashboard.stripe.com{path}payments/{stripe_id}'


class Message:

    def __init__(self, text, tags='danger'):
        self.text = text
        self.tags = tags

    def __str__(self):
        return self.text


class Paginator:

    def __init__(self, getter):
        self.page = 0
        self.per_page = 0
        self.amount = 0
        self.start = 0
        self.end = 0
        self.last = 0
        self.next = 0
        self.previous = 0
        self.page_range = None
        self.getter = getter

    async def eval(self):
        objects = await self.getter()

        self.amount = len(objects)
        self.start = (self.page - 1) * self.per_page
        self.end = self.start + self.per_page
        self.last = ceil(self.amount / self.per_page)
        self.next = self.page + 1 if self.page != self.last else None
        self.previous = self.page - 1 if self.page > 1 else None
        self.page_range = range(1, self.last + 1)

    async def __call__(self, page: int = Query(1, gt=0), per_page: int = Query(10, gt=0)):
        self.page = int(page)
        self.per_page = int(per_page)
        await self.eval()
        return self


def check_image_extension(image):
    allowed_extensions = {"png", "jpg", "jpeg", "webp"}
    file_extension = image.filename.split(".")[-1].lower() if "." in image.filename else ""
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Image must be one of: {', '.join(sorted(allowed_extensions))}")
