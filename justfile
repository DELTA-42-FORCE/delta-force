set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

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
    @status=0; \
    just api-audit || status=1; \
    just web-audit || status=1; \
    just desktop-audit || status=1; \
    exit "$status"

workspace-check:
    git diff --check
    docker compose --env-file .env.example -f infra/compose.yaml config --quiet

# --- API (Python / FastAPI) ---
api-install:
    cd apps/api; uv sync --all-groups

api-format:
    cd apps/api; uv run black src tests scripts alembic

api-format-check:
    cd apps/api; uv run black --check src tests scripts alembic

# Sobe a API local no Windows sem expor a porta à rede.
api-dev:
    cd apps/api; uv run python -m crm_api.dev_server

api-lint:
    cd apps/api; uv run flake8 src tests scripts alembic

api-test *args:
    cd apps/api; uv run pytest {{args}}

# Alvo obrigatório de integração (ADR 0003): SQLite de arquivo, sem Docker,
# PostgreSQL ou MinIO.
api-test-integration-sqlite:
    cd apps/api; uv run python scripts/run_sqlite_integration_tests.py

# Fundação legada em remoção pela #54; mantido enquanto o código de transição
# PostgreSQL existir (ADR 0003).
api-test-integration:
    docker compose --env-file .env -f infra/compose.yaml up -d postgres
    cd apps/api; uv run python scripts/wait_for_database.py
    cd apps/api; uv run python scripts/run_integration_tests.py

api-migrate:
    cd apps/api; uv run alembic upgrade head

api-rollback revision="-1":
    cd apps/api; uv run alembic downgrade {{revision}}

api-makemigration message:
    cd apps/api; uv run alembic revision --autogenerate -m "{{message}}"

api-check:
    just api-format-check
    just api-lint
    just api-test
    just api-test-integration-sqlite

api-audit:
    @status=0; \
    echo "Running Bandit (API code security)..."; \
    (cd apps/api && uv run bandit -r src) || status=1; \
    echo "Running pip-audit (Python dependency vulnerabilities)..."; \
    (cd apps/api && uv run pip-audit) || status=1; \
    echo "Available Python dependency updates (informational only):"; \
    (cd apps/api && uv run pip list --outdated) || true; \
    exit "$status"

# --- Web (React / TypeScript) ---
web-install:
    npm --prefix apps/web ci

web-dev:
    npm --prefix apps/web run dev

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
    @status=0; \
    echo "Running npm audit (web dependency vulnerabilities)..."; \
    npm --prefix apps/web audit || status=1; \
    echo "Available web dependency updates (informational only):"; \
    npm --prefix apps/web outdated || true; \
    exit "$status"

# --- Aplicativo Windows (Tauri + FastAPI sidecar) ---
# Estes alvos devem ser executados no Windows. O sidecar é gerado como PyInstaller
# `onedir` e nunca é versionado: o bundle Tauri o incorpora como recurso privado.
desktop-install:
    npm --prefix apps/desktop ci

desktop-sidecar:
    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File apps/desktop/scripts/build-sidecar.ps1

desktop-dev:
    just desktop-sidecar
    npm --prefix apps/desktop run dev

desktop-build:
    just desktop-sidecar
    npm --prefix apps/desktop run build

desktop-installer-smoke:
    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File apps/desktop/scripts/test-installer.ps1

desktop-format-check:
    cargo fmt --manifest-path apps/desktop/src-tauri/Cargo.toml --check

desktop-test:
    cd apps/api; uv run pytest tests/unit/test_desktop_runtime.py tests/unit/test_desktop_server.py tests/integration/test_desktop_sidecar_runtime.py
    cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml

desktop-audit:
    @status=0; \
    echo "Running npm audit (desktop tooling vulnerabilities)..."; \
    npm --prefix apps/desktop audit || status=1; \
    echo "Running cargo-audit (Rust dependency vulnerabilities)..."; \
    if command -v cargo-audit >/dev/null 2>&1; then \
        cargo audit --file apps/desktop/src-tauri/Cargo.lock || status=1; \
    else \
        echo "cargo-audit is required; install it with: cargo install cargo-audit --locked"; \
        status=1; \
    fi; \
    echo "Available desktop npm updates (informational only):"; \
    npm --prefix apps/desktop outdated || true; \
    exit "$status"

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
