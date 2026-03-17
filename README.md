# Orchestrator Agent

Sistema de orquestación multi-agente que descompone tareas complejas en subtareas
especializadas, coordina sub-agentes con IA, y gestiona ramas git aisladas (worktrees)
con memoria persistente a través de [Engram](https://github.com/Gentleman-Programming/engram).

---

## Arquitectura

```
┌──────────────────────────────────────────────────────────────┐
│                    AGENTE ORQUESTADOR                        │
│               (Claude Opus 4 — planificación)                │
│  Decomposer → Classifier → DAGExecutor → Merger             │
└────────────────────────┬─────────────────────────────────────┘
                         │ Crea sub-agentes por subtarea
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
  │ code-frontend│ │  test-agent  │ │  docs-agent  │
  │ (Claude      │ │ (Claude      │ │ (Claude      │
  │  Sonnet)     │ │  Sonnet)     │ │  Sonnet)     │
  │ wt/task-1    │ │ wt/task-2    │ │ wt/task-3    │
  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
         │                │                │
         └────────────────┼────────────────┘
                          ▼
          ┌───────────────────────────────┐
          │      ENGRAM (HTTP :7437)      │
          │   Memoria compartida entre    │
          │   agentes — SQLite + FTS5     │
          └───────────────────────────────┘
```

---

## Características

- **Descomposición automática**: Claude Opus 4 divide cualquier tarea en un DAG de subtareas
- **Sub-agentes especializados**: 8 tipos (frontend, backend, test, docs, review, debug, merge, generic)
- **Git worktrees aislados**: Cada sub-agente trabaja en su propia rama sin contaminar `main`
- **Memoria persistente**: Engram guarda resúmenes de sesiones, resultados y contexto de proyecto
- **Contexto compacto**: Los sub-agentes solo reportan resúmenes — el contexto del orquestador no se llena
- **Manejo de errores**: Reintentos automáticos con back-off exponencial
- **CLI rica**: typer + rich para una experiencia de usuario cómoda

---

## Prerequisitos

- **GitHub Copilot** subscription (provides access to Claude models via [GitHub Models](https://github.com/marketplace/models))
- **Python** 3.12+
- **Git** 2.30+ (soporte nativo de worktrees)
- **Engram** instalado y corriendo (ver [instalación](#engram))
- **GitHub token** `GITHUB_TOKEN` — disponible automáticamente con GitHub Copilot; para uso local crea un PAT con permiso *Models: read* en <https://github.com/settings/personal-access-tokens/new>

---

## Instalación Rápida

```bash
# 1. Clonar el repositorio
git clone https://github.com/ijimenezr-ic/orchestrator-agent.git
cd orchestrator-agent

# 2. Crear entorno virtual e instalar dependencias
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

pip install -e ".[dev]"

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env y añadir GITHUB_TOKEN
# (En entornos GitHub Copilot esta variable ya está disponible automáticamente)
# Para desarrollo local, crea un token en https://github.com/settings/personal-access-tokens/new
# con permiso "Models: read"
```

### Engram

```bash
# Instalar Engram (Go necesario)
go install github.com/Gentleman-Programming/engram@latest

# Iniciar el servidor de memoria
engram serve &

# Verificar que responde
curl http://localhost:7437/stats
```

---

## Uso

### Ejecutar una tarea

```bash
# Ejecutar tarea completa (descomponer + ejecutar + merge)
python -m orchestrator run "Implementar autenticación JWT con tests y documentación"

# Solo descomponer (sin ejecutar sub-agentes)
python -m orchestrator run --dry-run "Create a React dashboard component"

# Especificar proyecto Engram
python -m orchestrator run "Add login page" --project mi-proyecto
```

### Verificar estado

```bash
python -m orchestrator status
```

### Interactuar con la memoria (Engram)

```bash
# Buscar memorias
python -m orchestrator memory search "JWT auth"

# Ver estadísticas
python -m orchestrator memory stats
```

---

## Configuración

| Variable | Default | Descripción |
|----------|---------|-------------|
| `GITHUB_TOKEN` | — | Requerido. Token de GitHub (disponible automáticamente en entornos Copilot; para uso local crea un PAT con permiso *Models: read*) |
| `GITHUB_MODELS_URL` | `https://models.inference.ai.azure.com` | Endpoint de GitHub Models API |
| `ORCHESTRATOR_MODEL` | `claude-opus-4-5` | ID del modelo orquestador en el [catálogo de GitHub Models](https://github.com/marketplace/models) |
| `SUBAGENT_MODEL` | `claude-sonnet-4-5` | ID del modelo para los sub-agentes |
| `ENGRAM_URL` | `http://localhost:7437` | URL del servidor Engram |
| `MAX_RETRIES` | `1` | Reintentos por subtarea en caso de fallo |
| `MAX_SUBAGENTS` | `2` | Máximo de sub-agentes concurrentes |
| `TASK_TIMEOUT` | `300` | Timeout por subtarea (segundos) |
| `WORKTREE_BASE_DIR` | `../.worktrees` | Directorio base para git worktrees |

---

## Estructura del Proyecto

```
orchestrator-agent/
├── src/orchestrator/
│   ├── main.py            # CLI (typer + rich)
│   ├── config.py          # Configuración
│   ├── models.py          # Pydantic models (SubTask, TaskDAG, AgentResult)
│   ├── decomposer.py      # Descomponedor de tareas (Claude Opus)
│   ├── classifier.py      # Clasificador de tipos de agente
│   ├── spawner.py         # Creador y ejecutor de sub-agentes
│   ├── executor.py        # DAG Executor (LangGraph)
│   ├── worktree.py        # Git Worktree Manager
│   ├── memory.py          # Engram HTTP client
│   ├── reporter.py        # Compact Reporter
│   ├── merger.py          # Merge Coordinator
│   ├── errors.py          # Error handling + retry
│   ├── prompts/
│   │   ├── orchestrator.py
│   │   └── agents/        # System prompts por tipo de agente
│   └── graph/
│       ├── state.py       # LangGraph state
│       ├── nodes.py       # LangGraph nodes
│       └── builder.py     # Graph builder
├── tests/
│   ├── test_decomposer.py
│   ├── test_classifier.py
│   ├── test_worktree.py
│   └── test_memory.py
├── docs/
│   ├── ARCHITECTURE.md    # Arquitectura detallada
│   └── AGENT_TYPES.md     # Catálogo de tipos de agente
├── PLANNING_MVP.md        # Plan detallado del MVP (8 días)
├── PLANNING_COMPLETE.md   # Plan completo (38 días, 14 fases)
└── pyproject.toml
```

---

## Tests

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Tests con cobertura
pytest tests/ --cov=orchestrator --cov-report=term-missing
```

---

## Documentación

- [Arquitectura del Sistema](docs/ARCHITECTURE.md) — Diagramas, flujos, modelos de datos
- [Catálogo de Agentes](docs/AGENT_TYPES.md) — 8 tipos de agente con especificaciones
- [Plan MVP](PLANNING_MVP.md) — 7 fases, 8 días, criterios de aceptación
- [Plan Completo](PLANNING_COMPLETE.md) — 14 fases, 38 días, roadmap completo

---

## Contribuir

1. Fork del repositorio
2. Crear rama: `git checkout -b feature/mi-mejora`
3. Commit con mensajes descriptivos
4. Push y abrir Pull Request

---

## Licencia

MIT — ver [LICENSE](LICENSE)
