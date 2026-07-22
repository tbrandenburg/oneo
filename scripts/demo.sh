#!/usr/bin/env bash
# End-to-end proof-of-concept demo: filesystem -> Neo4j graph -> hybrid,
# graph-expanded, grounded retrieval. Runs the complete pipeline from a
# clean checkout and fails immediately on the first broken step.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

QUERY="How are customers billed?"
KNOWLEDGE_ROOT="./knowledge"
NEO4J_URI="bolt://localhost:7687"
READY_TIMEOUT_SECONDS=90

ts() {
    date '+%Y-%m-%d %H:%M:%S.%3N'
}

log() {
    echo "[$(ts)] $1"
}

fail() {
    echo "[$(ts)] PoC status: FAILURE" >&2
    echo "[$(ts)] $1" >&2
    exit 1
}

log "== Starting Neo4j =="
docker compose up -d neo4j

log "== Waiting for Neo4j readiness =="
deadline=$((SECONDS + READY_TIMEOUT_SECONDS))
until uv run oneo health >/dev/null 2>&1; do
    if [ "$SECONDS" -ge "$deadline" ]; then
        fail "Neo4j did not become reachable at ${NEO4J_URI} within ${READY_TIMEOUT_SECONDS}s"
    fi
    sleep 2
done

log "== Health check =="
uv run oneo health || fail "health check failed"

log "== Filesystem security =="
uv run oneo files "$KNOWLEDGE_ROOT" >/dev/null || fail "filesystem security check failed"
log "Filesystem security: PASS"

log "== OKF validation =="
uv run oneo validate "$KNOWLEDGE_ROOT" --strict || fail "OKF corpus validation failed"
log "OKF validation: PASS"

log "== Resetting derived index =="
uv run oneo reset || fail "reset failed"

log "== Indexing (schema, documents, sections, links, embeddings) =="
# A single `oneo index` run resets the owned graph, applies the Neo4j
# schema, projects documents/sections/relationships, embeds sections,
# and raises unless the vector and full-text indexes both reach ONLINE.
uv run oneo index "$KNOWLEDGE_ROOT" --rebuild || fail "indexing failed"
log "Graph projection: PASS"
log "Vector index: ONLINE"
log "Full-text index: ONLINE"

log "== Hybrid retrieval =="
retrieval_output=$(uv run oneo retrieve "customer billing" --mode hybrid)
echo "$retrieval_output" | grep -q "^\[seed\]" || fail "hybrid retrieval returned no seed hits"
log "Hybrid retrieval: PASS"

log "== Graph expansion =="
expansion_output=$(uv run oneo retrieve "customer billing" --mode graph-hybrid)
echo "$expansion_output" | grep -q "^\[expanded\]" || fail "graph expansion returned no expanded hits"
log "Graph expansion: PASS"

log "== Grounded answer generation =="
query_output=$(uv run oneo query "$QUERY" --mode graph-hybrid)
echo "$query_output" | grep -q "^answer: " || fail "no answer produced"
echo "$query_output" | grep -q "^insufficient_evidence: False$" || fail "answer had insufficient evidence"

log "== Verifying citations =="
citation_lines=$(echo "$query_output" | grep "^\[citation " || true)
[ -n "$citation_lines" ] || fail "answer had no citations"
while IFS= read -r line; do
    source_path=$(echo "$line" | grep -oP 'source_path=\K\S+')
    [ -n "$source_path" ] || fail "citation missing source_path: $line"
    [ -f "$KNOWLEDGE_ROOT/$source_path" ] || fail "citation source_path does not resolve to a file: $source_path"
done <<< "$citation_lines"
log "Answer grounding: PASS"

echo ""
log "Filesystem security: PASS"
log "OKF validation: PASS"
log "Graph projection: PASS"
log "Vector index: ONLINE"
log "Full-text index: ONLINE"
log "Hybrid retrieval: PASS"
log "Graph expansion: PASS"
log "Answer grounding: PASS"
log "PoC status: SUCCESS"
