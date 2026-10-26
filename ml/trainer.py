"""Shared training mechanics: seeding, optimiser, schedule, early stopping, run bookkeeping."""

import hashlib
import json
import os
import platform
import random
import subprocess
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TypeVar

import torch

T = TypeVar("T")


@dataclass(frozen=True)
class TrainConfig:
    seed: int = 13
    epochs: int = 4
    batch_size: int = 16
    learning_rate: float = 3e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    max_grad_norm: float = 1.0
    patience: int = 2  # epochs without validation improvement before stopping
    head_loss_weight: float = 1.0  # extractor only: weight of the role loss

    @classmethod
    def load(cls, path: Path) -> "TrainConfig":
        return cls(**json.loads(path.read_text(encoding="utf-8")))


def seed_everything(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")


def batches(items: Sequence[T], size: int, rng: random.Random | None = None) -> Iterator[list[T]]:
    order = list(range(len(items)))
    if rng is not None:
        rng.shuffle(order)
    for i in range(0, len(order), size):
        yield [items[j] for j in order[i: i + size]]


def make_optimizer(model: torch.nn.Module, config: TrainConfig, total_steps: int):
    no_decay = ("bias", "LayerNorm.weight", "layer_norm.weight")
    groups = [
        {"params": [p for n, p in model.named_parameters() if not any(k in n for k in no_decay)],
         "weight_decay": config.weight_decay},
        {"params": [p for n, p in model.named_parameters() if any(k in n for k in no_decay)], "weight_decay": 0.0},
    ]
    optimizer = torch.optim.AdamW(groups, lr=config.learning_rate)
    warmup = max(1, int(total_steps * config.warmup_ratio))

    def factor(step: int) -> float:
        if step < warmup:
            return (step + 1) / warmup
        return max(0.0, (total_steps - step) / max(1, total_steps - warmup))

    return optimizer, torch.optim.lr_scheduler.LambdaLR(optimizer, factor)


def fit(
    model: torch.nn.Module, train_items: Sequence[T], config: TrainConfig,
    step_loss: Callable[[Sequence[T]], torch.Tensor], validate: Callable[[], float], log: Callable[[dict], None],
) -> dict[str, torch.Tensor]:
    """Train, keep the weights from the epoch with the best validation score, and return them.

    `validate` returns a score where higher is better (macro-F1)."""
    rng = random.Random(config.seed)
    steps_per_epoch = (len(train_items) + config.batch_size - 1) // config.batch_size
    optimizer, scheduler = make_optimizer(model, config, steps_per_epoch * config.epochs)
    best_score, best_state, stale = float("-inf"), None, 0
    for epoch in range(1, config.epochs + 1):
        model.train()
        started, total = time.perf_counter(), 0.0
        for batch in batches(train_items, config.batch_size, rng):
            optimizer.zero_grad(set_to_none=True)
            loss = step_loss(batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            optimizer.step()
            scheduler.step()
            total += float(loss) * len(batch)
        model.eval()
        with torch.no_grad():
            score = validate()
        log({"epoch": epoch, "train_loss": total / max(1, len(train_items)), "validation_score": score,
             "seconds": time.perf_counter() - started})
        if score > best_score:
            best_score, stale = score, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= config.patience:
                break
    if best_state is None:
        raise ValueError("nothing was trained: epochs must be at least 1")
    return best_state


def sha256_of_weights(base_dir: Path) -> str:
    """Identifies the exact base weights a run started from."""
    digest = hashlib.sha256()
    for path in sorted(base_dir.glob("*.safetensors")):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def environment() -> dict:
    """What the run was produced with, so a result can be reproduced or questioned later."""
    import transformers

    try:
        code = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False, timeout=10)
        code_version = code.stdout.strip() or "unknown"
    except OSError:
        code_version = "unknown"
    return {"python": platform.python_version(), "torch": torch.__version__, "transformers": transformers.__version__,
            "cuda": torch.version.cuda, "device": "cuda" if torch.cuda.is_available() else "cpu",
            "code_version": code_version}


def write_run_record(out_dir: Path, name: str, payload: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / name).write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def config_dict(config: TrainConfig) -> dict:
    return asdict(config)
