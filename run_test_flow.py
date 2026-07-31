"""
Test / demo flow for the LinkedIn AI Agent.

This script exercises all MCP tools directly (bypassing the OpenCode agent)
to verify the browser automation pipeline end-to-end.

HITL confirmation uses a file signal (.hitl_signal) as a simple mechanism
for automated and CI testing.

For the REAL agent flow (via OpenCode conversation), see:
  - agents/linkedin_agent.md
  - .opencode/skills/linkedin-poster/SKILL.md

In the real flow, HITL confirmation happens through chat conversation,
NOT through file signals.
"""

import asyncio
import os
import time

from mcp.linkedin_server.tools import (
    close_browser,
    create_post,
    open_browser,
    verify_active_session,
    wait_for_human_auth,
)

SIGNAL_FILE = ".hitl_signal"


async def clean_signal():
    if os.path.exists(SIGNAL_FILE):
        os.remove(SIGNAL_FILE)


def _read_signal() -> str:
    if not os.path.exists(SIGNAL_FILE):
        return ""
    with open(SIGNAL_FILE, "rb") as f:
        raw = f.read()
    os.remove(SIGNAL_FILE)
    content = raw.decode("utf-8", errors="replace")
    return "".join(c for c in content if c.isalnum()).lower()


async def wait_for_signal(label="confirmacion", timeout_minutes=60):
    start = time.time()
    print("=" * 50)
    print(f"  HITL: Se requiere {label}")
    print("  En otra terminal, ejecuta:")
    print(f"    Set-Content -Path {SIGNAL_FILE} -Value yes")
    print("  O para cancelar:")
    print(f"    Set-Content -Path {SIGNAL_FILE} -Value no")
    print("=" * 50, flush=True)
    while time.time() - start < timeout_minutes * 60:
        content = await asyncio.to_thread(_read_signal)
        if content:
            return content == "yes"
        await asyncio.sleep(2)
    print("  Timeout alcanzado, cancelando.", flush=True)
    return False


async def main():
    # Step 1: Open browser
    print("[1/5] Abriendo navegador...", flush=True)
    result = await open_browser()
    sid = result["session_id"]
    print(f"  Session ID: {sid}", flush=True)

    # Step 2: Wait for user to confirm login manually
    print("\n[2/5] ESPERANDO QUE INICIES SESION", flush=True)
    print("  El navegador se abrio en linkedin.com/login", flush=True)
    print("  Inicia sesion y resuelve 2FA manualmente en el navegador.", flush=True)
    print("  Cuando hayas iniciado sesion, confirma en OTRA terminal:\n", flush=True)
    await clean_signal()
    login_confirmed = await wait_for_signal("iniciar sesion en el navegador")

    if not login_confirmed:
        print("  Login cancelado. Cerrando...", flush=True)
        await close_browser(sid)
        return

    # Confirm auth status in the session
    auth_result = await wait_for_human_auth(sid, timeout_minutes=0.1)
    print(f"  Auth: {auth_result['message']}", flush=True)

    # Step 3: Verify session
    print("\n[3/5] Verificando sesion...", flush=True)
    verify_result = await verify_active_session(sid)
    print(f"  {verify_result}", flush=True)

    if not verify_result.get("active"):
        print("  Sesion no activa. Cerrando...", flush=True)
        await close_browser(sid)
        return

    # Step 4: Confirm publish
    print("\n[4/5] CONFIRMAR PUBLICACION", flush=True)
    await clean_signal()
    confirmed = await wait_for_signal("confirmar publicacion")

    if confirmed:
        print("\n  Preparando post en el editor...", flush=True)
        post_result = await create_post(sid, "Hola mundo")
        print(f"  {post_result}", flush=True)

        if post_result.get("status") == "ok":
            print("\n  Ve al navegador, verifica el contenido y haz clic en 'Post'.", flush=True)
            print("  Presiona Ctrl+C cuando termines.", flush=True)
            try:
                while True:
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                pass
        else:
            print(f"\n  Error al preparar post: {post_result.get('message', 'desconocido')}", flush=True)
    else:
        print("\n  Publicacion cancelada por el usuario.", flush=True)

    # Step 5: Close browser
    print("\n[5/5] Cerrando navegador...", flush=True)
    close_result = await close_browser(sid)
    print(f"  {close_result}", flush=True)
    print("\n¡Flujo completo!", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrumpido por el usuario.", flush=True)
