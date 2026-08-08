set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
    @just --list

# Instala as dependências de todos os apps.
install:
    just api-install
    just web-install

# Verificação mínima que todo desenvolvedor executa antes de abrir um PR.
check:
    just workspace-check
    just api-check
    just web-check

# Auditoria manual: falha para vulnerabilidades e apenas informa versões novas.
# Não faz atualização automática de dependências.
audit:
    just api-audit
    just web-audit

workspace-check:
    git diff --check
    docker compose --env-file .env.example -f infra/compose.yaml config --quiet

# --- API (Python / FastAPI) ---
api-install:
    cd apps/api && uv sync --all-groups

api-format:
    cd apps/api && uv run black src tests

api-format-check:
    cd apps/api && uv run black --check src tests

api-lint:
    cd apps/api && uv run flake8 src tests

api-test *args:
    cd apps/api && uv run pytest {{args}}

api-check:
    just api-format-check
    just api-lint
    just api-test

api-audit:
    @echo "Running Bandit (API code security)..."
    cd apps/api && uv run bandit -r src
    @echo "Running pip-audit (Python dependency vulnerabilities)..."
    @set +e; cd apps/api; uv run pip-audit; audit_status=$?; set -e; echo "Available Python dependency updates (informational only):"; uv run pip list --outdated; exit "$audit_status"

# --- Web (React / TypeScript) ---
web-install:
    npm --prefix apps/web ci

web-format:
    npm --prefix apps/web run format

web-format-check:
    npm --prefix apps/web run format:check

web-lint:
    npm --prefix apps/web run lint

web-test:
    npm --prefix apps/web run test -- --run

web-typecheck:
    npm --prefix apps/web run typecheck

web-check:
    just web-format-check
    just web-lint
    just web-typecheck
    just web-test

web-audit:
    @echo "Running npm audit (JavaScript dependency vulnerabilities)..."
    @set +e; npm --prefix apps/web audit; audit_status=$?; set -e; echo "Available JavaScript dependency updates (informational only):"; npm --prefix apps/web outdated || test $? -eq 1; exit "$audit_status"

# --- Infraestrutura local ---
infra-up:
    docker compose --env-file .env -f infra/compose.yaml up -d

infra-down:
    docker compose --env-file .env -f infra/compose.yaml down

infra-logs:
    docker compose --env-file .env -f infra/compose.yaml logs -f

infra-reset:
    docker compose --env-file .env -f infra/compose.yaml down -v

# --- Higiene de Git ---
sync-develop:
    git fetch origin
    git rebase origin/develop

sync-main:
    git fetch origin
    git rebase origin/main
