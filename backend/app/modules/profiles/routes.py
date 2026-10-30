from fastapi import APIRouter

from app.modules.profiles.taxonomy import TAXONOMY, TaxonomyDTO

router = APIRouter()


@router.get("/taxonomy", response_model=TaxonomyDTO)
async def taxonomy():
    return TAXONOMY
