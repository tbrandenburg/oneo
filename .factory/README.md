# .factory/

This directory holds operator tooling used to *build* the Oneo proof of
concept via the plan-splitting/implement/review/demo agent workflow. It is
not part of the shipped Oneo CLI/package described in `doc/plan/plan.md`.

- `factory_v2.sh` — orchestrates the meta process of driving an agent
  through the implementation plan steps (split, implement, review, demo
  lifecycle) for this repository. Run it from outside the shipped package
  boundary; it has no runtime dependency on `src/` or `tests/` and is not
  imported or invoked by the Oneo application itself.
