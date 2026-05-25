import json
import os

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Request
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

from apps.cart.cart import CartManager
from apps.coupons.models import get_valid_coupon_by_id
from db import db

limiter = Limiter(key_func=get_remote_address)

cart_collection = db['cart']

_vite_manifest = None


def vite_asset(path: str) -> str:
    global _vite_manifest
    if _vite_manifest is None:
        manifest_path = os.path.join('static', 'dist', '.vite', 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                _vite_manifest = json.load(f)
        else:
            _vite_manifest = {}
    entry = _vite_manifest.get(path)
    if entry:
        return '/static/dist/' + entry['file']
    return '/static/' + path


async def get_current_cart(request: Request):
    cart_id = request.cookies.get('cart_id')
    coupon_id = request.cookies.get('coupon_id')

    cart = None
    if cart_id:
        try:
            cart = await cart_collection.find_one({"_id": ObjectId(cart_id)})
        except InvalidId:
            cart = None

    cart = cart or {'items': {}, 'coupon_id': coupon_id}

    if coupon_id:
        try:
            if await get_valid_coupon_by_id(coupon_id):
                cart['coupon_id'] = coupon_id
        except InvalidId:
            pass

    return CartManager(cart)


templates = Jinja2Templates(directory="templates")
templates.env.globals['vite_asset'] = vite_asset
