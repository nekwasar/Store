from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse

from apps.cart.cart import CartManager
from db import db
from dependencies import templates, get_current_cart
from recommender import Recommender

router = APIRouter()

cart_collection = db['cart']


@router.post("/add")
async def add_to_cart(request: Request,
                      product_id: str = Form(...),
                      quantity: int = Form(gt=0),
                      override_quantity: bool = Form(False),
                      current_cart: CartManager = Depends(get_current_cart)):
    await current_cart.add(product_id, override_quantity, quantity)
    referer = request.headers.get('referer', '/product')
    origin = request.headers.get('origin', '')
    if origin and referer.startswith(origin):
        redirect_url = referer[len(origin):] or '/product'
    else:
        redirect_url = '/product'
    redir_resp = RedirectResponse(url=redirect_url, status_code=303)
    redir_resp.set_cookie('cart_updated', '1')
    await current_cart.save(redir_resp)
    return redir_resp


@router.post("/remove")
async def remove_from_cart(product_id: str = Form(...), current_cart: CartManager = Depends(get_current_cart)):
    redir_resp = RedirectResponse(url='/cart', status_code=303)
    await current_cart.remove(product_id, redir_resp)
    return redir_resp


@router.get('/offcanvas')
async def cart_offcanvas(current_cart: CartManager = Depends(get_current_cart)):
    await current_cart.set_coupon()
    if len(current_cart):
        items = [item async for item in current_cart]
        html = templates.TemplateResponse("shop/cart/offcanvas_content.html", {
            "cart": current_cart, "items": items,
        })
    else:
        html = templates.TemplateResponse("shop/cart/offcanvas_content.html", {
            "cart": current_cart, "items": [],
        })
    return HTMLResponse(html.body)


@router.post("/offcanvas-update")
async def cart_offcanvas_update(
    product_id: str = Form(...),
    change: int = Form(...),
    current_cart: CartManager = Depends(get_current_cart),
):
    qty = current_cart.cart['items'].get(product_id, 0)
    new_qty = max(0, qty + change)
    if new_qty <= 0:
        resp = RedirectResponse(url='/cart', status_code=303)
        await current_cart.remove(product_id, resp)
    else:
        await current_cart.add(product_id, True, new_qty)
        resp = JSONResponse({"status": "ok"})
        await current_cart.save(resp)
    return resp


@router.post("/offcanvas-remove")
async def cart_offcanvas_remove(
    product_id: str = Form(...),
    current_cart: CartManager = Depends(get_current_cart),
):
    resp = JSONResponse({"status": "ok"})
    await current_cart.remove(product_id, resp)
    return resp


@router.get('/')
async def cart_detail(request: Request, current_cart: CartManager = Depends(get_current_cart)):
    await current_cart.set_coupon()
    if len(current_cart):

        items = [item async for item in current_cart]
        r = Recommender([str(item['product']['_id']) for item in items])
        recommendations = await r.suggest_products_for()
        response = templates.TemplateResponse("shop/cart/detail.html", {"request": request, "cart": current_cart,
                                                                        "items": items,
                                                                        'recommendations': recommendations,
                                                                        "checkout_step": 1})
        return response
    else:
        return RedirectResponse(url='/product', status_code=303)
