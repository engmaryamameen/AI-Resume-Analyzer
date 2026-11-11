# Notices

Copyright (c) 2026 Maryam Ameen. The backend, frontend, analysis pipeline, vocabulary, schemas, machine
learning code, tests and documentation in this repository are original work released under the MIT
licence in `LICENSE`.

No model weights are included. The models named in `models/manifest.json` and `backend/app/ml/semantic-models.json` are published by third parties
under their own licences (Apache-2.0 and MIT, see `docs/local-models.md`); anyone who
provisions them must follow those licences, including the notices they require. The synthetic and
hand-written datasets in `ml/data` are original and contain no real personal data.

Third-party runtime dependencies are declared in `backend/pyproject.toml` and `frontend/package.json` and
keep their own licences. Consult the resolved lockfiles and installed package notices for their licence terms.

The self-hosted Inter font (Rasmus Andersson) in `frontend/public/fonts/` is distributed under the SIL Open Font License 1.1. Its full copyright and licence notice is included alongside the WOFF2 file. No remote font provider is contacted at runtime.

The résumé-review image in `frontend/public/images/resume-review.webp` is illustrative. It does not depict a customer or testimonial. No third-party customer logos, endorsements, or testimonials are included.

The optional editorial reviewer uses Qwen3 through Ollama. The default [`qwen3:4b-instruct`](https://ollama.com/library/qwen3:4b-instruct) model is distributed under Apache License 2.0 and is provisioned separately. Preserve its model license and notices, and inspect the selected model's terms when changing the configured tag.
