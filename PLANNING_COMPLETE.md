# PLANNING COMPLETO — Orquestador Multi-Agente

> **Idioma**: Español  
> **Versión**: Complete (todas las fases)  
> **Incluye**: MVP (Fases 0-6) + Fases avanzadas (7-13)

---

## Visión del Proyecto Completo

Sistema de orquestación multi-agente de producción capaz de:
- Ejecutar tareas complejas en paralelo con hasta N sub-agentes concurrentes
- Catálogo completo de 8 tipos de agentes especializados
- Merge inteligente con resolución automática de conflictos
- Pipeline de validación y testing automático
- Memoria persistente multi-nivel con Engram
- Integración con OpenCode como agente de interfaz adicional
- Observabilidad completa (costes, DAG visual, resumption de checkpoints)

---

## Fases MVP (0-6)

> Ver [PLANNING_MVP.md](./PLANNING_MVP.md) para detalle completo de las Fases 0-6.

| Fase | Descripción | Tiempo |
|------|-------------|--------|
| 0 | Configuración del proyecto | 1 día |
| 1 | Descomponedor de tareas | 2 días |
| 2 | Worktree Manager | 2 días |
| 3 | Sub-Agent Spawner | 2 días |
| 4 | Engram Memory Integration | 2 días |
| 5 | DAG Executor Secuencial | 2 días |
| 6 | Test de Integración E2E | 1 día |

---

## Fase 7: DAG Executor Paralelo

### Descripción
Reemplazar la ejecución secuencial del MVP por ejecución asíncrona paralela.
Las subtareas sin dependencias entre sí se ejecutan al mismo tiempo, respetando
el límite configurable de sub-agentes concurrentes.

### Tareas

- [ ] 7.1 Implementar `AsyncSubAgentSpawner.run_async(task, prior_context)` con `asyncio`
- [ ] 7.2 Modificar `execute_subtask` para lanzar todas las tareas listas en paralelo
- [ ] 7.3 Usar `asyncio.gather()` con semáforo para limitar concurrencia (`MAX_SUBAGENTS`)
- [ ] 7.4 Adaptar `OrchestratorState` para acumular resultados concurrentes de forma segura
- [ ] 7.5 Añadir configuración `MAX_SUBAGENTS` respetada por el ejecutor
- [ ] 7.6 Tests de concurrencia: verificar que tareas independientes corren en paralelo
- [ ] 7.7 Tests de límite: verificar que MAX_SUBAGENTS=2 limita correctamente
- [ ] 7.8 Actualizar `builder.py` con nodo `execute_parallel`
- [ ] 7.9 Medir ganancia de tiempo vs. ejecución secuencial

### Archivos Afectados
- `src/orchestrator/spawner.py` (versión async)
- `src/orchestrator/graph/nodes.py` (nodo paralelo)
- `src/orchestrator/graph/builder.py` (nuevo builder con paralelismo)
- `src/orchestrator/executor.py` (DAGExecutor async)
- `src/orchestrator/config.py` (MAX_SUBAGENTS)

### Criterios de Aceptación
- Dado un DAG con 3 tareas independientes, las 3 corren simultáneamente
- `MAX_SUBAGENTS=2` limita a 2 sub-agentes activos en cualquier momento
- El tiempo total es significativamente menor que la suma de tiempos individuales
- Todos los tests del MVP siguen pasando

### Dependencias
- Fase 5 (DAG Executor) completada

### Tiempo Estimado
**3 días** (12-15 horas)

---

## Fase 8: Catálogo Completo de Agentes

### Descripción
Ampliar el catálogo de sub-agentes de 2 (MVP) a 8 tipos especializados, cada uno
con su propio system prompt detallado, lógica de clasificación, y patrones Engram.

### Tipos de Agentes a Agregar

| Tipo | Descripción |
|------|-------------|
| `code-frontend` | React + TypeScript, hooks, componentes, CSS |
| `code-backend` | Python/Node/Go, APIs REST, bases de datos |
| `docs-agent` | README, docstrings, API docs, changelogs |
| `review-agent` | Code review con checklist CRITICAL/WARNING/SUGGESTION |
| `debug-agent` | Investigación de fallos, root cause analysis |
| `merge-agent` | Resolución de conflictos de merge git |

### Tareas

- [ ] 8.1 Crear `prompts/agents/code_frontend.py` (React + TypeScript, accesibilidad, hooks)
- [ ] 8.2 Crear `prompts/agents/code_backend.py` (Python/Node/Go, seguridad, validación)
- [ ] 8.3 Crear `prompts/agents/docs_agent.py` (Google-style docstrings, README template)
- [ ] 8.4 Crear `prompts/agents/review_agent.py` (checklist OWASP + calidad + tests)
- [ ] 8.5 Crear `prompts/agents/debug_agent.py` (investigación sistemática de bugs)
- [ ] 8.6 Crear `prompts/agents/merge_agent.py` (resolución de conflictos git)
- [ ] 8.7 Actualizar `classifier.py` con reglas keyword para los nuevos tipos
- [ ] 8.8 Actualizar `spawner.py` con el mapa AgentType → SYSTEM_PROMPT completo
- [ ] 8.9 Actualizar `AgentType` enum con todos los tipos
- [ ] 8.10 Tests para clasificación de todos los tipos nuevos

### Archivos Afectados
- `src/orchestrator/prompts/agents/` (6 archivos nuevos/actualizados)
- `src/orchestrator/classifier.py`
- `src/orchestrator/spawner.py`
- `src/orchestrator/models.py`
- `tests/test_classifier.py`

### Criterios de Aceptación
- `AgentClassifier.classify("Create React login form")` → `CODE_FRONTEND`
- `AgentClassifier.classify("Write API documentation")` → `DOCS`
- `AgentClassifier.classify("Debug NullPointerException")` → `DEBUG`
- System prompt de cada agente tiene >500 palabras y es específico

### Dependencias
- Fase 3 (Sub-Agent Spawner) completada

### Tiempo Estimado
**3 días** (12-14 horas)

---

## Fase 9: Smart Merge Coordinator

### Descripción
Reemplazar el merge básico del MVP por un coordinador inteligente que detecta
conflictos, resuelve automáticamente los simples, y escala los complejos.

### Estrategia de Merge

```
Por cada rama a mergear:
    1. Intentar git merge --no-ff
    2. Si no hay conflictos → ÉXITO
    3. Si hay conflictos:
        a. Analizar tipo de conflicto (non-overlapping changes → auto-resolve)
        b. Conflictos en la misma línea → lanzar merge-agent
        c. Conflictos semánticos complejos → escalar al usuario con PR
```

### Tareas

- [ ] 9.1 Implementar detección de conflictos tras `git merge` fallido
- [ ] 9.2 Clasificar conflictos: triviales (whitespace, import order) vs. complejos
- [ ] 9.3 Auto-resolver conflictos triviales con heurísticas
- [ ] 9.4 Para conflictos complejos: lanzar `merge-agent` con el diff como contexto
- [ ] 9.5 Si merge-agent falla: generar instrucciones claras para el usuario
- [ ] 9.6 Implementar `MergeCoordinator.merge_with_conflict_handling()`
- [ ] 9.7 Guardar resultado del merge en Engram (topic_key: `task/{id}-merge`)
- [ ] 9.8 Tests con repositorios de test con conflictos pre-preparados

### Archivos Afectados
- `src/orchestrator/merger.py`
- `src/orchestrator/worktree.py`
- `src/orchestrator/graph/nodes.py` (nodo merge actualizado)
- `tests/test_merger.py` (nuevo)

### Criterios de Aceptación
- Merge sin conflictos → automático y silencioso
- Conflicto trivial (import duplicado) → auto-resuelto sin intervención
- Conflicto complejo → reporte claro al usuario con instrucciones

### Dependencias
- Fase 8 (merge-agent prompt) completada

### Tiempo Estimado
**3 días** (10-12 horas)

---

## Fase 10: Pipeline de Validación Automática

### Descripción
Después de cada merge, ejecutar automáticamente los tests del proyecto.
Si los tests fallan, lanzar un `debug-agent` para investigar y corregir.

### Flujo de Validación

```
merge_results → run_tests
    │
    ├─ PASS → save_memory → END ✅
    │
    └─ FAIL → spawn debug-agent → apply fix → run_tests (retry) → save_memory → END
```

### Tareas

- [ ] 10.1 Detectar el comando de test del proyecto (pytest, npm test, go test, etc.)
- [ ] 10.2 Implementar `ValidationPipeline.run_tests(worktree_path)` → subprocess
- [ ] 10.3 Parsear output de tests: tests pasados, fallidos, errores
- [ ] 10.4 Si hay fallos: crear subtarea `debug-agent` con el traceback como contexto
- [ ] 10.5 Lanzar debug-agent en una rama `fix/post-merge-debug`
- [ ] 10.6 Aplicar fix y re-ejecutar tests (máximo 2 intentos)
- [ ] 10.7 Reportar resultado final al usuario
- [ ] 10.8 Añadir nodo `validate_results` al grafo LangGraph
- [ ] 10.9 Tests: simular fallo de tests y verificar que debug-agent se lanza

### Archivos Afectados
- `src/orchestrator/graph/nodes.py` (nodo validate_results)
- `src/orchestrator/graph/builder.py`
- `src/orchestrator/executor.py`
- `src/orchestrator/validator.py` (nuevo)

### Criterios de Aceptación
- Tras merge exitoso, los tests del proyecto se ejecutan automáticamente
- Si fallan, se lanza debug-agent con el traceback
- El ciclo debug → fix → test se repite máximo 2 veces
- El resultado final indica si los tests pasan o no

### Dependencias
- Fase 8 (debug-agent), Fase 9 (Smart Merge)

### Tiempo Estimado
**3 días** (10-12 horas)

---

## Fase 11: Memoria Avanzada con Engram

### Descripción
Ampliar el uso de Engram a patrones avanzados: memoria a nivel de proyecto,
a nivel personal del desarrollador, sincronización cross-session, y sincronización
con git para compartir memoria entre equipos.

### Niveles de Memoria

| Nivel | Scope | topic_key pattern | Persistencia |
|-------|-------|-------------------|-------------|
| Tarea | Una subtarea específica | `task/{id}-*` | Sesión |
| Proyecto | Todo el proyecto | `project/{name}-context` | Permanente |
| Personal | Preferencias del dev | `personal/{dev}-preferences` | Permanente |
| Sesión | Una ejecución del orquestador | `session/{date}-{slug}` | 30 días |

### Tareas

- [ ] 11.1 Implementar `MemoryManager` como façade sobre `EngramClient`
- [ ] 11.2 Búsqueda contextual inteligente: combinar resultados de múltiples queries
- [ ] 11.3 Implementar `get_project_context(project)` → resumen del estado del proyecto
- [ ] 11.4 Guardar preferencias de arquitectura detectadas en sesiones anteriores
- [ ] 11.5 Implementar `engram sync` para compartir memoria vía git chunks
- [ ] 11.6 Recuperación de contexto tras interrupción: `resume_session(session_id)`
- [ ] 11.7 Límite y rotación de memorias antiguas (configurable: N días)
- [ ] 11.8 Tests con base de datos Engram real (test de integración)

### Archivos Afectados
- `src/orchestrator/memory.py` (ampliar EngramClient)
- `src/orchestrator/graph/nodes.py` (búsqueda contextual mejorada)
- `src/orchestrator/memory_manager.py` (nuevo)

### Criterios de Aceptación
- El orquestador recuerda el stack tecnológico de sesiones anteriores
- `resume_session("session-id")` recupera el estado de una sesión interrumpida
- La memoria del proyecto persiste entre sesiones distintas
- `engram sync` comparte la memoria con el repositorio

### Dependencias
- Fase 4 (Engram Integration básica)

### Tiempo Estimado
**4 días** (14-16 horas)

---

## Fase 12: Integración con OpenCode

### Descripción
Añadir OpenCode como segunda interfaz de agente (además de VS Code Copilot),
implementando un adaptador de plugin y gestión de sesiones para el protocolo OpenCode.

### Tareas

- [ ] 12.1 Investigar API de plugins de OpenCode
- [ ] 12.2 Implementar `OpenCodeAdapter` que recibe tareas del protocolo OpenCode
- [ ] 12.3 Gestión de sesiones: crear/continuar/pausar sesiones OpenCode
- [ ] 12.4 Mapear herramientas del orquestador al Memory Protocol de OpenCode
- [ ] 12.5 Implementar streaming de progreso en tiempo real a OpenCode
- [ ] 12.6 Test de integración: lanzar tarea desde OpenCode y verla completarse
- [ ] 12.7 Documentación de uso con OpenCode

### Archivos Afectados
- `src/orchestrator/adapters/opencode.py` (nuevo)
- `src/orchestrator/main.py` (comando `serve` para OpenCode)
- `docs/OPENCODE_INTEGRATION.md` (nuevo)

### Criterios de Aceptación
- Una tarea lanzada desde OpenCode se ejecuta y reporta resultados en el mismo cliente
- Las memorias de sesiones OpenCode se guardan en Engram con el proyecto correcto
- La integración no rompe la interfaz CLI existente

### Dependencias
- Fase 11 (Memoria Avanzada)

### Tiempo Estimado
**5 días** (20-25 horas)

---

## Fase 13: Observabilidad y Polish

### Descripción
Añadir tracking de costes, visualización del DAG, rate limiting robusto,
resumption desde checkpoints, y pulir la experiencia de usuario.

### Tareas

#### Tracking de Costes
- [ ] 13.1 Interceptar llamadas a Anthropic para capturar tokens input/output
- [ ] 13.2 Calcular coste estimado en USD por subtarea y total
- [ ] 13.3 Mostrar resumen de costes al final de cada ejecución
- [ ] 13.4 Guardar costes en Engram para análisis histórico

#### Visualización del DAG
- [ ] 13.5 Generar visualización ASCII del DAG con estado de cada nodo
- [ ] 13.6 Panel de progreso en tiempo real con `rich.Progress`
- [ ] 13.7 Comando `orchestrator dag show <session-id>` para ver el DAG de una sesión

#### Rate Limiting
- [ ] 13.8 Implementar token bucket para respetar rate limits de la API de Anthropic
- [ ] 13.9 Back-off exponencial con jitter en caso de error 429
- [ ] 13.10 Configuración por modelo (Opus tiene límites distintos a Sonnet)

#### Resumption desde Checkpoint
- [ ] 13.11 Guardar estado del grafo en Engram tras cada nodo completado
- [ ] 13.12 Comando `orchestrator resume <session-id>` para retomar una ejecución interrumpida
- [ ] 13.13 Detectar worktrees huérfanos y ofrecer opción de limpiarlos

#### Polish
- [ ] 13.14 Colores y emojis consistentes en output CLI (rich)
- [ ] 13.15 `--verbose` flag para logs detallados
- [ ] 13.16 `--quiet` flag para output mínimo (solo estado final)
- [ ] 13.17 Mensaje de error amigable cuando Engram no está corriendo
- [ ] 13.18 README actualizado con ejemplos de todos los comandos

### Archivos Afectados
- `src/orchestrator/main.py` (comandos nuevos, flags)
- `src/orchestrator/cost_tracker.py` (nuevo)
- `src/orchestrator/visualizer.py` (nuevo)
- `src/orchestrator/rate_limiter.py` (nuevo)
- `src/orchestrator/checkpoint.py` (nuevo)
- `README.md`

### Criterios de Aceptación
- Al terminar, muestra: `Total cost: $0.42 | Input: 12,450 tokens | Output: 3,200 tokens`
- Visualización ASCII del DAG muestra nodos PENDING/RUNNING/COMPLETED/FAILED con colores
- `orchestrator resume <id>` retoma exactamente donde se quedó
- `orchestrator --quiet run "task"` solo imprime el resumen final

### Dependencias
- Fase 12 (Integración OpenCode)

### Tiempo Estimado
**5 días** (20-25 horas)

---

## Resumen Total del Proyecto Completo

| Fase | Descripción | Días |
|------|-------------|------|
| 0-6 | MVP completo | 12 |
| 7 | DAG Executor Paralelo | 3 |
| 8 | Catálogo Completo de Agentes | 3 |
| 9 | Smart Merge Coordinator | 3 |
| 10 | Pipeline de Validación | 3 |
| 11 | Memoria Avanzada con Engram | 4 |
| 12 | Integración OpenCode | 5 |
| 13 | Observabilidad y Polish | 5 |
| **Total** | | **~38 días** |

---

## Priorización Post-MVP

| Prioridad | Fase | Impacto | Dificultad |
|-----------|------|---------|------------|
| 🔴 Alta | Fase 7 (Paralelismo) | Alto (velocidad) | Media |
| 🔴 Alta | Fase 8 (Catálogo agentes) | Alto (capacidades) | Baja |
| 🟡 Media | Fase 10 (Validación) | Alto (fiabilidad) | Media |
| 🟡 Media | Fase 9 (Smart Merge) | Medio (robustez) | Alta |
| 🟢 Baja | Fase 11 (Memoria avanzada) | Medio (UX) | Media |
| 🟢 Baja | Fase 12 (OpenCode) | Bajo (integraciones) | Alta |
| 🟢 Baja | Fase 13 (Observabilidad) | Medio (UX) | Media |
