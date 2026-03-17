# PLANNING MVP — Orquestador Multi-Agente

> **Idioma**: Español  
> **Versión**: MVP (Minimum Viable Product)  
> **Objetivo**: Sistema funcional de extremo a extremo con ejecución secuencial

---

## Alcance del MVP

El MVP entrega un sistema orquestador capaz de:

1. Recibir una tarea de alto nivel por CLI
2. Descomponerla en 2-6 subtareas con dependencias
3. Crear 2 tipos de sub-agentes: `code-agent` (genérico) y `test-agent`
4. Ejecutar subtareas **secuencialmente** (sin paralelismo)
5. Cada sub-agente trabaja en su propio **git worktree** aislado
6. Integración con **Engram** para memoria persistente (guardar + buscar)
7. Los sub-agentes reportan solo **resúmenes compactos** al orquestador
8. **Merge básico** de worktrees al finalizar
9. **Manejo de errores**: 1 reintento automático
10. Interfaz **CLI** con typer + rich

---

## No-Goals del MVP (diferidos a Complete)

- Ejecución paralela de sub-agentes (Phase 7)
- Catálogo completo de 7 tipos de agentes (Phase 8)
- Merge inteligente con resolución de conflictos (Phase 9)
- Pipeline de validación automática post-merge (Phase 10)
- Memoria avanzada multi-nivel en Engram (Phase 11)
- Integración con OpenCode (Phase 12)
- Observabilidad, tracking de costes, visualización DAG (Phase 13)

---

## Entregables del MVP

| Entregable | Descripción |
|-----------|-------------|
| CLI funcional | `python -m orchestrator run "<tarea>"` funciona end-to-end |
| Descomponedor | Genera DAG de subtareas desde descripción libre |
| Worktree Manager | Crea, lista y elimina git worktrees |
| Sub-agente spawner | Ejecuta sub-agentes en su worktree asignado |
| Engram client | Guarda y busca memorias vía HTTP API |
| DAG Executor | Ejecuta subtareas en orden de dependencias |
| Merge Coordinator | Merge básico de ramas al finalizar |
| Tests unitarios | Cobertura de módulos core: decomposer, classifier, worktree, memory |

---

## Fases del MVP

---

### Fase 0: Configuración del Proyecto (Día 1)

#### Descripción
Establecer la estructura del repositorio, dependencias, y verificar que el entorno
de desarrollo esté listo. Engram debe estar instalado y accesible.

#### Tareas

- [ ] 0.1 Crear estructura de directorios (`src/orchestrator/`, `tests/`, `docs/`)
- [ ] 0.2 Crear `pyproject.toml` con todas las dependencias (langgraph, anthropic, pydantic, httpx, typer, rich, gitpython, python-dotenv)
- [ ] 0.3 Crear `.env.example` con las variables requeridas
- [ ] 0.4 Crear `.gitignore` apropiado (Python + Engram + worktrees)
- [ ] 0.5 Instalar Engram y verificar que responde en `localhost:7437`
  ```bash
  engram serve &
  curl http://localhost:7437/stats
  ```
- [ ] 0.6 Crear `src/orchestrator/config.py` con constantes de configuración
- [ ] 0.7 Crear `src/orchestrator/models.py` con modelos Pydantic (SubTask, TaskDAG, AgentResult, enums)
- [ ] 0.8 Crear esqueleto básico de `main.py` con typer
- [ ] 0.9 Verificar: `python -m orchestrator --help` funciona

#### Archivos Afectados
- `pyproject.toml`
- `.env.example`
- `.gitignore`
- `src/orchestrator/__init__.py`
- `src/orchestrator/config.py`
- `src/orchestrator/models.py`
- `src/orchestrator/main.py`

#### Criterios de Aceptación
- `python -m orchestrator --help` imprime la ayuda sin errores
- `pip install -e ".[dev]"` instala todas las dependencias
- `curl http://localhost:7437/stats` responde con JSON

#### Tiempo Estimado
**1 día** (4-6 horas)

---

### Fase 1: Descomponedor de Tareas (Días 2-3)

#### Descripción
Implementar el módulo que envía una descripción de tarea a Claude Opus y recibe
una lista estructurada de subtareas con dependencias.

#### Tareas

- [ ] 1.1 Implementar `TaskDecomposer.decompose(task_description)` en `decomposer.py`
- [ ] 1.2 Diseñar el system prompt para descomposición (instrucciones, formato JSON, reglas)
- [ ] 1.3 Implementar parsing robusto de respuesta JSON (strip markdown fences, manejo de errores)
- [ ] 1.4 Asignar `branch_name` automático a cada subtarea
- [ ] 1.5 Implementar `TaskDAG.get_ready_tasks(completed_ids)` — método auxiliar
- [ ] 1.6 Implementar `TaskDAG.is_complete()` — método auxiliar
- [ ] 1.7 Escribir tests en `tests/test_decomposer.py` (mock del cliente Anthropic)
- [ ] 1.8 Comando CLI `orchestrator run --dry-run "tarea"` muestra el DAG sin ejecutar

#### Archivos Afectados
- `src/orchestrator/decomposer.py`
- `src/orchestrator/models.py` (métodos auxiliares en TaskDAG)
- `src/orchestrator/main.py` (flag --dry-run)
- `tests/test_decomposer.py`

#### Criterios de Aceptación
Dado "Add login page with tests", el descomponedor devuelve:
- ≥2 subtareas
- Una subtarea de tipo `code-*` sin dependencias
- Una subtarea de tipo `test-agent` que depende de la de código
- Cada subtarea tiene `id`, `title`, `description`, `type`, `depends_on`

```bash
python -m orchestrator run --dry-run "Add login page with tests"
# Muestra tabla con ≥2 subtareas y sus dependencias
```

#### Tiempo Estimado
**2 días** (8-10 horas)

---

### Fase 2: Worktree Manager (Días 3-4)

#### Descripción
Implementar el gestor de git worktrees para crear entornos de trabajo aislados
por sub-agente.

#### Tareas

- [ ] 2.1 Implementar `WorktreeManager.__init__` (repo path + base_dir configurable)
- [ ] 2.2 Implementar `create_worktree(task_id, branch_name)` → crea directorio + rama
- [ ] 2.3 Implementar `remove_worktree(task_id, force=True)` → limpieza segura
- [ ] 2.4 Implementar `list_worktrees()` → parsea salida porcelain de git
- [ ] 2.5 Implementar `merge_branch(source_branch, target="main")` → merge con --no-ff
- [ ] 2.6 Implementar `cleanup_all()` → elimina todos los worktrees del base_dir
- [ ] 2.7 Manejo de errores: worktree ya existe → reutilizar; error de git → prune + fallback
- [ ] 2.8 Escribir tests en `tests/test_worktree.py` (mock de git.Repo)

#### Archivos Afectados
- `src/orchestrator/worktree.py`
- `tests/test_worktree.py`

#### Criterios de Aceptación
```python
mgr = WorktreeManager()
path = mgr.create_worktree("task-1", "feature/task-1")
assert Path(path).exists()
# Crear un archivo en el worktree
(Path(path) / "test.txt").write_text("hello")
mgr.remove_worktree("task-1")
assert not Path(path).exists()
```

#### Tiempo Estimado
**2 días** (6-8 horas)

---

### Fase 3: Sub-Agent Spawner (Días 4-5)

#### Descripción
Implementar el spawner que crea un sub-agente con su prompt especializado,
lo ejecuta en el worktree asignado, y recoge el resumen compacto.

#### Tareas

- [ ] 3.1 Implementar `SubAgentSpawner.run(task, prior_context)` usando Claude Sonnet
- [ ] 3.2 Crear system prompts para `code-generic` y `test-agent` en `prompts/agents/`
- [ ] 3.3 Implementar `_parse_result` — extrae JSON del resultado del LLM
- [ ] 3.4 Implementar `_save_to_memory` — guarda resultado en Engram
- [ ] 3.5 Construir user message con: task info + worktree path + prior context
- [ ] 3.6 Instrucciones de respuesta formato JSON en el user message
- [ ] 3.7 `CompactReporter.format_summary()` — formatea AgentResult para display
- [ ] 3.8 `CompactReporter.format_engram_content()` — Markdown para Engram

#### Archivos Afectados
- `src/orchestrator/spawner.py`
- `src/orchestrator/reporter.py`
- `src/orchestrator/prompts/agents/code_backend.py`
- `src/orchestrator/prompts/agents/test_agent.py`
- `src/orchestrator/prompts/orchestrator.py`

#### Criterios de Aceptación
```python
task = SubTask(id="task-1", title="Create utils.py", ...)
result = spawner.run(task)
assert result.task_id == "task-1"
assert result.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
assert len(result.summary) > 10
```

#### Tiempo Estimado
**2 días** (8-10 horas)

---

### Fase 4: Integración con Engram Memory (Días 5-6)

#### Descripción
Implementar el cliente HTTP para Engram y conectarlo al flujo del orquestador.

#### Tareas

- [ ] 4.1 Implementar `EngramClient.search(query, limit)` → GET /search
- [ ] 4.2 Implementar `EngramClient.save_observation(title, type, content, topic_key, project)` → POST /observations
- [ ] 4.3 Implementar `EngramClient.get_context(project)` → GET /context
- [ ] 4.4 Implementar `EngramClient.session_start(session_id, project, directory)` → POST /sessions
- [ ] 4.5 Implementar `EngramClient.session_end(session_id, summary)` → POST /sessions/{id}/end
- [ ] 4.6 Implementar `EngramClient.get_stats()` → GET /stats
- [ ] 4.7 Manejo de errores: todas las llamadas tienen try/except con graceful degradation
- [ ] 4.8 Integrar `mem_search` antes de ejecutar cada subtarea (en spawner.py)
- [ ] 4.9 Integrar `mem_save` después de completar cada subtarea (en spawner.py)
- [ ] 4.10 Integrar `session_summary` al final de la ejecución completa (en nodes.py)
- [ ] 4.11 Escribir tests en `tests/test_memory.py` (mock de httpx.Client)

#### Archivos Afectados
- `src/orchestrator/memory.py`
- `src/orchestrator/spawner.py` (integración)
- `src/orchestrator/graph/nodes.py` (save_memory node)
- `tests/test_memory.py`

#### Criterios de Aceptación
Con Engram corriendo en localhost:7437:
```bash
python -m orchestrator memory stats
# Muestra estadísticas de Engram

python -m orchestrator memory search "JWT auth"
# Muestra resultados (o "No results found" si no hay)
```
Tras ejecutar una tarea completa:
```bash
curl http://localhost:7437/search?q=task-1
# Devuelve la observación guardada por el sub-agente
```

#### Tiempo Estimado
**2 días** (6-8 horas)

---

### Fase 5: DAG Executor Secuencial (Días 6-7)

#### Descripción
Implementar el ejecutor de grafo usando LangGraph que orquesta la ejecución
de subtareas en orden de dependencias, con manejo de errores y merge final.

#### Tareas

- [ ] 5.1 Definir `OrchestratorState` TypedDict en `graph/state.py`
- [ ] 5.2 Implementar nodo `decompose_task` en `graph/nodes.py`
- [ ] 5.3 Implementar nodo `classify_agents` (validación/override de tipos)
- [ ] 5.4 Implementar nodo `create_worktrees` (crea worktrees para todo el DAG)
- [ ] 5.5 Implementar nodo `execute_subtask` (ejecuta la primera tarea lista del DAG)
- [ ] 5.6 Implementar función de routing `_should_continue_executing`
- [ ] 5.7 Implementar nodo `collect_results`
- [ ] 5.8 Implementar nodo `merge_results` (llama a MergeCoordinator)
- [ ] 5.9 Implementar nodo `save_memory` (resumen de sesión en Engram)
- [ ] 5.10 Implementar `build_orchestrator_graph()` en `graph/builder.py`
- [ ] 5.11 Implementar `DAGExecutor.run(dag)` en `executor.py`
- [ ] 5.12 Implementar `with_retry(fn, task, max_retries)` en `errors.py`
- [ ] 5.13 Implementar `make_failed_result(task, error)` en `errors.py`
- [ ] 5.14 Integrar en `main.py`: comando `run` usa DAGExecutor

#### Archivos Afectados
- `src/orchestrator/graph/state.py`
- `src/orchestrator/graph/nodes.py`
- `src/orchestrator/graph/builder.py`
- `src/orchestrator/executor.py`
- `src/orchestrator/errors.py`
- `src/orchestrator/main.py`

#### Criterios de Aceptación
Flujo end-to-end funcional:
```bash
GITHUB_TOKEN=ghp_... python -m orchestrator run "Create a Python utility with tests"
# Descompone en subtareas
# Ejecuta cada subtarea en orden
# Muestra tabla de resultados
# Hace merge al finalizar
```

#### Tiempo Estimado
**2 días** (10-12 horas)

---

### Fase 6: Test de Integración (Día 8)

#### Descripción
Test end-to-end del sistema completo con una tarea real. Identificar y corregir
casos borde descubiertos durante el test.

#### Tareas

- [ ] 6.1 Ejecutar test E2E: `"Create a React component with tests"` con API key real
- [ ] 6.2 Verificar que el DAG se descompone correctamente
- [ ] 6.3 Verificar que los worktrees se crean y eliminan limpiamente
- [ ] 6.4 Verificar que Engram guarda y recupera memorias
- [ ] 6.5 Verificar que el merge final funciona sin conflictos
- [ ] 6.6 Medir tiempo total de ejecución y coste estimado de tokens
- [ ] 6.7 Corregir casos borde identificados
- [ ] 6.8 Ejecutar suite de tests unitarios: `pytest tests/ -v`
- [ ] 6.9 Verificar que todos los tests pasan

#### Archivos Afectados
- Cualquier módulo con bugs identificados
- `tests/` — tests adicionales para casos borde

#### Criterios de Aceptación
- `pytest tests/ -v` — todos los tests pasan
- El flujo E2E completo funciona sin errores
- Los worktrees se limpian correctamente tras la ejecución
- Las memorias están guardadas en Engram tras la ejecución

#### Tiempo Estimado
**1 día** (6-8 horas)

---

## Resumen de Tiempo Total del MVP

| Fase | Descripción | Días |
|------|-------------|------|
| 0 | Configuración del proyecto | 1 |
| 1 | Descomponedor de tareas | 2 |
| 2 | Worktree Manager | 2 |
| 3 | Sub-Agent Spawner | 2 |
| 4 | Engram Memory | 2 |
| 5 | DAG Executor | 2 |
| 6 | Test de integración | 1 |
| **Total** | | **~8 días** |

---

## Prerequisitos del MVP

- Python 3.12+
- Git 2.30+ (soporte de worktrees)
- Engram instalado y corriendo (`engram serve`)
- API key de Anthropic
- VS Code con extensión GitHub Copilot (para desarrollo asistido)
