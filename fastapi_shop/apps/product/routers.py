from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Query, Request, HTTPException, Depends

from apps.cart.cart import CartManager
from apps.cart.routers import get_current_cart
from apps.category.models import get_all_categories, get_category_by_slug, get_category_by_id
from apps.product.models import ProductSchema, create_product, get_products_by_category, get_all_products, \
    get_product_by_slug, ProductCreateSchema, get_available_products, search_products, suggest_products, \
    get_category_product_counts
from dependencies import templates
from recommender import Recommender
from cache import cache_get, cache_set, cache_delete
from utils import Message

router = APIRouter()


@router.post("/")
async def create_product_endpoint(product: ProductCreateSchema = Depends(ProductCreateSchema)):
    result = await create_product(product_data=product.model_dump())
    await cache_delete("products:*")
    return result


@router.get("/", response_model=dict)
async def product_list_endpoint(
    request: Request,
    page: int = Query(1, gt=0),
    per_page: int = Query(12, gt=0, le=100),
    sort: str = Query("newest", regex="^(price_asc|price_desc|name_asc|name_desc|newest|oldest)$"),
    current_cart: CartManager = Depends(get_current_cart),
):
    categories = await get_all_categories()
    counts = await get_category_product_counts()
    products = await get_available_products(sort=sort)
    total = len(products)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    paged = products[start:start + per_page]
    return templates.TemplateResponse("shop/product/list.html", {
        "request": request, "categories": categories,
        "category_counts": counts,
        "products": paged, "cart": current_cart,
        "page": page, "per_page": per_page, "total": total,
        "total_pages": total_pages, "sort": sort,
    })


@router.get("/suggest")
async def product_suggest(
    q: str = Query(..., min_length=1, description="Search query"),
):
    suggestions = await suggest_products(q)
    return suggestions


@router.get("/search")
async def product_search(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, gt=0),
    per_page: int = Query(12, gt=0, le=100),
    current_cart: CartManager = Depends(get_current_cart),
):
    categories = await get_all_categories()
    counts = await get_category_product_counts()
    products = await search_products(q)
    total = len(products)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    paged = products[start:start + per_page]
    return templates.TemplateResponse("shop/product/list.html", {
        "request": request, "categories": categories,
        "category_counts": counts,
        "products": paged, "cart": current_cart,
        "search_query": q, "total": total,
        "page": page, "per_page": per_page, "total_pages": total_pages,
    })


@router.get("/{category_slug}", response_model=dict)
async def product_list_by_category_endpoint(
    request: Request,
    category_slug: str,
    page: int = Query(1, gt=0),
    per_page: int = Query(12, gt=0, le=100),
    sort: str = Query("newest", regex="^(price_asc|price_desc|name_asc|name_desc|newest|oldest)$"),
    current_cart: CartManager = Depends(get_current_cart),
):
    categories = await get_all_categories()
    counts = await get_category_product_counts()
    category = await get_category_by_slug(slug=category_slug)
    products = await get_products_by_category(category=category, sort=sort)
    total = len(products)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    paged = products[start:start + per_page]
    return templates.TemplateResponse("shop/product/list.html", {
        "request": request, "category": category,
        "categories": categories, "category_counts": counts,
        "products": paged, "cart": current_cart,
        "page": page, "per_page": per_page, "total": total,
        "total_pages": total_pages, "sort": sort,
    })


@router.get("/{_id}/{slug}", response_model=ProductSchema)
async def product_detail(request: Request, _id: str, slug: str, current_cart: CartManager = Depends(get_current_cart)):
    try:
        oid = ObjectId(_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Product not found")
    product_schema = await get_product_by_slug(_id=oid, slug=slug)
    if not product_schema:
        raise HTTPException(status_code=404, detail="Product not found")
    category = await get_category_by_id(_id=product_schema['category_id'])
    context = {"request": request, "product": product_schema,
               "category": category, "cart": current_cart}
    r = Recommender([product_schema['_id']])
    recommendations = await r.suggest_products_for()
    context.update({'recommendations': recommendations})

    if request.cookies.get('cart_updated') == '1':
        context.update({'messages': [Message(text='Product has been added to cart', tags='info')]})
        response = templates.TemplateResponse("shop/product/detail.html", context=context)
        response.set_cookie('cart_updated', '0')
    else:
        response = templates.TemplateResponse("shop/product/detail.html", context=context)
    return response
