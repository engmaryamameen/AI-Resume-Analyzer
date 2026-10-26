# ADR 0003: Local models only, behind one engine interface

**Status:** accepted · **Context:** résumés are personal data; the product's value is trustworthy,
explainable evidence. Hosted AI services would send that data to a third party, and generative output
cannot be bounded against invented claims.
**Decision:** no third-party AI service is called, ever. Analysis uses three small, locally executed models
(a fine-tuned extractor, a pretrained retriever, a fine-tuned verifier) loaded from checksum-verified,
human-approved `safetensors` files, never downloaded by the application. The pipeline depends on one
`Engine` interface with two implementations: the learned engine, and a clearly labelled rule-based baseline
that is not presented as machine learning. Mode is all-or-nothing; on a budget overrun or failure the whole
analysis is redone with the rules engine and says so. No text generation: recommendations quote the résumé.
**Consequences:** data stays on the operator's machines; the application works without model files;
results record which engine produced them; model quality depends on training data that does not exist yet
([AI_LIMITATIONS.md](../AI_LIMITATIONS.md)).
**Rejected:** hosted LLM APIs (privacy); a local generative model for judging or rewriting (cannot be
validated or calibrated here); a vector database or agent framework (no need).
**Revisit when:** evaluation on real data shows the small models are not good enough; then try larger
encoders before anything else.
