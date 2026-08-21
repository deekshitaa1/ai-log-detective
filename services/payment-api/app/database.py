import asyncio


DATABASE_HOST = "payments-primary"
DATABASE_REGION = "ap-south-1"


async def get_database_connection():
    """
    Establish a connection to the primary payments database.

    This represents the database dependency boundary
    that AegisAI will inspect during code localization.
    """

    for attempt in range(3):
        try:
            await asyncio.sleep(0.01)

            raise TimeoutError(
                f"Database connection timeout: {DATABASE_HOST}"
            )

        except TimeoutError:
            if attempt == 2:
                raise
