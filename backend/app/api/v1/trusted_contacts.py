from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.paging import Page

from app.core.auth import get_auth
from app.modules.contacts.schemas import ContactCreate, ContactPatch, ContactRead
from app.modules.contacts.service import ContactService

router = APIRouter(prefix="/v1/trusted-contacts", tags=["trusted contacts"])


def service(request: Request):
    return ContactService(request.app.state.engine)


@router.get("", response_model=Page[ContactRead])
async def list_contacts(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    contacts: ContactService = Depends(service),
):
    return await contacts.list(auth, limit=limit, cursor=cursor)


@router.post("", response_model=ContactRead)
async def create_contact(
    data: ContactCreate,
    auth: AuthContext = Depends(get_auth),
    contacts: ContactService = Depends(service),
):
    return await contacts.create(auth, data)


@router.patch("/{id}", response_model=ContactRead)
async def patch_contact(
    id: UUID,
    data: ContactPatch,
    auth: AuthContext = Depends(get_auth),
    contacts: ContactService = Depends(service),
):
    return await contacts.patch(auth, id, data)


@router.delete("/{id}", status_code=204)
async def delete_contact(
    id: UUID, auth: AuthContext = Depends(get_auth), contacts: ContactService = Depends(service)
):
    await contacts.delete(auth, id)
    return Response(status_code=204)
