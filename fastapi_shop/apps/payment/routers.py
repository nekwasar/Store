import os

import stripe
from bson import ObjectId
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from stripe.error import SignatureVerificationError

from apps.order.models import get_order_by_id, OrderSchema
from apps.product.models import get_product_by_id
from celery_tasks import send_bill_email
from db import db
from dependencies import templates
from recommender import Recommender
from utils import Message, get_stripe_url

order_collection = db['order']

router = APIRouter()


def _get_stripe_key():
    return os.environ.get('STRIPE_SECRET_KEY', '')


def _get_stripe_version():
    return os.environ.get('STRIPE_API_VERSION', '2023-10-16')


stripe.api_key = _get_stripe_key()
stripe.api_version = _get_stripe_version()
STRIPE_CURRENCY = os.environ.get('STRIPE_CURRENCY', 'cad')


@router.get('/process')
async def payment_process_get(request: Request):
    order_id = request.cookies.get('order_id')
    if not order_id:
        return RedirectResponse(url='/cart', status_code=303)
    order_doc = await get_order_by_id(order_id)
    if not order_doc:
        return RedirectResponse(url='/cart', status_code=303)
    order = OrderSchema(**order_doc)
    products = {item.product_id: await get_product_by_id(item.product_id) for item in order.items}
    return templates.TemplateResponse("shop/payment/process.html", {"request": request, "order": order,
                                                                     "products": products,
                                                                     "checkout_step": 3})


@router.post('/process')
async def payment_process_post(request: Request):
    order_id = request.cookies.get('order_id')
    if not order_id:
        return RedirectResponse(url='/cart', status_code=303)
    order_doc = await get_order_by_id(order_id)
    if not order_doc:
        return RedirectResponse(url='/cart', status_code=303)
    order = OrderSchema(**order_doc)
    success_url = str(request.url).replace('process', 'completed')
    cancel_url = str(request.url).replace('process', 'canceled')

    session_data = {
        'mode': 'payment',
        'client_reference_id': order_id,
        'success_url': success_url,
        'cancel_url': cancel_url,
        'line_items': []
    }

    for item in order.items:
        session_data['line_items'].append({
            'price_data': {
                'unit_amount': int(round(item.price * 100)),
                'currency': STRIPE_CURRENCY,
                'product_data': {
                    'name': item.product_name,
                },
            },
            'quantity': item.quantity,
        })

    if order.coupon:
        try:
            existing = stripe.Coupon.list(limit=1)
            stripe_coupon = None
            for c in existing.auto_paging_iter():
                if c.name == order.coupon["code"]:
                    stripe_coupon = c
                    break
        except Exception:
            stripe_coupon = None

        if not stripe_coupon:
            stripe_coupon = stripe.Coupon.create(
                name=order.coupon["code"],
                percent_off=order.discount,
                duration='once',
            )
        session_data['discounts'] = [{'coupon': stripe_coupon.id}]

    session = stripe.checkout.Session.create(**session_data)

    return RedirectResponse(url=session.url, status_code=303)


@router.get('/completed')
async def payment_completed(request: Request):
    order_id = request.cookies.get('order_id')
    if not order_id:
        return RedirectResponse(url='/product', status_code=303)
    order_doc = await get_order_by_id(order_id)
    if not order_doc:
        return RedirectResponse(url='/product', status_code=303)
    order = OrderSchema(**order_doc)
    return templates.TemplateResponse("shop/payment/completed.html", {"request": request, "order": order,
                                                                       "checkout_step": 4})


@router.get('/canceled')
async def payment_canceled(request: Request):
    return templates.TemplateResponse("shop/payment/canceled.html", {"request": request})


@router.post('/webhook/')
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature', '')
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            os.environ.get('STRIPE_WEBHOOK_SECRET'))
    except ValueError:
        return Response(status_code=400)
    except SignatureVerificationError:
        return Response(status_code=400)

    if event.type == 'checkout.session.completed':
        session = event.data.object
        if session.mode == 'payment' and session.payment_status == 'paid':
            order_data = await get_order_by_id(session.client_reference_id)
            if not order_data:
                return Response(status_code=404)

            if order_data.get('status') == 'paid':
                return Response(status_code=200)

            stripe_id = session.payment_intent
            stripe_url = get_stripe_url(stripe_id)

            await order_collection.update_one(
                {'_id': order_data['_id']},
                {'$set': {
                    'paid': True,
                    'status': 'paid',
                    'stripe_id': stripe_id,
                    'stripe_url': stripe_url,
                }}
            )
            order_data['paid'] = True
            order_data['status'] = 'paid'
            order_data['stripe_id'] = stripe_id
            order_data['stripe_url'] = stripe_url
            order = convert_object_id_to_str(await get_order_by_id(str(order_data['_id'])))
            ids = [item["product_id"] for item in order['items']]
            r = Recommender(ids)
            await r.products_bought()
            send_bill_email.delay(order)

    return Response(status_code=200)


def convert_object_id_to_str(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = convert_object_id_to_str(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = convert_object_id_to_str(item)
    elif isinstance(obj, ObjectId):
        obj = str(obj)
    return obj
