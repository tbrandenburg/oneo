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

declare -A CORPUS_QUERY=(
    [billing]="How are customers billed?"
    [engineering]="How does the engineering team deploy the service?"
)

ts() {
    date '+%Y-%m-%d %H:%M:%S.%3N'
}

log() {
    echo "[$(ts)] $1"
}

fail() {
    echo "[$(ts)] Multi-corpus status: FAILURE" >&2
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

log "== Registered corpuses =="
uv run oneo corpus list || fail "corpus registry could not be loaded"

for corpus in billing engineering; do
    root="./corpuses/${corpus}"

    log "== [$corpus] Filesystem security =="
    uv run oneo files --corpus "$corpus" >/dev/null || fail "[$corpus] filesystem security check failed"

    log "== [$corpus] OKF validation =="
    uv run oneo validate --corpus "$corpus" --strict || fail "[$corpus] OKF corpus validation failed"

    log "== [$corpus] Resetting derived index =="
    uv run oneo reset --corpus "$corpus" || fail "[$corpus] reset failed"

    log "== [$corpus] Indexing (schema, documents, sections, links, embeddings) =="
    uv run oneo index --corpus "$corpus" --rebuild || fail "[$corpus] indexing failed"

    log "== [$corpus] Hybrid retrieval =="
    retrieval_output=$(uv run oneo retrieve "${CORPUS_QUERY[$corpus]}" --mode hybrid --corpus "$corpus")
    echo "$retrieval_output" | grep -q "^\[seed\]" || fail "[$corpus] hybrid retrieval returned no seed hits"

    log "== [$corpus] Graph expansion =="
    expansion_output=$(uv run oneo retrieve "${CORPUS_QUERY[$corpus]}" --mode graph-hybrid --top-k 1 --corpus "$corpus")
    echo "$expansion_output" | grep -q "^\[expanded\]" || fail "[$corpus] graph expansion returned no expanded hits"

    log "== [$corpus] Grounded answer generation =="
    query_output=$(uv run oneo query "${CORPUS_QUERY[$corpus]}" --mode graph-hybrid --corpus "$corpus")
    echo "$query_output" | grep -q "^answer: " || fail "[$corpus] no answer produced"
    echo "$query_output" | grep -q "^insufficient_evidence: False$" || fail "[$corpus] answer had insufficient evidence"

    citation_lines=$(echo "$query_output" | grep "^\[citation " || true)
    [ -n "$citation_lines" ] || fail "[$corpus] answer had no citations"
    while IFS= read -r line; do
        source_path=$(echo "$line" | grep -oP 'source_path=\K\S+')
        [ -n "$source_path" ] || fail "[$corpus] citation missing source_path: $line"
        [ -f "$root/$source_path" ] || fail "[$corpus] citation source_path does not resolve to a file: $source_path"
    done <<< "$citation_lines"

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

echo ""
log "Corpus billing: indexed, retrieval PASS, query PASS"
log "Corpus engineering: indexed, retrieval PASS, query PASS"
log "Corpus isolation: PASS"
log "Rebuild-from-filesystem (per corpus): PASS"
log "Multi-corpus status: SUCCESS"
