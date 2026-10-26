# ADR 0001: Modular monolith

**Status:** accepted · **Context:** one small team, bursty workload, one transactional database.
**Decision:** one backend package with domain sub-packages and a one-way dependency rule; a worker
process runs the same code. **Consequences:** simple transactions and deployment; boundaries are kept
by convention and review, not by the network. **Alternatives:** microservices (rejected: cost
without a scaling need).
