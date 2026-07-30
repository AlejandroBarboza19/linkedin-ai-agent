---
name: linkedin-poster
description: Publicar contenido en LinkedIn usando Playwright con Human in the Loop para login y 2FA
---

## Objective

Publicar contenido en LinkedIn usando Playwright para navegación real. La skill orquesta la validación del contenido, la confirmación humana, el flujo de login manual con HITL, y la publicación vía MCP `linkedin_server`.

## Activation

La skill se activa cuando el usuario solicita:

- Publicar un post en LinkedIn.
- Redactar y publicar contenido profesional.
- Compartir una nota o artículo en LinkedIn.

## Dependencies

- **MCP Server:** `linkedin_server` — controla Playwright (navegador visible).
- **Agent:** `linkedin-agent` — define la identidad y reglas HITL.

## Pre-flight Validations

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
5. MCP: open_browser_tool → navegador visible en linkedin.com/login
       │
6. [HITL] Esperar login manual del usuario (credenciales + 2FA)
       │
7. MCP: verify_session_tool → confirmar sesión activa
       │
8. MCP: create_post_tool(content) → escribir contenido en el editor
       │
9. [HITL] Confirmación final antes de publicar
       │
10. Usuario hace clic en "Publicar" manualmente
       │
11. MCP: close_browser_tool → cerrar navegador, descartar cookies
```

## Human in the Loop (HITL)

Dos puntos críticos requieren intervención humana obligatoria:

1. **Login y 2FA** — El agente abre linkedin.com/login y espera. El usuario ingresa credenciales y resuelve 2FA manualmente.
2. **Confirmación de publicación** — La skill nunca publica sin confirmación explícita del usuario.

## Security Restrictions

1. **No almacenar credenciales** — El agente nunca guarda, loguea o gestiona contraseñas, cookies o tokens de sesión.
2. **No persistir sesión** — Las cookies viven solo en la sesión del navegador. Al cerrarlo, todo se descarta.
3. **No rellenar login** — El agente nunca interactúa con los campos de email/contraseña.
4. **Audit logging** — Cada publicación exitosa se registra con timestamp.
