#!/usr/bin/env bash
# End-to-end multi-corpus demo: filesystem -> Neo4j graph -> hybrid,
# graph-expanded, grounded retrieval, run independently against two
# registered corpuses, then proving they are fully isolated. Runs the
# complete pipeline from a clean checkout and fails immediately on the
# first broken step.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

NEO4J_URI="bolt://localhost:7687"
READY_TIMEOUT_SECONDS=90
LOG_DIR="logs/demo"
CURRENT_LOG=""
RETRY_ATTEMPTS=3
RETRY_DELAY_SECONDS=2

declare -A CORPUS_QUERY=(
    [billing]="How are customers billed?"
    [engineering]="How does the engineering team deploy the service?"
)

mkdir -p "$LOG_DIR"

ts() {
    date '+%Y-%m-%d %H:%M:%S.%3N'
}

log() {
    echo "[$(ts)] $1"
}

fail() {
    echo "[$(ts)] Multi-corpus status: FAILURE" >&2
    echo "[$(ts)] $1" >&2
    if [ -n "$CURRENT_LOG" ] && [ -f "$CURRENT_LOG" ]; then
        echo "[$(ts)] --- tail of $CURRENT_LOG ---" >&2
        tail -n 50 "$CURRENT_LOG" >&2
        echo "[$(ts)] --- end of log ---" >&2
    fi
    exit 1
}

# Runs a command, teeing its combined stdout+stderr into a per-step log
# file (in addition to normal terminal output), and records the log file
# so fail() can dump it if a later assertion fails. Relies on pipefail
# (set above) so the reported exit status is the command's, not tee's.
run_step() {
    local logfile="$1"
    shift
    CURRENT_LOG="$logfile"
    : > "$logfile"
    "$@" 2>&1 | tee -a "$logfile"
}

# Retries a check function up to RETRY_ATTEMPTS times, ~RETRY_DELAY_SECONDS
# apart, truncating the given log file before each attempt. Mirrors the
# "poll instead of fail" precedent used by _wait_for_fulltext_queryable
# inside index(), applied here to the retrieval/query assertions that run
# immediately after --rebuild (the highest-risk window for eventually
# consistent Neo4j full-text/vector indexes).
retry_check() {
    local logfile="$1"
    shift
    local attempt
    for ((attempt = 1; attempt <= RETRY_ATTEMPTS; attempt++)); do
        CURRENT_LOG="$logfile"
        : > "$logfile"
        if "$@" "$logfile"; then
            return 0
        fi
        if [ "$attempt" -lt "$RETRY_ATTEMPTS" ]; then
            sleep "$RETRY_DELAY_SECONDS"
        fi
    done
    return 1
}

log "== Starting Neo4j =="
run_step "$LOG_DIR/00-neo4j-up.log" docker compose up -d neo4j || fail "failed to start Neo4j via docker compose"

log "== Waiting for Neo4j readiness =="
deadline=$((SECONDS + READY_TIMEOUT_SECONDS))
until run_step "$LOG_DIR/00-neo4j-wait.log" uv run oneo health; do
    if [ "$SECONDS" -ge "$deadline" ]; then
        fail "Neo4j did not become reachable at ${NEO4J_URI} within ${READY_TIMEOUT_SECONDS}s"
    fi
    sleep 2
done

log "== Health check =="
run_step "$LOG_DIR/00-health.log" uv run oneo health || fail "health check failed"

log "== Registered corpuses =="
run_step "$LOG_DIR/00-corpus-list.log" uv run oneo corpus list || fail "corpus registry could not be loaded"

for corpus in billing engineering; do
    root="./corpuses/${corpus}"

    log "== [$corpus] Filesystem security =="
    run_step "$LOG_DIR/${corpus}-files.log" uv run oneo files --corpus "$corpus" >/dev/null || fail "[$corpus] filesystem security check failed"

    log "== [$corpus] OKF validation =="
    run_step "$LOG_DIR/${corpus}-validate.log" uv run oneo validate --corpus "$corpus" --strict || fail "[$corpus] OKF corpus validation failed"

    log "== [$corpus] Resetting derived index =="
    run_step "$LOG_DIR/${corpus}-reset.log" uv run oneo reset --corpus "$corpus" || fail "[$corpus] reset failed"

    log "== [$corpus] Indexing (schema, documents, sections, links, embeddings) =="
    run_step "$LOG_DIR/${corpus}-index.log" uv run oneo index --corpus "$corpus" --rebuild || fail "[$corpus] indexing failed"

    log "== [$corpus] Hybrid retrieval =="
    check_hybrid_retrieval() {
        local logfile="$1"
        local output
        output=$(uv run oneo retrieve "${CORPUS_QUERY[$corpus]}" --mode hybrid --corpus "$corpus" 2>>"$logfile" | tee -a "$logfile")
        echo "$output" | grep -q "^\[seed\]"
    }
    retry_check "$LOG_DIR/${corpus}-retrieval.log" check_hybrid_retrieval || fail "[$corpus] hybrid retrieval returned no seed hits"

    log "== [$corpus] Graph expansion =="
    check_graph_expansion() {
        local logfile="$1"
        local output
        output=$(uv run oneo retrieve "${CORPUS_QUERY[$corpus]}" --mode graph-hybrid --top-k 1 --corpus "$corpus" 2>>"$logfile" | tee -a "$logfile")
        echo "$output" | grep -q "^\[expanded\]"
    }
    retry_check "$LOG_DIR/${corpus}-expansion.log" check_graph_expansion || fail "[$corpus] graph expansion returned no expanded hits"

    log "== [$corpus] Grounded answer generation =="
    check_grounded_answer() {
        local logfile="$1"
        local output
        output=$(uv run oneo query "${CORPUS_QUERY[$corpus]}" --mode graph-hybrid --corpus "$corpus" 2>>"$logfile" | tee -a "$logfile")
        echo "$output" | grep -q "^answer: " || return 1
        echo "$output" | grep -q "^insufficient_evidence: False$" || return 1

        local citation_lines
        citation_lines=$(echo "$output" | grep "^\[citation " || true)
        [ -n "$citation_lines" ] || return 1

        local line source_path
        while IFS= read -r line; do
            source_path=$(echo "$line" | grep -oP 'source_path=\K\S+')
            [ -n "$source_path" ] || return 1
            [ -f "$root/$source_path" ] || return 1
        done <<< "$citation_lines"
    }
    retry_check "$LOG_DIR/${corpus}-query.log" check_grounded_answer || fail "[$corpus] grounded answer generation failed (no answer, insufficient evidence, or missing/invalid citations)"

    log "Corpus ${corpus}: indexed, retrieval PASS, query PASS"
done

log "== Rebuild-from-filesystem (per corpus) =="
for corpus in billing engineering; do
    before=$(uv run oneo verify --corpus "$corpus")
    uv run oneo index --corpus "$corpus" --rebuild >/dev/null || fail "[$corpus] rebuild failed"
    after=$(uv run oneo verify --corpus "$corpus")
    [ "$before" = "$after" ] || fail "[$corpus] rebuild-from-filesystem produced a different verify snapshot"
    log "Rebuild-from-filesystem [$corpus]: PASS"
done

log "== Corpus isolation check =="
billing_docs=$(uv run oneo verify --corpus billing | grep -oP 'documents=\K[0-9]+')
engineering_docs=$(uv run oneo verify --corpus engineering | grep -oP 'documents=\K[0-9]+')
[ "$billing_docs" -gt 0 ] || fail "billing corpus reports zero documents"
[ "$engineering_docs" -gt 0 ] || fail "engineering corpus reports zero documents"

# Retrieving each corpus with the other corpus's query must never
# surface a citation whose source_path resolves inside the other
# corpus's root.
cross_query_output=$(uv run oneo query "${CORPUS_QUERY[engineering]}" --mode graph-hybrid --corpus billing || true)
cross_citations=$(echo "$cross_query_output" | grep "^\[citation " || true)
if [ -n "$cross_citations" ]; then
    while IFS= read -r line; do
        source_path=$(echo "$line" | grep -oP 'source_path=\K\S+')
        [ ! -f "./corpuses/engineering/$source_path" ] || fail "billing query surfaced an engineering-only source_path: $source_path"
    done <<< "$cross_citations"
fi
log "Corpus isolation: PASS"

log "== MCP agent interface =="
run_step "$LOG_DIR/mcp-agent-interface.log" uv run python -c "
import asyncio
from mcp.shared.memory import create_connected_server_and_client_session
from oneo.mcp_server import build_server

async def main():
    async with create_connected_server_and_client_session(build_server()) as session:
        corpora = await session.call_tool('oneo_list_corpuses', {})
        assert any(c['name'] == 'billing' for c in corpora.structuredContent['result'])
        ask = await session.call_tool('oneo_ask', {'question': 'How are customers billed?', 'corpus': 'billing'})
        assert ask.structuredContent['insufficient_evidence'] is False
        assert ask.structuredContent['citations']
        print('MCP agent interface: PASS')

asyncio.run(main())
" || fail "MCP agent interface check failed"

echo ""
log "Corpus billing: indexed, retrieval PASS, query PASS"
log "Corpus engineering: indexed, retrieval PASS, query PASS"
log "Corpus isolation: PASS"
log "Rebuild-from-filesystem (per corpus): PASS"
log "Multi-corpus status: SUCCESS"
