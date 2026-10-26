# Notices

Copyright (c) 2026 Maryam Ameen. The backend, frontend, analysis pipeline, vocabulary, schemas, machine
learning code, tests and documentation in this repository are original work released under the MIT
licence in `LICENSE`.

No model weights are included. The models named in `models/manifest.json` are published by third parties
under their own licences (Apache-2.0 and MIT, see `docs/MODEL_SELECTION_AND_PROVENANCE.md`); anyone who
provisions them must follow those licences, including the notices they require. The synthetic and
hand-written datasets in `ml/data` are original and contain no real personal data.

Third-party runtime dependencies are declared in `backend/pyproject.toml` and `frontend/package.json` and
keep their own licences. A generated dependency licence inventory has not been produced yet; create one
from the resolved lockfiles when you build the environment.
