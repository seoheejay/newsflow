"""공통 응답 스키마."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    """SR-I-304: 모든 목록 응답의 형태."""

    total_count: int
    page: int
    items_per_page: int
    items: list[T]
