"""
Flujo de prueba / demo del LinkedIn AI Agent.

Este script ejercita todas las tools MCP directamente (sin pasar por el agente
de OpenCode) para verificar el pipeline de automatización del navegador
de principio a fin.

La confirmación HITL usa una señal por archivo (.hitl_signal) como mecanismo
simple para pruebas automatizadas y CI.

Para el flujo REAL del agente (vía conversación con OpenCode), ver:
  - agents/linkedin_agent.md
  - .opencode/skills/linkedin-poster/SKILL.md

En el flujo real, la confirmación HITL ocurre por conversación,
NO mediante señales por archivo.
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
    print("  Abre OTRA terminal en la MISMA carpeta del proyecto")
    print("  (donde se esta ejecutando este script) y ejecuta:")
    print()
    print("  PowerShell:")
    print(f"    Set-Content -Path {SIGNAL_FILE} -Value yes")
    print("  CMD:")
    print(f"    echo yes > {SIGNAL_FILE}")
    print()
    print("  O para cancelar (PowerShell / CMD):")
    print(f"    Set-Content -Path {SIGNAL_FILE} -Value no   /   echo no > {SIGNAL_FILE}")
    print("=" * 50, flush=True)
    while time.time() - start < timeout_minutes * 60:
        content = await asyncio.to_thread(_read_signal)
        if content:
            return content == "yes"
        await asyncio.sleep(2)
    print("  Timeout alcanzado, cancelando.", flush=True)
    return False


async def main():
    # Paso 1: Abrir navegador
    print("[1/5] Abriendo navegador...", flush=True)
    result = await open_browser()
    sid = result["session_id"]
    print(f"  Session ID: {sid}", flush=True)

    # Paso 2: Esperar a que el usuario confirme el login manualmente
    print("\n[2/5] ESPERANDO QUE INICIES SESION", flush=True)
    print("  El navegador se abrio en linkedin.com/login", flush=True)
    print("  Inicia sesion y resuelve 2FA manualmente en el navegador.", flush=True)
    print("  Cuando hayas iniciado sesion, confirma en OTRA terminal", flush=True)
    print("  (en la MISMA carpeta del proyecto):\n", flush=True)
    await clean_signal()
    login_confirmed = await wait_for_signal("iniciar sesion en el navegador")

    if not login_confirmed:
        print("  Login cancelado. Cerrando...", flush=True)
        await close_browser(sid)
        return

    # Confirmar el estado de autenticación en la sesión
    auth_result = await wait_for_human_auth(sid, timeout_minutes=0.1)
    print(f"  Auth: {auth_result['message']}", flush=True)

    # Paso 3: Verificar sesión
    print("\n[3/5] Verificando sesion...", flush=True)
    verify_result = await verify_active_session(sid)
    print(f"  {verify_result}", flush=True)

    if not verify_result.get("active"):
        print("  Sesion no activa. Cerrando...", flush=True)
        await close_browser(sid)
        return

    # Paso 4: Confirmar publicación
    print("\n[4/5] CONFIRMAR PUBLICACION", flush=True)
    await clean_signal()
    confirmed = await wait_for_signal("confirmar publicacion")

    if confirmed:
        print("\n  Publicando post en LinkedIn...", flush=True)
        post_result = await create_post(sid, "Hola mundo")
        print(f"  {post_result}", flush=True)
    else:
        print("\n  Publicacion cancelada por el usuario.", flush=True)

    # Paso 5: Cerrar navegador
    print("\n[5/5] Cerrando navegador...", flush=True)
    close_result = await close_browser(sid)
    print(f"  {close_result}", flush=True)
    print("\n¡Flujo completo!", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrumpido por el usuario.", flush=True)
