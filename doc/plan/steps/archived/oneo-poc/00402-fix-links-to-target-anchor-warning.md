> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Fix Neo4j warning for unresolved LINKS_TO target_anchor property

## Why this matters

`Neo4jStore.write_links` (added in Step 00400) runs
`SET r.target_anchor = row.target_anchor`. When a resolved
`OkfLink.target_anchor` is `None` (e.g. a plain document link with no
`#anchor` fragment, such as `knowledge/overview.md`'s link to
`topics/example.markdown`), Neo4j silently does not create the
`target_anchor` property on the relationship (Neo4j has no concept of
a null property value — `SET x = null` removes/never creates the key).

Every subsequent read of that property (`Neo4jStore.export_graph`, and
any future consumer that queries `r.target_anchor`) then triggers a
Neo4j driver warning:

```
warn: property key does not exist. The property `target_anchor` does
not exist. Verify that the spelling is correct.
```

This was reproduced during review by running `oneo reset`,
`oneo index ./knowledge --no-embeddings`, and calling
`Neo4jStore.export_graph()` directly — the warning fires on every call
because the sample corpus's only link has no anchor. This is validation
noise introduced by this step's own code and will get noisier as more
anchor-less links are indexed; it should be silenced before it masks a
real schema problem in a later step (e.g. Step 6 hybrid retrieval or
Step 7 graph expansion, both of which will also read `LINKS_TO`
properties).

## Actions

1. In `src/oneo/neo4j_store.py`, update `write_links` and any Cypher
   that reads `r.target_anchor` to tolerate the property legitimately
   not existing, e.g. by using `coalesce(r.target_anchor, null)` in
   `RETURN`/`ORDER BY` clauses, or by only conditionally `SET`-ing the
   property when `row.target_anchor IS NOT NULL`.
2. Confirm the fix by re-running:
   ```bash
   oneo reset
   oneo index ./knowledge --no-embeddings
   ```
   and calling `Neo4jStore.export_graph()` (or any code path that reads
   `target_anchor`) and confirming no Neo4j driver warning is emitted.
3. Add/extend a unit or integration test asserting that indexing a link
   without an anchor produces no driver warning and that
   `export_graph()`/`list_documents()`-style reads still return the
   expected (null/absent) `target_anchor` value.
4. Re-run the full test suite (`pytest tests/unit tests/integration`)
   and confirm all tests still pass.
