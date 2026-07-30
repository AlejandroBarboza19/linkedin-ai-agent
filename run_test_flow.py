import asyncio
import os
import sys
import time
from mcp.linkedin_server.tools import open_browser, wait_for_human_auth, verify_active_session, create_post, close_browser

SIGNAL_FILE = ".hitl_signal"


async def clean_signal():
    if os.path.exists(SIGNAL_FILE):
        os.remove(SIGNAL_FILE)


async def wait_for_signal(timeout_minutes=60):
    start = time.time()
    print(f"\n{'='*50}")
    print("  HITL: Se requiere confirmacion para publicar")
    print(f"  En otra terminal, ejecuta:")
    print(f"    echo yes > {SIGNAL_FILE}")
    print(f"  O para cancelar:")
    print(f"    echo no > {SIGNAL_FILE}")
    print(f"{'='*50}\n", flush=True)
    while time.time() - start < timeout_minutes * 60:
        if os.path.exists(SIGNAL_FILE):
            with open(SIGNAL_FILE) as f:
                answer = f.read().strip().lower()
            os.remove(SIGNAL_FILE)
            return answer == "yes"
        await asyncio.sleep(2)
    print("  Timeout alcanzado, cancelando.", flush=True)
    return False


async def main():
    # Step 1: Open browser
    print("[1/5] Abriendo navegador...", flush=True)
    result = await open_browser()
    sid = result["session_id"]
    print(f"  Session ID: {sid}", flush=True)

    # Step 2: Wait for human auth
    print("\n[2/5] ESPERANDO AUTENTICACION HUMANA", flush=True)
    print("  El navegador se abrio en linkedin.com/login", flush=True)
    print("  Inicia sesion y resuelve 2FA manualmente.", flush=True)
    print("  La herramienta monitoreara automaticamente cuando completes el login.\n", flush=True)

    auth_result = await wait_for_human_auth(sid, timeout_minutes=5)
    print(f"  Resultado: {auth_result['message']}", flush=True)

    if auth_result["status"] != "ok":
        print("  No se pudo autenticar. Cerrando...", flush=True)
        await close_browser(sid)
        return

    # Step 3: Verify session
    print("\n[3/5] Verificando sesion...", flush=True)
    verify_result = await verify_active_session(sid)
    print(f"  {verify_result}", flush=True)

    # Step 4: HITL signal
    await clean_signal()
    confirmed = await wait_for_signal()

    if confirmed:
        # Step 5: Create post (prepares editor, does NOT auto-publish)
        print("\n[4/5] Preparando post en el editor...", flush=True)
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

    # Step 6: Close browser
    print("\n[5/5] Cerrando navegador...", flush=True)
    close_result = await close_browser(sid)
    print(f"  {close_result}", flush=True)
    print("\n¡Flujo completo!", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrumpido por el usuario.", flush=True)
