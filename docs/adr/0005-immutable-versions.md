# ADR 0005: Immutable résumé and job-description versions

**Status:** accepted · **Decision:** edits never change a version; they create the next one under a
row lock with a `base_version_no` check. Analyses reference exact versions.
**Consequences:** "which text produced this result" is always answerable; staleness is a comparison
of version numbers; more rows. **Rejected:** in-place edits plus a history table.
