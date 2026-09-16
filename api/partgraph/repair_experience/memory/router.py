from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    Request,
    UploadFile,
    status,
)
from starlette.responses import FileResponse

from ..auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from ..config import settings
from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..repair_session.router import (
    DEVICE_HEADER,
    IDEMPOTENCY_HEADER,
    _parse_device_id,
    _parse_idempotency_key,
)
from .photo_lifecycle import (
    create_photo,
    cron_request_authorized,
    delete_photo,
    photo_content,
    reconcile_photo_storage_batch,
    reconcile_photo_storage_item,
)
from .schemas import (
    FastenerCreate,
    FastenerRead,
    FastenerStateUpdate,
    InventoryItemCreate,
    InventoryItemRead,
    InventoryStateUpdate,
    ObservationCreate,
    ObservationRead,
    PhotoDeleteRead,
    PhotoEvidenceRead,
    PhotoPurpose,
    StorageLocationCreate,
    StorageLocationRead,
)
from .service import (
    create_fastener,
    create_inventory_item,
    create_observation,
    create_storage_location,
    list_fasteners,
    list_inventory,
    list_observations,
    list_photos,
    list_storage_locations,
    update_fastener_state,
    update_inventory_state,
)
from .storage import PhotoFormatError, PhotoResourceLimitError, prepare_photo

ERROR_RESPONSES = {
    401: {"model": ErrorEnvelope},
    403: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    413: {"model": ErrorEnvelope},
    415: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    500: {"model": ErrorEnvelope},
    503: {"model": ErrorEnvelope},
}
router = APIRouter(
    prefix="/api/v1/repair-sessions",
    tags=["Repair Memory"],
    responses=ERROR_RESPONSES,
)
CsrfDep = Depends(require_csrf)
DeviceHeader = Annotated[str | None, Header(alias=DEVICE_HEADER)]
IdempotencyHeader = Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)]


def _mutation_headers(device_header: str | None, idempotency_header: str | None) -> tuple[UUID, str]:
    device_id = _parse_device_id(device_header, required=True)
    assert device_id is not None
    return device_id, _parse_idempotency_key(idempotency_header)


@router.get("/{session_id}/storage-locations", response_model=list[StorageLocationRead])
async def storage_locations(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> list[StorageLocationRead]:
    return await list_storage_locations(db, user_id=user.id, session_id=session_id)


@router.post(
    "/{session_id}/storage-locations",
    response_model=StorageLocationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def add_storage_location(
    session_id: UUID,
    payload: StorageLocationCreate,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: DeviceHeader = None,
    idempotency_header: IdempotencyHeader = None,
) -> StorageLocationRead:
    device_id, idempotency_key = _mutation_headers(device_header, idempotency_header)
    return await create_storage_location(
        db,
        user_id=user.id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )


@router.get("/{session_id}/fasteners", response_model=list[FastenerRead])
async def fasteners(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> list[FastenerRead]:
    return await list_fasteners(db, user_id=user.id, session_id=session_id)


@router.post(
    "/{session_id}/fasteners",
    response_model=FastenerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def add_fastener(
    session_id: UUID,
    payload: FastenerCreate,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: DeviceHeader = None,
    idempotency_header: IdempotencyHeader = None,
) -> FastenerRead:
    device_id, idempotency_key = _mutation_headers(device_header, idempotency_header)
    return await create_fastener(
        db,
        user_id=user.id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )


@router.patch(
    "/{session_id}/fasteners/{fastener_id}",
    response_model=FastenerRead,
    dependencies=[CsrfDep],
)
async def change_fastener_state(
    session_id: UUID,
    fastener_id: UUID,
    payload: FastenerStateUpdate,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: DeviceHeader = None,
    idempotency_header: IdempotencyHeader = None,
) -> FastenerRead:
    device_id, idempotency_key = _mutation_headers(device_header, idempotency_header)
    return await update_fastener_state(
        db,
        user_id=user.id,
        session_id=session_id,
        fastener_id=fastener_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )


@router.get("/{session_id}/inventory", response_model=list[InventoryItemRead])
async def inventory(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> list[InventoryItemRead]:
    return await list_inventory(db, user_id=user.id, session_id=session_id)


@router.post(
    "/{session_id}/inventory",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def add_inventory_item(
    session_id: UUID,
    payload: InventoryItemCreate,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: DeviceHeader = None,
    idempotency_header: IdempotencyHeader = None,
) -> InventoryItemRead:
    device_id, idempotency_key = _mutation_headers(device_header, idempotency_header)
    return await create_inventory_item(
        db,
        user_id=user.id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )


@router.patch(
    "/{session_id}/inventory/{item_id}",
    response_model=InventoryItemRead,
    dependencies=[CsrfDep],
)
async def change_inventory_state(
    session_id: UUID,
    item_id: UUID,
    payload: InventoryStateUpdate,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: DeviceHeader = None,
    idempotency_header: IdempotencyHeader = None,
) -> InventoryItemRead:
    device_id, idempotency_key = _mutation_headers(device_header, idempotency_header)
    return await update_inventory_state(
        db,
        user_id=user.id,
        session_id=session_id,
        item_id=item_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )


@router.get("/{session_id}/observations", response_model=list[ObservationRead])
async def observations(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> list[ObservationRead]:
    return await list_observations(db, user_id=user.id, session_id=session_id)


@router.post(
    "/{session_id}/observations",
    response_model=ObservationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def add_observation(
    session_id: UUID,
    payload: ObservationCreate,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: DeviceHeader = None,
    idempotency_header: IdempotencyHeader = None,
) -> ObservationRead:
    device_id, idempotency_key = _mutation_headers(device_header, idempotency_header)
    return await create_observation(
        db,
        user_id=user.id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        payload=payload,
    )


@router.get("/{session_id}/photos", response_model=list[PhotoEvidenceRead])
async def photos(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> list[PhotoEvidenceRead]:
    return await list_photos(db, user_id=user.id, session_id=session_id)


@router.post(
    "/{session_id}/photos",
    response_model=PhotoEvidenceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def add_photo(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    background_tasks: BackgroundTasks,
    photo: Annotated[UploadFile, File()],
    purpose: Annotated[PhotoPurpose, Form()] = "general",
    observation_id: Annotated[UUID | None, Form()] = None,
    fastener_id: Annotated[UUID | None, Form()] = None,
    device_header: DeviceHeader = None,
    idempotency_header: IdempotencyHeader = None,
) -> PhotoEvidenceRead:
    device_id, idempotency_key = _mutation_headers(device_header, idempotency_header)
    try:
        data = await photo.read(settings.photo_max_bytes + 1)
    finally:
        await photo.close()
    if not data or len(data) > settings.photo_max_bytes:
        raise PartGraphError(
            code=ErrorCode.PHOTO_TOO_LARGE,
            message=f"Photo must be between 1 byte and {settings.photo_max_bytes} bytes.",
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        )
    try:
        prepared = await prepare_photo(data, maximum_bytes=settings.photo_max_bytes)
    except PhotoResourceLimitError as exc:
        raise PartGraphError(
            code=ErrorCode.PHOTO_TOO_LARGE,
            message="Photo dimensions, decoded pixel count, or sanitized size exceed the allowed limit.",
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        ) from exc
    except PhotoFormatError as exc:
        raise PartGraphError(
            code=ErrorCode.PHOTO_MEDIA_TYPE_UNSUPPORTED,
            message="Photo content must be a valid JPEG, PNG, WebP, or HEIC image.",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        ) from exc
    result = await create_photo(
        db,
        user_id=user.id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        purpose=purpose,
        observation_id=observation_id,
        fastener_id=fastener_id,
        filename=photo.filename,
        data=prepared.data,
        maximum_bytes=settings.photo_max_bytes,
    )
    background_tasks.add_task(reconcile_photo_storage_item, result.id)
    return result


@router.get("/{session_id}/photos/{photo_id}/content", response_class=FileResponse)
async def get_photo_content(
    session_id: UUID,
    photo_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> FileResponse:
    row, path = await photo_content(
        db,
        user_id=user.id,
        session_id=session_id,
        photo_id=photo_id,
    )
    return FileResponse(path, media_type=row.media_type)


@router.delete(
    "/{session_id}/photos/{photo_id}",
    response_model=PhotoDeleteRead,
    dependencies=[CsrfDep],
)
async def remove_photo(
    session_id: UUID,
    photo_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    background_tasks: BackgroundTasks,
    device_header: DeviceHeader = None,
    idempotency_header: IdempotencyHeader = None,
) -> PhotoDeleteRead:
    device_id, idempotency_key = _mutation_headers(device_header, idempotency_header)
    result = await delete_photo(
        db,
        user_id=user.id,
        session_id=session_id,
        photo_id=photo_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
    )
    background_tasks.add_task(reconcile_photo_storage_item, result.id)
    return result


@router.get("/maintenance/photo-storage/reconcile", include_in_schema=False)
async def reconcile_photo_storage(request: Request) -> dict[str, int]:
    if not cron_request_authorized(request.headers.get("authorization")):
        raise PartGraphError(
            code=ErrorCode.AUTH_REQUIRED,
            message="Photo storage reconciliation authorization required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return await reconcile_photo_storage_batch()
