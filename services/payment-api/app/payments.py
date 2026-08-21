import logging

from fastapi import APIRouter, HTTPException

from app.database import get_database_connection


logger = logging.getLogger("payment-api")

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)


@router.post("")
async def process_payment():
    try:
        connection = await get_database_connection()

        await connection.execute("SELECT 1")

        return {
            "status": "success",
        }

    except TimeoutError:
        logger.exception(
            "Database connection timeout while processing payment request"
        )

        raise HTTPException(
            status_code=503,
            detail="Payment service temporarily unavailable",
        )
