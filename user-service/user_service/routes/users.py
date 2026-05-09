from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound

from common.core.database import get_db
from user_service.schemas.user import UserCreate, UserOut, UserUpdate
from user_service.services import users as user_service
from user_service.core.logging import logger

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[UserOut])
async def get_users(db: AsyncSession = Depends(get_db)):
    logger.info("get_users_start")

    try:
        users = await user_service.get_all_users(db)

        logger.info("get_users_success", users_count=len(users))
        return users

    except Exception as e:
        logger.error("get_users_failed", error=str(e))
        raise


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("get_user_start", user_id=user_id)

    try:
        user = await user_service.get_user(user_id, db)

        logger.info("get_user_success", user_id=user_id)
        return user
    except NoResultFound:
        logger.warning("get_user_not_found", user_id=user_id)
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logger.error("get_user_error", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500)


@router.post("/", response_model=UserOut)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    logger.info("create_user_start", name=data.name, balance=data.balance)

    try:
        user = await user_service.create_user(data, db)

        logger.info("create_user_success", user_id=user.id)
        return JSONResponse(content=jsonable_encoder(user), status_code=201)

    except Exception as e:
        logger.error("create_user_failed", error=str(e))
        raise


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int, data: UserUpdate, db: AsyncSession = Depends(get_db)
):
    logger.info(
        "update_user_start", user_id=user_id, name=data.name, balance=data.balance
    )

    try:
        user = await user_service.update_user(user_id, data, db)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info("update_user_success", user_id=user_id)
        return user

    except HTTPException:
        logger.warning("update_user_not_found", user_id=user_id)
        raise

    except Exception as e:
        logger.error("update_user_failed", user_id=user_id, error=str(e))
        raise


@router.delete("/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    logger.info(
        "delete_user_start",
        user_id=user_id,
    )

    try:
        await user_service.delete_user(user_id, db)

        logger.info("delete_user_success", user_id=user_id)

        return Response(status_code=204)
    except NoResultFound:
        logger.warning("delete_user_not_found", user_id=user_id)
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logger.error("delete_user_error", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500)


