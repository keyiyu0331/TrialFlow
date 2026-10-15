from fastapi import HTTPException, Query, status

from ..schemas import ErrorResponse

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Resource not found"}}
VALIDATION_ERROR = {422: {"model": ErrorResponse, "description": "Invalid request"}}


def not_found(resource: str, resource_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"detail": f"{resource} {resource_id} not found", "code": "not_found"},
    )


def limit_param(default: int = 50):
    return Query(default, ge=1, le=500)


def offset_param():
    return Query(0, ge=0)
