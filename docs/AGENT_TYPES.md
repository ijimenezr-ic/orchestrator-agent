# Catálogo de Tipos de Sub-Agentes

## Tabla Resumen

| Tipo              | Especialización                       | Modelo       | Cuándo se activa                          |
|-------------------|---------------------------------------|--------------|-------------------------------------------|
| `code-frontend`   | React, TypeScript, UI components      | Claude Sonnet | Tareas de UI, componentes, CSS, hooks    |
| `code-backend`    | Python, Node, Go, APIs, BD            | Claude Sonnet | APIs REST, modelos BD, servicios backend |
| `code-generic`    | Implementación general, scripts       | Claude Sonnet | Código que no encaja en frontend/backend |
| `test-agent`      | Tests unitarios, integración, e2e     | Claude Sonnet | Siempre después de tareas de código      |
| `docs-agent`      | README, docstrings, API docs          | Claude Sonnet | Después de implementación               |
| `review-agent`    | Revisión de código, calidad           | Claude Sonnet | Última fase, antes de merge final        |
| `debug-agent`     | Investigar fallos, corregir bugs      | Claude Sonnet | Cuando una tarea falla tras reintentos   |
| `merge-agent`     | Resolver conflictos de merge          | Claude Sonnet | Cuando git merge falla automáticamente   |

---

## Descripción Detallada por Tipo

---

### `code-frontend`

**Especialización**: Desarrollo de interfaces de usuario con React y TypeScript.

**Activación**: Se asigna cuando la descripción de la subtarea contiene palabras clave como:
`react`, `tsx`, `frontend`, `ui`, `component`, `css`, `html`, `vue`, `svelte`

**Prompt strategy**: El agente es un senior frontend engineer con acceso al worktree.
Prioriza: TypeScript estricto, hooks modernos, componentes funcionales, accesibilidad,
manejo de estados de carga/error, CSS Modules o Tailwind.

**Engram topic_key pattern**: `task/{id}-frontend`

**Naming de rama**: `feature/{task-id}-code`

**Inputs esperados**:
- Descripción de la UI a implementar
- Contexto del stack existente (si hay)
- Ruta del worktree asignado

**Outputs esperados**:
- Archivos `.tsx`, `.ts`, `.css` creados/modificados
- Resumen compacto con decisiones de diseño clave

---

### `code-backend`

**Especialización**: APIs REST/GraphQL, servicios de negocio, bases de datos.

**Activación**: Palabras clave: `api`, `backend`, `server`, `django`, `fastapi`, `flask`,
`express`, `node`, `database`, `sql`, `orm`

**Prompt strategy**: Senior backend engineer con foco en: validación de inputs,
seguridad (no SQL injection, no secretos hardcodeados), manejo de errores explícito,
logging, documentación de endpoints.

**Engram topic_key pattern**: `task/{id}-backend`

**Naming de rama**: `feature/{task-id}-code`

**Checklist de seguridad aplicado**: SQL injection, validación de inputs, auth checks,
rate limiting awareness, env vars para secrets.

---

### `code-generic`

**Especialización**: Código que no encaja claramente en frontend o backend. Scripts,
utilidades, configuración, herramientas de build.

**Activación**: Fallback cuando ningún keyword específico aplica.

**Engram topic_key pattern**: `task/{id}-code`

**Naming de rama**: `feature/{task-id}-code`

---

### `test-agent`

**Especialización**: Testing en todas sus formas — unitario, integración, e2e.

**Activación**: Palabras clave: `test`, `spec`, `pytest`, `jest`, `coverage`,
`unit`, `integration`, `e2e`

**Prompt strategy**: QA engineer especializado. Prioriza: cobertura de rutas críticas,
casos borde, paths de error, tests herméticamente aislados (mocks para externos),
patrón AAA (Arrange-Act-Assert).

**Dependencias típicas**: Siempre depende de una subtarea `code-*`.

**Engram topic_key pattern**: `task/{id}-testing`

**Naming de rama**: `feature/{task-id}-test`

**Convenciones de naming**:
```
Python: test_<behavior>_<expected_outcome>.py
JS/TS:  <ComponentName>.test.tsx / <module>.spec.ts
```

---

### `docs-agent`

**Especialización**: Documentación técnica en todas sus formas.

**Activación**: Palabras clave: `doc`, `readme`, `documentation`, `docstring`,
`comment`, `wiki`, `mkdocs`

**Prompt strategy**: Technical writer con acceso al código. Genera:
README.md con quick start, docstrings Google-style para Python o JSDoc para JS/TS,
documentación de API, diagramas ASCII, entradas de CHANGELOG.

**Dependencias típicas**: Depende de la subtarea de código correspondiente.

**Engram topic_key pattern**: `task/{id}-docs`

**Naming de rama**: `feature/{task-id}-docs`

---

### `review-agent`

**Especialización**: Revisión de código con foco en correctness, seguridad y mantenibilidad.

**Activación**: Palabras clave: `review`, `audit`, `quality`, `lint`, `sonar`

**Prompt strategy**: Senior reviewer con checklist estructurado:
CRITICAL (bloqueante) / WARNING (recomendado) / SUGGESTION (nice-to-have).
Verifica: lógica, seguridad (OWASP), rendimiento, cobertura de tests, calidad.

**Dependencias típicas**: Depende de tests y docs. Es la última subtarea del DAG.

**Engram topic_key pattern**: `task/{id}-review`

**Naming de rama**: No crea rama propia; lee de las ramas de otros agentes.

---

### `debug-agent`

**Especialización**: Investigar y corregir fallos.

**Activación**:
1. Palabras clave: `debug`, `fix`, `bug`, `error`, `traceback`, `issue`
2. Automáticamente cuando un sub-agente falla tras el número máximo de reintentos

**Prompt strategy**: Debugger metódico. Lee el error, localiza la causa raíz,
propone y aplica la corrección mínima necesaria. Documenta la causa en Engram.

**Engram topic_key pattern**: `bug/{id}-investigation`

**Naming de rama**: `fix/{task-id}-debug`

---

### `merge-agent`

**Especialización**: Resolver conflictos de merge entre worktrees.

**Activación**: Automáticamente cuando `git merge` falla con conflictos.

**Prompt strategy**: Analiza los conflictos de merge (`<<<<`, `====`, `>>>>`),
entiende el contexto de ambas versiones, resuelve preservando la intención de ambas
ramas cuando es posible, escala al usuario cuando el conflicto es semántico.

**Engram topic_key pattern**: `task/{id}-merge`

**Naming de rama**: Opera directamente en `main`.

---

## Reglas de Dependencia entre Tipos

```
código (frontend/backend/generic)
    ↓ siempre antes de
tests (test-agent)
    ↓ preferiblemente antes de
docs (docs-agent)
    ↓ ambos antes de
review (review-agent)  ← última en el DAG
```

**Excepciones**:
- `debug-agent` puede insertarse en cualquier punto del DAG cuando hay un fallo.
- `merge-agent` opera fuera del DAG principal, durante la fase de consolidación.
- `docs-agent` puede correr en paralelo con `test-agent` si comparten solo dependencia en el código.

---

## Patrones de topic_key en Engram

| Situación                     | topic_key                        |
|-------------------------------|----------------------------------|
| Implementación de código      | `task/{id}-implementation`       |
| Testing de una tarea          | `task/{id}-testing`              |
| Documentación                 | `task/{id}-documentation`        |
| Review de código              | `task/{id}-review`               |
| Investigación de bug          | `bug/{id}-investigation`         |
| Integración/merge             | `task/{id}-integration`          |
| Resumen de sesión             | `session/{date}-{task-slug}`     |
| Contexto de proyecto          | `project/{name}-context`         |

---

## Convenciones de Naming de Ramas

| Tipo de agente | Patrón de rama                  | Ejemplo                          |
|----------------|---------------------------------|----------------------------------|
| code-frontend  | `feature/{task-id}-code`        | `feature/task-1-auth-code`       |
| code-backend   | `feature/{task-id}-code`        | `feature/task-2-api-code`        |
| code-generic   | `feature/{task-id}-code`        | `feature/task-3-config-code`     |
| test-agent     | `feature/{task-id}-test`        | `feature/task-4-auth-test`       |
| docs-agent     | `feature/{task-id}-docs`        | `feature/task-5-auth-docs`       |
| review-agent   | *(no crea rama)*                | —                                |
| debug-agent    | `fix/{task-id}-debug`           | `fix/task-2-api-debug`           |
| merge-agent    | `main` *(directamente)*         | —                                |
