from fastapi import APIRouter, Body, HTTPException

from apps.category.models import CategorySchema, create_category, get_all_categories, get_category_by_slug, \
    get_category_by_id

router = APIRouter()


@router.post("/")
async def create_category_endpoint(category: CategorySchema = Body(default=None)):
    if category is None:
        raise HTTPException(status_code=422, detail="Request body must contain a valid category object")
    category_data = await create_category(category.model_dump())
    return category_data


@router.get("/")
async def get_all_categories_endpoint():
    categories = await get_all_categories()
    return categories


@router.get("/{identifier}", response_model=CategorySchema)
async def get_category_by_identifier_endpoint(identifier: str):
    category_schema = await get_category_by_id(_id=identifier)
    if not category_schema:
        category_schema = await get_category_by_slug(slug=identifier)
    if category_schema:
        return category_schema
    raise HTTPException(status_code=404, detail="Category not found")
