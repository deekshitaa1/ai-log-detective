from app.models import RepositoryFile
from app.services.repair import generate_repair_proposal

content = """import asyncio

DATABASE_HOST = "payments-primary"

async def get_database_connection():
    await asyncio.sleep(0.01)

    raise TimeoutError(
        f"Database connection timeout: {DATABASE_HOST}"
    )
"""

file = RepositoryFile(
    path="services/payment-api/app/database.py",
    content=content,
    language="python",
    size_bytes=len(content),
)

proposal = generate_repair_proposal(file)

print("TYPE:", proposal.repair_type)
print("DIFF EMPTY:", not bool(proposal.diff))
print()
print("DIFF:")
print(proposal.diff)
