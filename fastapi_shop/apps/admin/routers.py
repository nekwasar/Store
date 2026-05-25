
import csv
import io
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from pymongo.errors import DuplicateKeyError

import apps.category.models as cat_m
import apps.coupons.models as coup_m
import apps.order.models as ord_m
import apps.product.models as prod_m
from apps.audit_log import audit_collection
from db import db, delete_objects, delete_object
from dependencies import templates
from logger import get_logger
from cache import cache_delete
from utils import Paginator, Message
from constants import COLLECTION_USER, COLLECTION_PRODUCT, COLLECTION_ORDER, COLLECTION_AUDIT_LOG

router = APIRouter()
_log = get_logger("admin")


@router.get("/")
async def get_admin(request: Request):
    return templates.TemplateResponse("admin/home.html", {"request": request, 'admin': True})


# Dashboard API endpoints

def _compute_item_total(items: list) -> float:
    total = 0.0
    for item in items:
        total += item.get("price", 0) * item.get("quantity", 0)
    return total


def _compute_order_total(order: dict) -> float:
    items = order.get("items", [])
    total = _compute_item_total(items)
    discount = order.get("discount", 0)
    if discount:
        total -= total * (discount / 100)
    return total


@router.get("/api/stats")
async def admin_api_stats():
    total_orders = await db[COLLECTION_ORDER].count_documents({})
    total_products = await db[COLLECTION_PRODUCT].count_documents({})
    total_users = await db[COLLECTION_USER].count_documents({})

    total_revenue = 0.0
    cursor = db[COLLECTION_ORDER].find({"paid": True})
    async for order in cursor:
        total_revenue += _compute_order_total(order)

    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "total_products": total_products,
        "total_users": total_users,
    }


@router.get("/api/revenue")
async def admin_api_revenue(period: str = Query("7d")):
    days = int(period.replace("d", ""))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    daily = {}
    cursor = db[COLLECTION_ORDER].find({"paid": True, "created": {"$gte": since}})
    async for order in cursor:
        created = order.get("created")
        if created:
            day_key = created.strftime("%Y-%m-%d") if hasattr(created, "strftime") else str(created)[:10]
            daily[day_key] = daily.get(day_key, 0) + _compute_order_total(order)

    return [{"date": d, "revenue": round(r, 2)} for d, r in sorted(daily.items())]


@router.get("/api/recent-orders")
async def admin_api_recent_orders(limit: int = Query(5)):
    cursor = db[COLLECTION_ORDER].find().sort("created", -1).limit(limit)
    orders = []
    async for o in cursor:
        user_id = o.get("user_id")
        username = None
        if user_id:
            user_doc = await db[COLLECTION_USER].find_one({"_id": ObjectId(user_id)})
            if user_doc:
                username = user_doc.get("username")
        orders.append({
            "_id": str(o["_id"]),
            "first_name": o.get("first_name", ""),
            "last_name": o.get("last_name", ""),
            "email": o.get("email", ""),
            "total": round(_compute_order_total(o), 2),
            "status": o.get("status", "pending"),
            "created": o.get("created").isoformat() if o.get("created") else "",
            "username": username,
        })
    return orders


@router.get("/api/popular-products")
async def admin_api_popular_products(limit: int = Query(5)):
    product_sales = {}
    cursor = db[COLLECTION_ORDER].find({})
    async for order in cursor:
        for item in order.get("items", []):
            pid = item.get("product_id")
            qty = item.get("quantity", 0)
            if pid:
                product_sales[pid] = product_sales.get(pid, 0) + qty

    sorted_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:limit]
    products = []
    for pid, total_sold in sorted_products:
        prod = await db[COLLECTION_PRODUCT].find_one({"_id": pid if isinstance(pid, str) else pid})
        products.append({
            "name": prod["name"] if prod else "Unknown",
            "total_sold": total_sold,
        })
    return products


# Audit log viewer

@router.get("/audit-log")
async def admin_audit_log(request: Request, page: int = Query(1, gt=0), per_page: int = Query(50, gt=0)):
    total = await audit_collection.count_documents({})
    cursor = audit_collection.find().sort("created", -1).skip((page - 1) * per_page).limit(per_page)
    logs = []
    async for l in cursor:
        logs.append({
            "_id": str(l["_id"]),
            "admin_user": l.get("admin_user", ""),
            "action": l.get("action", ""),
            "entity_type": l.get("entity_type", ""),
            "entity_id": l.get("entity_id", ""),
            "summary": l.get("summary", ""),
            "created": l.get("created").isoformat() if l.get("created") else "",
        })
    return templates.TemplateResponse("admin/audit_log.html", {
        "request": request,
        "logs": logs,
        "admin": True,
        "page": page,
        "per_page": per_page,
        "total": total,
        "last_page": max(1, (total + per_page - 1) // per_page),
    })


# CATEGORY ADMIN CRUD ROUTING

# TODO поменять использование category.id на category._id  в моделях и шаблонах
@router.get("/category/")
async def admin_category_list_endpoint(request: Request,
                                       pagination: Paginator = Depends(Paginator(cat_m.get_all_categories))):
    categories = await cat_m.get_all_categories()
    context = {"request": request, "categories": categories[pagination.start:pagination.end],
               'admin': True,
               "paginator": pagination}

    return await list_endpoint_dry(request, context, model='category')


@router.get("/category/create")
async def admin_category_create_endpoint(request: Request):
    context = {"request": request, 'admin': True}

    if request.cookies.get('category_created') == 'True':
        context.update({'messages': [Message(text=f'New category has been created', tags='info')]})
        response = templates.TemplateResponse("admin/category/create.html", context=context)
        response.set_cookie('category_created', 'False')
    else:
        response = templates.TemplateResponse("admin/category/create.html", context=context)
    return response


@router.post("/category/create")
async def admin_category_create_endpoint(request: Request,
                                         next_page: str = Form(...),
                                         form: cat_m.CategoryCreateSchema = Depends(
                                             cat_m.CategoryCreateSchema.as_form), ):
    try:
        category = await cat_m.create_category(form.model_dump())
        _log.info("category_created name=%s id=%s", category["name"], category["_id"])
        redirect_url = next_page if next_page == 'create' else f'edit/{category["_id"]}'

        response = RedirectResponse(url=redirect_url,
                                    status_code=303, )
        response.set_cookie('category_created', 'True')
    except DuplicateKeyError as e:
        messages = [Message(f"A category called {form.model_dump()['name']} already exists! "
                            f"Please type a different name for the category.")]
        response = templates.TemplateResponse("admin/category/create.html",
                                              {"request": request, 'admin': True, "messages": messages, "form": form})
    return response


@router.get("/category/edit/{_id}")
async def admin_category_edit_endpoint(request: Request, _id: str):
    category = await cat_m.get_category_by_id(_id)
    context = {"request": request, "category": category, 'admin': True}
    if request.cookies.get('category_created') == 'True':
        context.update({'messages': [Message(text=f'New category {category["name"]} has been created', tags='info')]})
        response = templates.TemplateResponse("admin/category/edit.html", context=context)
        response.set_cookie('category_created', 'False')
    else:
        response = templates.TemplateResponse("admin/category/edit.html", context=context)
    return response


@router.post("/category/edit/{_id}")
async def admin_category_edit_endpoint(request: Request,
                                       _id: str,
                                       form: cat_m.CategoryCreateSchema = Depends(
                                           cat_m.CategoryCreateSchema.as_form), ):
    edited_category = await cat_m.edit_category(_id, form.model_dump())
    message = [Message(text=f'Category {edited_category["name"]} has been edited', tags='info')]

    return templates.TemplateResponse("admin/category/edit.html",
                                      {"request": request,
                                       "category": edited_category,
                                       "messages": message,
                                       'admin': True})


@router.get("/category/delete/{_id}")
async def admin_category_delete_endpoint(request: Request, _id: str):
    category = await cat_m.get_category_by_id(_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return templates.TemplateResponse("admin/category/delete_confirm.html",
                                      {"request": request, "category": category, 'admin': True})


@router.get("/category/delete_confirm/{_id}")
async def admin_category_delete_confirm_endpoint(request: Request, _id: str):
    _log.info("category_deleted id=%s", _id)
    await delete_object(_id, 'category')
    response = RedirectResponse(url='/admin/category/',
                                status_code=303, )
    response.set_cookie('category_deleted', 'True')
    return response


# PRODUCT ADMIN CRUD ROUTING


@router.get("/product/")
async def admin_product_list_endpoint(request: Request,
                                      pagination: Paginator = Depends(Paginator(prod_m.get_all_products))):
    products = await prod_m.get_all_products()
    context = {"request": request, "products": products[pagination.start:pagination.end],
               'admin': True,
               'paginator': pagination}

    return await list_endpoint_dry(request, context, model='product')


@router.get("/product/create")
async def admin_product_create_endpoint(request: Request, categories_list: list = Depends(cat_m.get_all_categories)):
    context = {"request": request, "categories_list": categories_list, 'admin': True}
    if request.cookies.get('product_created') == 'True':
        context.update({'messages': [Message(text=f'New product has been created', tags='info')]})
        response = templates.TemplateResponse("admin/product/create.html", context=context)
        response.set_cookie('product_created', 'False')
    else:
        response = templates.TemplateResponse("admin/product/create.html", context=context)
    return response


@router.post("/product/create")
async def admin_product_create_endpoint(request: Request,
                                        next_page: str = Form(...),
                                        form: prod_m.ProductCreateSchema = Depends(
                                            prod_m.ProductCreateSchema.as_form), ):
    try:
        product = await prod_m.create_product(form.model_dump())
        _log.info("product_created name=%s id=%s", product["name"], product["_id"])

        redirect_url = next_page if next_page == 'create' else f'edit/{product["_id"]}'
        response = RedirectResponse(url=redirect_url,
                                    status_code=303, )
        response.set_cookie('product_created', 'True')
        return response
    except HTTPException as e:
        messages = [Message(e.detail)]
        categories_list = await cat_m.get_all_categories()
        return templates.TemplateResponse("admin/product/create.html",
                                          {"request": request, "categories_list": categories_list, 'admin': True,
                                           "messages": messages})
    except InvalidId:
        messages = [Message('You must select a valid category')]
        categories_list = await cat_m.get_all_categories()
        return templates.TemplateResponse("admin/product/create.html",
                                          {"request": request, "categories_list": categories_list, 'admin': True,
                                           "messages": messages})
    except Exception:
        messages = [Message("An unexpected error occurred while creating the product")]
        categories_list = await cat_m.get_all_categories()
        return templates.TemplateResponse("admin/product/create.html",
                                          {"request": request, "categories_list": categories_list, 'admin': True,
                                           "messages": messages})


@router.get("/product/edit/{_id}")
async def admin_product_edit_endpoint(request: Request, _id: str,
                                      categories_list: list = Depends(cat_m.get_all_categories)):
    product = await prod_m.get_product_by_id(_id)

    context = {"request": request, "product": product, "categories_list": categories_list, 'admin': True}

    if request.cookies.get('product_created') == 'True':
        context.update({'messages': [Message(text=f'New product {product["name"]} has been created', tags='info')]})
        response = templates.TemplateResponse("admin/product/edit.html", context=context)
        response.set_cookie('product_created', 'False')
    else:
        response = templates.TemplateResponse("admin/product/edit.html", context=context)
    return response


@router.post("/product/edit/{_id}")
async def admin_product_edit_endpoint(request: Request,
                                      _id: str,
                                      form: prod_m.ProductCreateSchema = Depends(prod_m.ProductCreateSchema.as_form),
                                      categories_list: list = Depends(cat_m.get_all_categories)):
    edited_product = await prod_m.edit_product(_id, form.model_dump())
    await cache_delete("products:*")
    message = [Message(text=f'Product {edited_product["name"]} has been edited', tags='info')]

    return templates.TemplateResponse("admin/product/edit.html",
                                      {"request": request, "product": edited_product,
                                       "categories_list": categories_list,
                                       'messages': message,
                                       'admin': True})


@router.get("/product/delete/{_id}")
async def admin_product_delete_endpoint(request: Request, _id: str):
    product = await prod_m.get_product_by_id(_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return templates.TemplateResponse("admin/product/delete_confirm.html",
                                      {"request": request, "product": product, 'admin': True})


@router.get("/product/delete_confirm/{_id}")
async def admin_product_delete_confirm_endpoint(request: Request, _id: str):
    await delete_object(_id, 'product')
    await cache_delete("products:*")
    response = RedirectResponse(url='/admin/product/',
                                status_code=303, )
    response.set_cookie('product_deleted', 'True')
    return response


# ORDER ADMIN CRUD ROUTING

@router.get("/order/")
async def admin_order_list_endpoint(request: Request,
                                    pagination: Paginator = Depends(Paginator(ord_m.get_all_orders))):
    orders = await ord_m.get_all_orders()
    context = {"request": request, "orders": orders[pagination.start:pagination.end],
               'admin': True,
               'paginator': pagination}

    return await list_endpoint_dry(request, context, model='order')


@router.get("/order/create")
async def admin_order_create_endpoint(request: Request, coupons_list: list = Depends(coup_m.get_valid_coupons)):
    context = {"request": request, "coupons_list": coupons_list, 'admin': True}

    if request.cookies.get('order_created') == 'True':
        context.update({'messages': [Message(text=f'New order has been created', tags='info')]})
        response = templates.TemplateResponse("admin/order/create.html", context=context)
        response.set_cookie('order_created', 'False')
    else:
        response = templates.TemplateResponse("admin/order/create.html", context=context)
    return response


@router.post("/order/create")
async def admin_order_create_endpoint(request: Request,
                                      next_page: str = Form(...),
                                      form: ord_m.OrderCreateSchema = Depends(ord_m.OrderCreateSchema.as_form),
                                      coupons_list: list = Depends(coup_m.get_valid_coupons)):
    coupon = None
    if form.coupon:
        coupon = await coup_m.get_coupon_by_id(form.coupon)
    try:
        order_data = form.model_dump()
        items_data = [{"product_id": product, "quantity": quantity}
                      for product, quantity
                      in zip(order_data['products'], order_data['quantities'])]
        order = await ord_m.create_order(order_data=order_data, items=items_data)

        redirect_url = next_page if next_page == 'create' else f'edit/{order["_id"]}'
        response = RedirectResponse(url=redirect_url,
                                    status_code=303, )
        response.set_cookie('order_created', 'True')
    except HTTPException as e:
        messages = [Message(e.detail)]
        response = templates.TemplateResponse("admin/order/create.html",
                                              {"request": request, "coupons_list": coupons_list,
                                               'admin': True, "messages": messages,
                                               "form": form, "coupon": coupon})
    except Exception:
        messages = [Message("An unexpected error occurred while creating the order")]
        response = templates.TemplateResponse("admin/order/create.html",
                                              {"request": request, "coupons_list": coupons_list,
                                               'admin': True, "messages": messages,
                                               "form": form, "coupon": coupon})
    return response


@router.get("/order/edit/{_id}")
async def admin_order_edit_endpoint(request: Request, _id: str, coupons_list: list = Depends(coup_m.get_valid_coupons)):
    order = await ord_m.get_order_by_id(_id)
    coupon = await coup_m.get_coupon_by_id(order["coupon"]['_id']) if order.get("coupon") else None
    items = await ord_m.get_order_items(order["items"])

    context = {"request": request, "order": order, "coupons_list": coupons_list,
               "coupon": coupon,
               'admin': True, "items": items}

    if request.cookies.get('order_created') == 'True':
        context['messages'] = [Message(text=f'New order {order["_id"]} has been created', tags='info')]
        response = templates.TemplateResponse("admin/order/edit.html", context=context)
        response.set_cookie('order_created', 'False')
    else:
        if (message := request.cookies.get('error_msg')) is not None and message != 'False':
            context['messages'] = [Message(text=message)]
        response = templates.TemplateResponse("admin/order/edit.html", context=context)
        if request.cookies.get('error_msg') != 'False':
            response.set_cookie('error_msg', 'False')
    return response


@router.post("/order/edit/{_id}")
async def admin_order_edit_endpoint(request: Request,
                                    _id: str,
                                    form: ord_m.OrderCreateSchema = Depends(ord_m.OrderCreateSchema.as_form),
                                    coupons_list: list = Depends(coup_m.get_valid_coupons)):
    try:
        order = await ord_m.edit_order(_id, form.model_dump())
        coupon = order.get('coupon')
        message = [Message(text=f'Order {order["_id"]} has been edited', tags='info')]
    except HTTPException as e:
        order = await ord_m.get_order_by_id(_id)
        coupon = order.get('coupon')
        if isinstance(coupon, dict) and '_id' in coupon:
            coupon = await coup_m.get_coupon_by_id(coupon['_id'])
        message = [Message(text=e.detail, tags='danger')]
    except Exception:
        order = await ord_m.get_order_by_id(_id)
        coupon = order.get('coupon')
        if isinstance(coupon, dict) and '_id' in coupon:
            coupon = await coup_m.get_coupon_by_id(coupon['_id'])
        message = [Message(text="An unexpected error occurred while editing the order", tags='danger')]

    context = {"request": request, "order": order, "coupon": coupon,
               "coupons_list": coupons_list,
               'messages': message,
               'admin': True}

    items = await ord_m.get_order_items(order["items"])
    context.update({"items": items})

    return templates.TemplateResponse("admin/order/edit.html", context)


@router.get("/order/delete/{_id}")
async def admin_order_delete_endpoint(request: Request, _id: str):
    return templates.TemplateResponse("admin/order/delete_confirm.html",
                                      {"request": request, "order_id": _id, 'admin': True})


@router.get("/order/delete_confirm/{_id}")
async def admin_order_delete_confirm_endpoint(request: Request, _id: str):
    await delete_object(_id, 'order')
    response = RedirectResponse(url='/admin/order/',
                                status_code=303, )
    response.set_cookie('order_deleted', 'True')
    return response


# COUPON ADMIN CRUD ROUTING
@router.get("/coupon/")
async def admin_coupon_list_endpoint(request: Request,
                                     pagination: Paginator = Depends(Paginator(coup_m.get_all_coupons))):
    coupons = await coup_m.get_all_coupons()
    context = {"request": request, "coupons": coupons[pagination.start:pagination.end],
               'admin': True,
               'paginator': pagination}

    return await list_endpoint_dry(request, context, model='coupon')


@router.get("/coupon/create")
async def admin_coupon_create_endpoint(request: Request):
    context = {"request": request, 'admin': True}

    if request.cookies.get('coupon_created') == 'True':
        context.update({'messages': [Message(text=f'New coupon has been created', tags='info')]})
        response = templates.TemplateResponse("admin/coupon/create.html", context=context)
        response.set_cookie('coupon_created', 'False')
    else:
        response = templates.TemplateResponse("admin/coupon/create.html", context=context)
    return response


@router.post("/coupon/create")
async def admin_coupon_create_endpoint(request: Request,
                                       next_page: str = Form(...),
                                       form: coup_m.CouponCreateSchema = Depends(coup_m.CouponCreateSchema.as_form)):
    try:
        coupon_data = form.model_dump()
        coupon = await coup_m.create_coupon(coupon_data)

        redirect_url = next_page if next_page == 'create' else f'edit/{coupon["_id"]}'
        response = RedirectResponse(url=redirect_url,
                                    status_code=303, )
        response.set_cookie('coupon_created', 'True')
    except HTTPException as e:
        messages = [Message(e.detail)]
        response = templates.TemplateResponse("admin/coupon/create.html",
                                              {"request": request, 'admin': True, "messages": messages, "form": form})
    except Exception:
        messages = [Message("An unexpected error occurred while creating the coupon")]
        response = templates.TemplateResponse("admin/coupon/create.html",
                                              {"request": request, 'admin': True, "messages": messages, "form": form})
    return response


@router.get("/coupon/edit/{_id}")
async def admin_coupon_edit_endpoint(request: Request, _id: str):
    coupon = await coup_m.get_coupon_by_id(_id)
    context = {"request": request, "coupon": coupon, 'admin': True, }

    if request.cookies.get('coupon_created') == 'True':
        context.update({'messages': [Message(text=f'New coupon {coupon["_id"]} has been created', tags='info')]})
        response = templates.TemplateResponse("admin/coupon/edit.html", context=context)
        response.set_cookie('coupon_created', 'False')
    else:
        response = templates.TemplateResponse("admin/coupon/edit.html", context=context)
    return response


@router.post("/coupon/edit/{_id}")
async def admin_coupon_edit_endpoint(request: Request,
                                     _id: str,
                                     form: coup_m.CouponCreateSchema = Depends(coup_m.CouponCreateSchema.as_form)):
    try:
        coupon = await coup_m.edit_coupon(_id, form.model_dump())
        message = [Message(text=f'Coupon {coupon["_id"]} has been edited', tags='info')]
    except HTTPException as e:
        coupon = await coup_m.get_coupon_by_id(_id)
        message = [Message(text=e.detail, tags='danger')]
    except Exception:
        coupon = await coup_m.get_coupon_by_id(_id)
        message = [Message(text="An unexpected error occurred while editing the coupon", tags='danger')]

    context = {"request": request, "coupon": coupon, 'messages': message, 'admin': True}

    return templates.TemplateResponse("admin/coupon/edit.html", context)


@router.get("/coupon/delete/{_id}")
async def admin_coupon_delete_endpoint(request: Request, _id: str):
    coupon = await coup_m.get_coupon_by_id(_id)
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return templates.TemplateResponse("admin/coupon/delete_confirm.html",
                                      {"request": request, "coupon": coupon, 'admin': True})


@router.get("/coupon/delete_confirm/{_id}")
async def admin_coupon_delete_confirm_endpoint(request: Request, _id: str):
    await delete_object(_id, 'coupon')
    response = RedirectResponse(url='/admin/coupon/',
                                status_code=303, )
    response.set_cookie('coupon_deleted', 'True')
    return response


# GENERAL


@router.post("/objects/delete/{model}", name="admin_objects_delete_endpoint")
async def admin_objects_delete_endpoint(request: Request, model: str, delete: list[str] = Form(...)):
    if delete[0] == 'on':
        delete = delete[1:]
    return templates.TemplateResponse("admin/objects/delete_confirm.html",
                                      {"request": request, "model": model, "delete": delete, 'admin': True})


@router.post("/objects/delete_confirm/{model}")
async def admin_objects_delete_confirm_endpoint(request: Request, model: str, delete: str = Form(...)):
    await delete_objects(delete, model)
    response = RedirectResponse(url=f'/admin/{model}/',
                                status_code=303, )
    response.set_cookie('objects_deleted', 'True')
    return response


async def list_endpoint_dry(request: Request, context: dict, model: str):
    """
    Common operation for listing endpoints.

    :param request: Request object from the FastAPI application.
    :param context: Dictionary containing data to be passed to the template.
    :param model: String representing the model for which the listing endpoint is called.
    :return: TemplateResponse for rendering the list.
    """
    message = None
    cookie_to_unset = None

    if request.cookies.get(f'{model}_deleted') == 'True':
        message = f'{model.capitalize()} has been deleted'
        cookie_to_unset = f'{model}_deleted'
    elif request.cookies.get('objects_deleted') == 'True':
        message = f'{model.capitalize()} objects has been deleted'
        cookie_to_unset = 'objects_deleted'

    if message:
        context.update({'messages': [Message(text=message, tags='info')]})

    response = templates.TemplateResponse(f'admin/{model}/list.html', context=context)

    if cookie_to_unset:
        response.set_cookie(cookie_to_unset, 'False')
    return response


# ---------------------------------------------------------------------------
# CSV EXPORT
# ---------------------------------------------------------------------------
@router.get("/export/orders")
async def admin_export_orders():
    orders = await ord_m.get_all_orders()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Customer", "Email", "Total", "Status", "Created"])
    for o in orders:
        writer.writerow([
            o._id, f"{o.first_name} {o.last_name}", o.email,
            f"${o.get_total_cost():.2f}", o.paid and "Paid" or "Pending",
            o.created,
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"},
    )


@router.get("/export/products")
async def admin_export_products():
    products = await prod_m.get_all_products()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Category", "Price", "Stock", "Available"])
    for p in products:
        writer.writerow([
            p["_id"], p["name"], p["category_name"],
            p["price"], p.get("stock", 0), p["available"],
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )
