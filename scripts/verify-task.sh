#!/bin/bash
# scripts/verify-task.sh
#
# Purpose:
#   Deterministic verification gate for Codex / coding-agent loops.
#
# Usage:
#   ./scripts/verify-task.sh
#   ./scripts/verify-task.sh tests/test_app.py
#
# Optional env vars:
#   FULL=1              Run broader checks when available.
#   SKIP_LINT=1         Skip lint checks.
#   SKIP_TYPECHECK=1    Skip typecheck checks.
#   SKIP_TESTS=1        Skip tests.
#
# Recommended Codex instruction:
#   After every code change, run ./scripts/verify-task.sh.
#   If it fails, inspect the first relevant error and make one focused fix.
#   Stop only when this script passes.

set -Eeuo pipefail

TARGET="${1:-}"
FULL="${FULL:-0}"
SKIP_LINT="${SKIP_LINT:-0}"
SKIP_TYPECHECK="${SKIP_TYPECHECK:-0}"
SKIP_TESTS="${SKIP_TESTS:-0}"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

LOG_DIR=".codex"
LOG_FILE="$LOG_DIR/verify-task.log"
mkdir -p "$LOG_DIR"

CURRENT_STEP="startup"

trap 'echo ""; echo "❌ Verification failed during: ${CURRENT_STEP}"; echo "See ${LOG_FILE} for details."; exit 1' ERR

log() {
  printf "\n[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

run() {
  CURRENT_STEP="$*"
  log "▶ $*"
  "$@" 2>&1 | tee -a "$LOG_FILE"
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

has_file() {
  [ -f "$1" ]
}

has_poetry_project() {
  has_file "pyproject.toml" && grep -q '^\[tool\.poetry\]' pyproject.toml
}

run_python_tool() {
  if has_poetry_project && has_cmd poetry; then
    run poetry run "$@"
  else
    run "$@"
  fi
}

has_python_tool() {
  local tool_name="$1"

  if has_poetry_project && has_cmd poetry; then
    poetry run python -c "import shutil, sys; sys.exit(0 if shutil.which('${tool_name}') else 1)" >/dev/null 2>&1
  else
    has_cmd "$tool_name"
  fi
}

package_json_has_script() {
  local script_name="$1"

  if ! has_file "package.json"; then
    return 1
  fi

  if has_cmd node; then
    node -e "
      const pkg = require('./package.json');
      process.exit(pkg.scripts && pkg.scripts['${script_name}'] ? 0 : 1);
    "
  else
    grep -q "\"${script_name}\"[[:space:]]*:" package.json
  fi
}

node_pm() {
  if has_file "pnpm-lock.yaml" && has_cmd pnpm; then
    echo "pnpm"
  elif has_file "yarn.lock" && has_cmd yarn; then
    echo "yarn"
  elif has_file "bun.lockb" && has_cmd bun; then
    echo "bun"
  elif has_file "package-lock.json" && has_cmd npm; then
    echo "npm"
  elif has_file "package.json" && has_cmd npm; then
    echo "npm"
  else
    echo ""
  fi
}

run_node_script() {
  local pm="$1"
  local script_name="$2"

  case "$pm" in
    pnpm) run pnpm run "$script_name" ;;
    yarn) run yarn "$script_name" ;;
    bun)  run bun run "$script_name" ;;
    npm)  run npm run "$script_name" ;;
    *)    return 1 ;;
  esac
}

run_node_tests() {
  local pm="$1"

  if package_json_has_script "test"; then
    if [ -n "$TARGET" ]; then
      case "$pm" in
        pnpm) run pnpm test -- "$TARGET" ;;
        yarn) run yarn test "$TARGET" ;;
        bun)  run bun test "$TARGET" ;;
        npm)  run npm test -- "$TARGET" ;;
      esac
    else
      run_node_script "$pm" "test"
    fi
  fi
}

run_node_checks() {
  local pm
  pm="$(node_pm)"

  if [ -z "$pm" ]; then
    return 0
  fi

  log "Detected Node.js project using ${pm}"

  if [ "$SKIP_LINT" != "1" ] && package_json_has_script "lint"; then
    run_node_script "$pm" "lint"
  fi

  if [ "$SKIP_TYPECHECK" != "1" ]; then
    if package_json_has_script "typecheck"; then
      run_node_script "$pm" "typecheck"
    elif package_json_has_script "type-check"; then
      run_node_script "$pm" "type-check"
    fi
  fi

  if [ "$SKIP_TESTS" != "1" ]; then
    run_node_tests "$pm"
  fi

  if [ "$FULL" = "1" ] && package_json_has_script "build"; then
    run_node_script "$pm" "build"
  fi
}

run_python_checks() {
  if ! has_file "pyproject.toml" && ! has_file "requirements.txt" && ! has_file "setup.py"; then
    return 0
  fi

  if has_poetry_project && has_cmd poetry; then
    log "Detected InnSight Python project using Poetry"
  else
    log "Detected Python project"
  fi

  if [ "$SKIP_LINT" != "1" ]; then
    if has_python_tool ruff; then
      run_python_tool ruff check .
    elif has_python_tool flake8; then
      run_python_tool flake8 .
    fi
  fi

  if [ "$SKIP_TYPECHECK" != "1" ] && has_python_tool mypy; then
    run_python_tool mypy .
  fi

  if [ "$SKIP_TESTS" != "1" ]; then
    if has_poetry_project && has_cmd poetry; then
      if [ -n "$TARGET" ]; then
        run poetry run pytest "$TARGET"
      else
        run poetry run pytest
      fi
    elif has_cmd pytest; then
      if [ -n "$TARGET" ]; then
        run pytest "$TARGET"
      else
        run pytest
      fi
    elif has_cmd python && [ -d "tests" ]; then
      run python -m unittest discover
    fi
  fi

  if [ "$FULL" = "1" ] && has_poetry_project && has_cmd poetry; then
    run poetry build
  fi
}

run_go_checks() {
  if ! has_file "go.mod"; then
    return 0
  fi

  log "Detected Go project"

  if has_cmd gofmt; then
    CURRENT_STEP="gofmt check"
    log "▶ gofmt check"
    UNFORMATTED="$(gofmt -l .)"
    if [ -n "$UNFORMATTED" ]; then
      echo "$UNFORMATTED" | tee -a "$LOG_FILE"
      echo "❌ Go files need formatting. Run: gofmt -w <files>" | tee -a "$LOG_FILE"
      exit 1
    fi
  fi

  if [ "$SKIP_TESTS" != "1" ]; then
    if [ -n "$TARGET" ]; then
      run go test "$TARGET"
    else
      run go test ./...
    fi
  fi
}

run_rust_checks() {
  if ! has_file "Cargo.toml"; then
    return 0
  fi

  log "Detected Rust project"

  if has_cmd cargo; then
    if [ "$SKIP_LINT" != "1" ]; then
      run cargo fmt --check
      if [ "$FULL" = "1" ]; then
        run cargo clippy --all-targets --all-features -- -D warnings
      fi
    fi

    if [ "$SKIP_TESTS" != "1" ]; then
      if [ -n "$TARGET" ]; then
        run cargo test "$TARGET"
      else
        run cargo test
      fi
    fi
  fi
}

run_custom_project_check() {
  if [ -x "./scripts/verify-local.sh" ]; then
    log "Detected custom project verifier: ./scripts/verify-local.sh"
    run ./scripts/verify-local.sh "$TARGET"
  fi
}

main() {
  : > "$LOG_FILE"

  log "Starting verification"
  log "Repository: $ROOT"
  log "Target: ${TARGET:-<none>}"
  log "FULL=${FULL} SKIP_LINT=${SKIP_LINT} SKIP_TYPECHECK=${SKIP_TYPECHECK} SKIP_TESTS=${SKIP_TESTS}"

  run_custom_project_check
  run_node_checks
  run_python_checks
  run_go_checks
  run_rust_checks

  CURRENT_STEP="final git diff check"

  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log "Changed files:"
    git status --short | tee -a "$LOG_FILE"
  fi

  log "✅ Verification passed"
}

main "$@"
