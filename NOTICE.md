# Notices

Copyright (c) 2026 Maryam Ameen. The backend, frontend, analysis pipeline, vocabulary, schemas, machine
learning code, tests and documentation in this repository are original work released under the MIT
licence in `LICENSE`.

No model weights are included. The models named in `models/manifest.json` and `backend/app/ml/semantic-models.json` are published by third parties
under their own licences (Apache-2.0 and MIT, see `docs/local-models.md`); anyone who
provisions them must follow those licences, including the notices they require. The synthetic and
hand-written datasets in `ml/data` are original and contain no real personal data.

Third-party runtime dependencies are declared in `backend/pyproject.toml` and `frontend/package.json` and
keep their own licences. A generated dependency licence inventory has not been produced yet; create one
from the resolved lockfiles when you build the environment.

Self-hosted fonts in `frontend/public/fonts/`: Inter (Rasmus Andersson) and Source Serif 4
(Adobe) are distributed under the SIL Open Font License 1.1. Their full copyright and licence
notices are included alongside the WOFF2 files. No remote font provider is contacted at runtime.
