from fastapi import APIRouter, Request, Depends, Form
from pydantic import EmailStr

from apps.cart.cart import CartManager
from apps.cart.routers import get_current_cart
from apps.order.models import create_order
from db import db
from dependencies import templates
from fastapi.responses import RedirectResponse
from celery_tasks import send_order_email
from middleware import get_user_from_token
from utils import Message

user_collection = db['user']

router = APIRouter()


@router.get('/')
async def order_create(request: Request, current_cart: CartManager = Depends(get_current_cart)):
    await current_cart.set_coupon()
    items = [item async for item in current_cart]
    context = {"request": request, "cart": current_cart, "items": items}

    if message := request.cookies.get('error_msg'):
        context.update({'messages': [Message(text=message)]})

    context["checkout_step"] = 2
    response = templates.TemplateResponse("shop/order/create.html", context)
    return response


@router.post('/')
async def order_created(request: Request,
                        first_name: str = Form(...),
                        last_name: str = Form(...),
                        email: EmailStr = Form(...),
                        address: str = Form(...),
                        postal_code: str = Form(...),
                        city: str = Form(...),
                        current_cart: CartManager = Depends(get_current_cart)):
    await current_cart.set_coupon()
    items = [item async for item in current_cart]
    order_data = {'first_name': first_name,
                  'last_name': last_name,
                  'email': email,
                  'address': address,
                  'postal_code': postal_code,
                  'city': city, }

    token = request.cookies.get("token")
    username = get_user_from_token(token)
    if username:
        user_doc = await user_collection.find_one({"username": username})
        if user_doc:
            order_data['user_id'] = str(user_doc["_id"])

    if current_cart.coupon:
        order_data['coupon'] = current_cart.coupon["_id"]
        order_data['discount'] = current_cart.coupon["discount"]

    order_data = await create_order(order_data=order_data, items=items)
    await current_cart.clear()
    send_order_email.delay(order_data['_id'], order_data['email'])
    response = RedirectResponse(url='/payment/process', status_code=303)
    response.set_cookie('order_id', order_data['_id'])
    response.delete_cookie('coupon_id', path='/')
    response.delete_cookie('coupon', path='/')
    return response
