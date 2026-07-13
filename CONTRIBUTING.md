# Contributing to gaokao-analyzer

We love your input! We want to make contributing to gaokao-analyzer as easy and transparent as possible.

## Development Process

1. Fork the repo and create your branch from `main`
2. If you've added code, add tests
3. Ensure the test suite passes
4. Make sure your code lints
5. Issue a pull request

## Code Style

- **Python**: We use [Ruff](https://docs.astral.sh/ruff) for linting and formatting
- **TypeScript**: We use the built-in TS compiler with strict mode
- **Commit messages**: Use [Conventional Commits](https://www.conventionalcommits.org)

### Setup

```bash
pip install -r requirements-dev.txt
pre-commit install
```

### Before committing

```bash
# Run linting
ruff check .
ruff format --check .

# Run type checking
mypy agents/ services/ routes/

# Run tests
pytest tests/ -v
```

## Project Structure

```
gaokao-analyzer/
├── agents/          # AI Agent implementations (F1-F4)
│   ├── diagnosis_agent.py    # F1: Learning diagnosis
│   ├── planning_agent.py     # F2: Study planning
│   ├── recommendation_agent.py # F3: Exercise recommendation
│   └── assessment_agent.py   # F4: Assessment agent
├── services/        # Business logic services
│   ├── agent_service_adapter.py # Unified Agent-service bridge
│   └── error_review_service.py  # F8: Spaced repetition
├── routes/          # API endpoints
│   ├── agent.py     # Agent orchestration API
│   ├── learning.py  # Learning center API
│   └── assessment.py # Assessment API
├── frontend/        # React + TypeScript frontend
├── data/            # SQLite database (auto-created)
├── scripts/         # Utility scripts
├── tests/           # Test suite
├── models.py        # Database models & migrations
├── app.py           # FastAPI application
└── config.py        # Configuration
```

## Adding a New Agent

1. Create a new agent class in `agents/`
2. Optionally add FC tool services in `services/agents/`
3. Register the agent in `routes/agent.py`'s `get_orchestrator()`
4. Add state handler and transition in the orchestrator

## Adding a New API Route

1. Create a new route file in `routes/`
2. Import and register in `app.py` via `include_router`
3. Add Pydantic models for request/response validation

## Adding a New Database Migration

1. Add a new `_migrate_to_vN` function in `models.py`
2. Register it in the `MIGRATIONS` dict
3. Increment `CURRENT_SCHEMA_VERSION`

## Adding a New Frontend Page

1. Create the page component in `frontend/src/pages/`
2. Export it from the `index.ts` barrel file
3. Add a lazy-loaded route in `frontend/src/routes/index.tsx`
4. Add a sidebar navigation item in `frontend/src/layouts/Sidebar.tsx`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
