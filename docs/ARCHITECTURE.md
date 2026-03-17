# Arquitectura del Orquestador Multi-Agente

## Visión General del Sistema

El Orquestador Multi-Agente es un sistema de IA capaz de recibir una tarea de alto nivel,
descomponerla en subtareas especializadas, y coordinar agentes independientes para ejecutarlas
en paralelo usando git worktrees aislados, con memoria persistente a través de Engram.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          USUARIO (CLI / IDE)                               │
│              python -m orchestrator run "Implementar auth JWT"             │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      AGENTE ORQUESTADOR                                    │
│                    (Claude Opus 4 — Opus)                                  │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐ │
│  │ Decomposer   │  │ Classifier   │  │ DAGExecutor   │  │  Merger      │ │
│  │ (LLM→DAG)    │→ │ (tipo agente)│→ │ (LangGraph)   │→ │  (merge+     │ │
│  └──────────────┘  └──────────────┘  └───────┬───────┘  │  cleanup)    │ │
│                                              │           └──────────────┘ │
└──────────────────────────────────────────────┼────────────────────────────┘
                                               │ Spawner (por subtarea)
                    ┌──────────────────────────┼──────────────────────┐
                    │                          │                       │
                    ▼                          ▼                       ▼
          ┌─────────────────┐      ┌───────────────────┐   ┌──────────────────┐
          │  code-frontend  │      │   test-agent      │   │   docs-agent     │
          │  (Claude Sonnet)│      │  (Claude Sonnet)  │   │  (Claude Sonnet) │
          │  wt/task-1-code │      │  wt/task-2-test   │   │  wt/task-3-docs  │
          └────────┬────────┘      └─────────┬─────────┘   └────────┬─────────┘
                   │                         │                       │
                   └──────────────┬──────────┘                       │
                                  │          ┌────────────────────────┘
                                  ▼          ▼
                    ┌─────────────────────────────────────────────┐
                    │            ENGRAM (HTTP :7437)              │
                    │   SQLite + FTS5 — Memoria compartida        │
                    │   ~/.engram/engram.db                       │
                    └─────────────────────────────────────────────┘
```

---

## Flujo de Interacción entre Componentes

```
Usuario
  │
  │  1. "Implementar auth JWT con tests y docs"
  ▼
main.py (CLI typer)
  │
  │  2. decompose(task_description)
  ▼
decomposer.py → Claude Opus → TaskDAG
  │
  │  3. classify_agents(dag)
  ▼
classifier.py → verifica/asigna AgentType por subtarea
  │
  │  4. create_worktrees(dag)
  ▼
worktree.py → git worktree add para cada subtarea
  │
  │  5. Bucle: execute_subtask(next_ready_task)
  ▼
spawner.py → sub-agente Claude Sonnet en su worktree
     │
     │  5a. mem_search(task.title) — contexto previo
     │  5b. Ejecuta la tarea
     │  5c. mem_save(resultado) — guarda en Engram
     │  5d. Devuelve AgentResult compacto
  │
  │  6. Repite hasta que DAG.is_complete()
  │
  │  7. merge_results → git merge cada rama → cleanup
  │
  │  8. save_memory → sesión completa guardada en Engram
  ▼
Usuario recibe tabla resumen
```

---

## Modelos de Datos

### SubTask
```
SubTask
├── id: str                  # "task-1-auth-code"
├── title: str               # "Implementar middleware JWT"
├── description: str         # descripción detallada
├── type: AgentType          # code-backend, test-agent, etc.
├── depends_on: List[str]    # IDs de subtareas previas
├── status: TaskStatus       # PENDING → RUNNING → COMPLETED/FAILED
├── branch_name: str         # "feature/task-1-auth-code"
├── worktree_path: str       # "/home/user/.worktrees/task-1-auth-code"
└── retry_count: int         # número de intentos
```

### TaskDAG
```
TaskDAG
├── original_task: str       # descripción original del usuario
├── subtasks: List[SubTask]  # grafo completo de tareas
└── created_at: datetime
```

### AgentResult (resumen compacto)
```
AgentResult
├── task_id: str
├── status: TaskStatus
├── summary: str             # párrafo de lo que se hizo
├── files_changed: List[str] # rutas relativas
├── branch: str
└── errors: Optional[str]
```

---

## Integración con Engram

Engram actúa como la **memoria compartida** del sistema. Hay tres patrones de uso:

### 1. Búsqueda de Contexto Previo (antes de ejecutar)
```python
# El orquestador busca trabajo previo relacionado
prior = memory.search(task.title, limit=3)
```

### 2. Guardar Resultado (al terminar cada subtarea)
```python
# El sub-agente guarda su resultado
memory.save_observation(
    title=f"[{task_id}] {task_title}",
    type="progress",
    content=markdown_result,
    topic_key=f"task/{task_id}",
    project="mi-proyecto",
)
```

### 3. Resumen de Sesión (al final)
```python
# El orquestador guarda el resumen completo
memory.save_observation(
    title="Session summary: ...",
    type="session",
    content="## Goal\n...\n## Accomplished\n...\n## Next Steps\n...",
    topic_key="session/...",
    project="mi-proyecto",
)
```

**Patrón topic_key:**
| Tipo          | topic_key                          |
|---------------|------------------------------------|
| Implementación | `task/{id}-implementation`        |
| Tests         | `task/{id}-testing`               |
| Documentación | `task/{id}-documentation`         |
| Review        | `task/{id}-review`                |
| Sesión        | `session/{fecha}-{slug-tarea}`    |

---

## Ciclo de Vida del Git Worktree

```
1. CREACIÓN
   git worktree add ../.worktrees/task-1-auth-code feature/task-1-auth-code
   → Crea rama nueva + directorio aislado

2. TRABAJO DEL SUB-AGENTE
   cd ../.worktrees/task-1-auth-code
   → Escribe archivos, hace commits locales

3. MERGE AL COMPLETAR
   git checkout main
   git merge feature/task-1-auth-code --no-ff

4. LIMPIEZA
   git worktree remove ../.worktrees/task-1-auth-code
   git branch -d feature/task-1-auth-code
```

**Reglas de naming de ramas:**
- Código: `feature/task-{id}-code`
- Tests: `feature/task-{id}-test`
- Docs: `feature/task-{id}-docs`
- Review: `feature/task-{id}-review`
- Fix: `fix/task-{id}-debug`

---

## Estrategias de Manejo de Errores

| Escenario | Estrategia |
|-----------|-----------|
| Sub-agente falla | 1 reintento con back-off exponencial |
| Dependencia fallida | Marcar subtareas dependientes como SKIPPED |
| Conflicto de merge | Log + continuar sin esa rama; reportar al usuario |
| Engram no disponible | Continuar sin memoria (degradado graceful) |
| LLM no responde | Timeout + MaxRetriesExceededError |
| Worktree ya existe | Reutilizar el directorio existente |

---

## Selección de Modelos LLM

| Componente | Modelo | Razón |
|------------|--------|-------|
| Orquestador (decomposición, planificación) | Claude Opus 4 | Mayor razonamiento, mejor para DAGs complejos |
| Sub-agentes (implementación, tests, docs) | Claude Sonnet 4 | Mayor velocidad, menor coste, suficiente para tareas concretas |
| Clasificador (fallback LLM) | Claude Opus 4 | Mismo cliente, precisión importante |

---

## Consideraciones de Seguridad

1. **Secretos**: El `GITHUB_TOKEN` se lee solo de variables de entorno (`.env`). Nunca se hardcodea. En entornos Copilot está disponible automáticamente; en desarrollo local se usa un PAT con permiso *Models: read*.
2. **Worktrees aislados**: Los sub-agentes solo pueden escribir en su propio worktree, no en `main`.
3. **Validación de inputs**: El descomponedor valida que el JSON de respuesta sea parseable antes de crear el DAG.
4. **Sin ejecución de código arbitrario**: Los sub-agentes generan código pero no lo ejecutan en el host. (TODO: sandbox para Phase 10)
5. **Límites de tokens**: Cada sub-agente tiene un `max_tokens=4096` para evitar facturas inesperadas.
6. **Rate limiting**: `MAX_SUBAGENTS=2` limita la concurrencia (configurable por env var).

---

## Estado LangGraph

```
OrchestratorState (TypedDict)
├── task_description: str       # tarea original
├── dag: Optional[TaskDAG]      # grafo descompuesto
├── results: List[AgentResult]  # resultados acumulados
├── completed_task_ids: Set[str] # IDs terminadas
├── project: str                # proyecto Engram
└── error: Optional[str]        # error del último nodo
```

El grafo compila los nodos:
```
decompose → classify → create_worktrees → execute (loop) → collect → merge → save_memory → END
```
