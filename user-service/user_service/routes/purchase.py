from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.database import get_db
from user_service.core.logging import logger
from common.schemas.purchase import (
    PrepareResponse,
    UserPrepareRequest,
    UserCommitResponse,
    UserCommitRequest,
    RollbackRequest,
)
from user_service.services import purchases as purchases_service

router = APIRouter(prefix="/purchases", tags=["purchases"])

"""
The coordinator passes all data needed to make decition abount purchase.
We prepare transaction and detatch client (in case if we have multiple replicas of microservice)
"""


@router.post("/prepare", response_model=PrepareResponse)
async def prepare(request: UserPrepareRequest):
    logger.info(
        "prepare_purchase_user_start",
        transaction_id=request.transaction_id,
        user_id=request.user_id,
        amount=request.amount,
    )
    try:
        result = await purchases_service.prepare(
            request.transaction_id, request.user_id, request.amount
        )
        return result
    except Exception as e:
        logger.error("route_user_prepare_error", error=str(e))
        raise HTTPException(status_code=500, detail="Prepare failed")


"""
Endpoint commits prepared transaction.
Purchase is being commited to the microservice db
"""


@router.post("/commit", response_model=UserCommitResponse)
async def commit(request: UserCommitRequest):
    logger.info("commit_purchase_user_commit", transaction_id=request.transaction_id)
    try:
        result = await purchases_service.commit(request.transaction_id, request.user_id)
        return result
    except Exception as e:
        logger.error("route_user_commit_error", error=str(e))
        raise HTTPException(status_code=500, detail="Commit failed")


"""
Endpoint rollsback prepared transaction.
Purchase operations must rollback.
"""


@router.post("/rollback", status_code=204)
async def rollback(request: RollbackRequest):
    logger.info(
        "rollback_purchase_user_rollback", transaction_id=request.transaction_id
    )
    try:
        await purchases_service.rollback(request.transaction_id)
    except Exception as e:
        logger.error("route_user_rollback_error", error=str(e))
        raise HTTPException(status_code=500, detail="Rollback failed")
