import asyncio
from .tools import linkedin_post


async def handle_request(request: dict) -> dict:
    action = request.get("action")
    if action == "post":
        return await linkedin_post(request.get("content", ""))
    return {"error": f"Unknown action: {action}"}
