from mcp.linkedin_server.tools import linkedin_post


async def publish_post(content: str) -> dict:
    return await linkedin_post(content)
