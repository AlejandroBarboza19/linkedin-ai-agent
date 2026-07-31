# LinkedIn Poster Skill

## Objective

Publicar contenido en LinkedIn usando Playwright para navegación real (navegador visible). La skill orquesta la validación del contenido, la confirmación humana vía conversación, el flujo de login manual con HITL, y la publicación vía MCP `linkedin_server`.

## Activation

La skill se activa cuando el usuario solicita:

- Publicar un post en LinkedIn.
- Redactar y publicar contenido profesional.
- Compartir una nota o artículo en LinkedIn.

## Dependencies

- **MCP Server:** `linkedin_server` — controla Playwright (navegador visible, no headless).
- **Agent:** `linkedin_agent` — define la identidad y reglas HITL.
- **Logger:** `src/telemetry/logger.py` — registra cada acción para auditoría.

## Pre-flight Validations

Antes de abrir el navegador, la skill debe validar:

| Validación | Regla |
|---|---|
| **Contenido no vacío** | El texto debe tener al menos 1 carácter. |
| **Longitud máxima** | Máximo 3000 caracteres (límite de LinkedIn). |
| **Sin datos sensibles** | El contenido no debe contener contraseñas, tokens, API keys o información personal identificable. |
| **Sin enlaces acortados** | No se permiten URLs acortadas (bit.ly, etc.). Usar URLs completas. |
| **Sin menciones masivas** | No etiquetar más de 5 personas o empresas por post. |

## Publication Flow

```
1. Redactar o recibir contenido del usuario (conversación)
       │
2. Ejecutar validaciones pre-flight
       │
3. Mostrar preview al usuario por chat
       │
4. [HITL] ¿Usuario confirma preview?
       ├── Sí → continuar
       └── No → devolver al usuario para edición
       │
5. MCP: open_browser_tool → navegador visible en linkedin.com/login
       │
6. [HITL] El agente notifica: "Navegador abierto. Inicia sesión."
       El usuario ingresa credenciales + 2FA manualmente en el navegador.
       │
7. MCP: wait_for_human_auth_tool → detecta que la URL salió de /login
       │
8. MCP: verify_session_tool → confirma sesión activa
       │
9. MCP: create_post_tool(content) → escribe contenido en el editor
       │   (el botón Publicar NO se pulsa automáticamente)
       │
10. [HITL] El agente pregunta por chat:
    "El post está listo en el editor. Revisa el contenido
    y haz clic en 'Publicar' si estás de acuerdo."
       │
11. [HITL] Usuario hace clic en "Publicar" manualmente en el navegador.
       │
12. MCP: close_browser_tool → cerrar navegador, descartar cookies
       │
13. El agente notifica resultado por chat.
```

## Human in the Loop (HITL)

Tres puntos requieren intervención humana obligatoria:

1. **Confirmación de preview** — El agente muestra el contenido por chat y pregunta antes de abrir el navegador.
2. **Login y 2FA** — El agente abre linkedin.com/login y espera. El usuario ingresa credenciales y resuelve 2FA manualmente. El agente nunca toca los campos de contraseña ni maneja códigos.
3. **Publicación final** — El agente escribe el contenido en el editor pero nunca pulsa "Publicar". El usuario hace clic manualmente tras revisión visual.

La comunicación HITL ocurre siempre por conversación (chat), no por archivos de señal ni comandos de consola.

## Security Restrictions

1. **No almacenar credenciales** — El agente nunca guarda, loguea o gestiona contraseñas, cookies o tokens de sesión.
2. **No persistir sesión** — Las cookies viven solo en la sesión del navegador. Al cerrar el navegador, todo se descarta.
3. **No rellenar login** — El agente nunca interactúa con los campos de email/contraseña. Es responsabilidad exclusiva del usuario.
4. **No reintentar ante timeout de login** — Si el usuario no completa el login en un tiempo razonable, la skill cancela y notifica.
5. **Audit logging** — Cada publicación exitosa se registra con timestamp (sin incluir credenciales ni cookies).

## Output

La skill retorna un dict con:

```python
{
    "status": "ok" | "error" | "cancelled",
    "message": "Post published successfully" | "User cancelled" | "...",
    "timestamp": "2025-07-30T12:00:00Z"
}
```
