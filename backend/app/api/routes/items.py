"""
Demo CRUD 接口 — 演示前后端 + 数据库完整读写能力

提供 system_items 表的增删改查接口：
  POST   /items        创建 Item
  GET    /items        查询列表（分页、按 is_active 过滤）
  GET    /items/{id}   查询详情
  PUT    /items/{id}   更新 Item
  DELETE /items/{id}   删除 Item

Sprint0 阶段用于验证 前端 → 后端 → MySQL 主链路是否跑通。
"""

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.exception.base_exception import AppException
from app.core.exception.error_code import ITEM_NOT_FOUND
from app.db.session import get_db
from app.models.item import SystemItem
from app.schemas.common import ApiResponse, PaginatedResult
from app.schemas.item import ItemCreate, ItemResponse, ItemUpdate

router = APIRouter()


@router.post("", response_model=ApiResponse[ItemResponse], status_code=status.HTTP_201_CREATED, summary="创建 Item")
def create_item(payload: ItemCreate, db: Session = Depends(get_db)) -> ApiResponse[ItemResponse]:
    item = SystemItem(
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ApiResponse(data=item)


@router.get("", response_model=ApiResponse[PaginatedResult[ItemResponse]], summary="查询 Item 列表")
def list_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[PaginatedResult[ItemResponse]]:
    statement: Select[tuple[SystemItem]] = select(SystemItem).order_by(SystemItem.id.desc())
    count_statement = select(func.count()).select_from(SystemItem)

    if is_active is not None:
        statement = statement.where(SystemItem.is_active == is_active)
        count_statement = count_statement.where(SystemItem.is_active == is_active)

    total = db.scalar(count_statement) or 0
    items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()

    return ApiResponse(data=PaginatedResult(items=items, total=total, page=page, page_size=page_size))


@router.get("/{id}", response_model=ApiResponse[ItemResponse], summary="查询 Item 详情")
def get_item(id: int = Path(description="Item ID"), db: Session = Depends(get_db)) -> ApiResponse[ItemResponse]:
    item = db.get(SystemItem, id)
    if item is None:
        raise AppException.from_error_code(ITEM_NOT_FOUND)

    return ApiResponse(data=item)


@router.put("/{id}", response_model=ApiResponse[ItemResponse], summary="更新 Item")
def update_item(
    payload: ItemUpdate,
    id: int = Path(description="Item ID"),
    db: Session = Depends(get_db),
) -> ApiResponse[ItemResponse]:
    item = db.get(SystemItem, id)
    if item is None:
        raise AppException.from_error_code(ITEM_NOT_FOUND)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return ApiResponse(data=item)


@router.delete("/{id}", response_model=ApiResponse[bool], summary="删除 Item")
def delete_item(id: int = Path(description="Item ID"), db: Session = Depends(get_db)) -> ApiResponse[bool]:
    item = db.get(SystemItem, id)
    if item is None:
        raise AppException.from_error_code(ITEM_NOT_FOUND)

    db.delete(item)
    db.commit()
    return ApiResponse(data=True)
