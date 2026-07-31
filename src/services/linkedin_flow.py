from mcp.linkedin_server.tools import create_post


async def publish_post(session_id: str, content: str) -> dict:
    return await create_post(session_id, content)
