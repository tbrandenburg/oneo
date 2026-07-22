.PHONY: help sync up down health validate index reset query retrieve cypher test test-unit test-integration test-e2e demo publish clean

help:
	@echo "Available targets:"
	@echo "  sync             Install/sync dependencies with uv"
	@echo "  up               Start Neo4j (docker compose)"
	@echo "  down             Stop Neo4j (docker compose)"
	@echo "  health           Check Neo4j connectivity via the CLI"
	@echo "  validate         Validate the OKF knowledge corpus (strict)"
	@echo "  index            Rebuild the Neo4j graph index from ./knowledge"
	@echo "  reset            Delete the derived Neo4j index"
	@echo "  retrieve         Run hybrid retrieval; use QUERY=\"...\""
	@echo "  query            Run a grounded query; use QUERY=\"...\""
	@echo "  cypher           Run Cypher via the Neo4j HTTP API; use CYPHER=\"...\""
	@echo "  test             Run the full pytest suite"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only (needs Neo4j)"
	@echo "  test-e2e         Run end-to-end tests only"
	@echo "  demo             Run the full end-to-end demo script"
	@echo "  publish          Bump version, tag, and release; use BUMP=patch|minor|major"
	@echo "  clean            Remove build artifacts"

KNOWLEDGE_ROOT ?= ./knowledge
QUERY ?= How are customers billed?
NEO4J_HTTP_URL ?= http://localhost:7474/db/neo4j/query/v2
NEO4J_USER ?= neo4j
NEO4J_PASSWORD ?= password
CYPHER ?= MATCH (d:OkfDocument) OPTIONAL MATCH (d)-[l:LINKS_TO]->(target:OkfDocument) OPTIONAL MATCH (d)-[:HAS_SECTION]->(s:OkfSection) RETURN d.document_id AS document, s.heading AS section, l.raw_target AS raw_target, l.target_anchor AS link_to_anchor, target.document_id AS linked_document
BUMP ?= patch

sync:
	uv sync

up:
	docker compose up -d neo4j

down:
	docker compose down

health:
	uv run oneo health

validate:
	uv run oneo validate $(KNOWLEDGE_ROOT) --strict

index:
	uv run oneo index $(KNOWLEDGE_ROOT) --rebuild

reset:
	uv run oneo reset

retrieve:
	uv run oneo retrieve "$(QUERY)" --mode hybrid

query:
	uv run oneo query "$(QUERY)"

cypher:
	curl -s -u $(NEO4J_USER):$(NEO4J_PASSWORD) -H "Content-Type: application/json" \
		-X POST $(NEO4J_HTTP_URL) \
		-d '{"statement": "$(CYPHER)"}'

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit

test-integration:
	uv run pytest tests/integration

test-e2e:
	uv run pytest tests/e2e

demo:
	./scripts/demo.sh

publish:
	@case "$(BUMP)" in \
		patch|minor|major) ;; \
		*) echo "BUMP must be one of: patch, minor, major (got '$(BUMP)')" >&2; exit 1 ;; \
	esac
	@test -z "$$(git status --porcelain)" || { echo "Working tree is not clean; commit or stash changes before publishing" >&2; exit 1; }
	uv run pytest
	uv version --bump $(BUMP)
	uv build
	git add pyproject.toml uv.lock
	git commit -m "chore: release $$(uv version --short)"
	git tag -a "$$(uv version --short)" -m "Release $$(uv version --short)"
	git push origin HEAD "$$(uv version --short)"
	gh release create "$$(uv version --short)" --verify-tag --title "$$(uv version --short)" --generate-notes

clean:
	rm -rf build/* .pytest_cache .coverage
