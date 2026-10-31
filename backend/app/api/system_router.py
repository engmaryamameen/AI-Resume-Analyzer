from fastapi import APIRouter, Depends

from app.api.schemas import ModelStatusOut
from app.core.config import Settings, get_settings
from app.ml.manifest import REQUIRED_MODELS, ArtifactError, fingerprint, load_manifest

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/models", response_model=ModelStatusOut)
def models(settings: Settings = Depends(get_settings)) -> ModelStatusOut:
    """Which local models are approved on this server. The worker's actual state is recorded per analysis."""
    if not settings.ml_enabled:
        return ModelStatusOut(
            learned_models_approved=False,
            models=[],
            note="Local neural inference is disabled; analyses use the rule-based reading.",
        )
    try:
        if settings.ml_enabled and (settings.model_dir / "semantic-manifest.json").is_file():
            from app.ml.semantic import semantic_manifest

            semantic = semantic_manifest(settings.model_dir)
            return ModelStatusOut(
                available_method="semantic",
                learned_models_approved=False,
                models=[entry.ref() for entry in semantic.models],
                note="Pinned pretrained semantic models are provisioned locally. Each report records the engine actually used.",
            )
        manifest = load_manifest(settings.model_dir)
    except (ArtifactError, ValueError, OSError):
        return ModelStatusOut(
            learned_models_approved=False,
            models=[],
            note="No model manifest is installed; analyses use the rule-based reading.",
        )
    approved = fingerprint(manifest) != "rules"
    return ModelStatusOut(
        available_method="learned" if approved else "rules",
        learned_models_approved=approved,
        models=[m.ref() for m in manifest.models if m.id in REQUIRED_MODELS and m.approved],
        note=(
            "Approved local models are installed; each analysis records whether they were used."
            if approved
            else "The local models are not all approved yet; analyses use the rule-based reading."
        ),
    )
