import os
import httpx


LINKEDIN_API_URL = "https://api.linkedin.com/v2"


async def linkedin_post(content: str) -> dict:
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "author": "urn:li:person:me",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LINKEDIN_API_URL}/ugcPosts", headers=headers, json=payload
        )
    resp.raise_for_status()
    return resp.json()
