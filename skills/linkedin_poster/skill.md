# LinkedIn Poster Skill

## Objective

Publicar contenido en LinkedIn usando Playwright para navegación real. La skill orquesta la validación del contenido, la confirmación humana, el flujo de login manual con HITL, y la publicación vía MCP `linkedin_server`.

## Activation

La skill se activa cuando el usuario solicita:

- Publicar un post en LinkedIn.
- Redactar y publicar contenido profesional.
- Compartir una nota o artículo en LinkedIn.

## Dependencies

- **MCP Server:** `linkedin_server` — controla Playwright (navegador headless).
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
1. Redactar o recibir contenido del usuario
       │
2. Ejecutar validaciones pre-flight
       │
3. Mostrar preview al usuario
       │
4. [HITL] ¿Usuario confirma preview?
       ├── Sí → continuar
       └── No → devolver al usuario para edición
       │
5. Iniciar Playwright vía MCP (navegador headless)
       │
6. Navegar a linkedin.com/login
       │
7. [HITL] Esperar login manual del usuario
       │   - Usuario ingresa email y contraseña
       │   - Usuario resuelve 2FA si es necesario
       │   - El agente detecta que la sesión está activa
       │
8. Navegar a la página de creación de post
       │
9. Rellenar contenido en el editor
       │
10. [HITL] Mostrar confirmación final
       ├── Sí → hacer clic en "Publicar"
       └── No → cerrar navegador sin publicar
       │
11. Notificar resultado
       │
12. Cerrar navegador (las cookies se descartan automáticamente)
```

## Human in the Loop (HITL)

Esta skill requiere intervención humana en dos puntos críticos:

1. **Login y 2FA** — El agente abre linkedin.com/login y espera. El usuario debe ingresar sus credenciales y resolver cualquier 2FA manualmente. El agente nunca toca los campos de contraseña ni maneja códigos.
2. **Confirmación de publicación** — La skill nunca publica sin confirmación explícita del usuario.

Preview mostrado antes de abrir el navegador:

```
📝 PREVIEW
─────────────────────────
{texto del post}

¿Confirmas que quieres publicar esto?
Escribe "sí" para continuar o "no" para editar.
```

Confirmación final antes de hacer clic en "Publicar":

```
⚠️ CONFIRMACIÓN FINAL
─────────────────────────
El navegador está listo en linkedin.com.
El post está escrito en el editor.

¿Confirmas que el contenido es correcto y deseas publicar?
Escribe "sí" para publicar o "no" para cerrar sin publicar.
```

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
