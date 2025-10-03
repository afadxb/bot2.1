from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List

from ..settings import AppSettings
from ..storage import models
from ..storage.db import Database
from ..utils.time import now_et, to_epoch_seconds

logger = logging.getLogger(__name__)

_POSITIVE_LEXICON = {"beat", "surge", "strong", "record", "upgrade", "positive"}
_NEGATIVE_LEXICON = {"miss", "drop", "weak", "downgrade", "negative", "lawsuit"}

try:  # pragma: no cover - optional dependency
    from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore
    import torch  # type: ignore

    _TRANSFORMERS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    AutoModelForSequenceClassification = None  # type: ignore
    AutoTokenizer = None  # type: ignore
    torch = None  # type: ignore
    _TRANSFORMERS_AVAILABLE = False


@dataclass(slots=True)
class SentimentResult:
    score: float
    gate: str
    reasons: List[str]


class SentimentAnalyzer:
    def __init__(self, settings: AppSettings, db: Database) -> None:
        self.settings = settings
        self.db = db
        self._pipeline = None
        if (
            self.settings.ai_model.lower() == "finbert"
            and self.settings.ai_sentiment_enabled
            and _TRANSFORMERS_AVAILABLE
        ):
            try:
                tokenizer = AutoTokenizer.from_pretrained("yiyanghkust/finbert-tone")
                model = AutoModelForSequenceClassification.from_pretrained("yiyanghkust/finbert-tone")
                self._pipeline = (tokenizer, model)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to load FinBERT; falling back to heuristics: %s", exc)
                self._pipeline = None

    def analyze(self, news_items: Iterable[models.Catalyst]) -> Dict[str, SentimentResult]:
        news_map: Dict[str, List[models.Catalyst]] = {}
        for item in news_items:
            news_map.setdefault(item.symbol, []).append(item)

        results: Dict[str, SentimentResult] = {}
        provenance: List[models.AIProvenanceRecord] = []
        for symbol, items in news_map.items():
            if not self.settings.ai_sentiment_enabled:
                results[symbol] = SentimentResult(score=0.0, gate="PASS", reasons=["disabled"])
                continue

            if self._pipeline:
                score = self._score_with_finbert(items)
            else:
                score = self._score_with_heuristic(items)

            gate = "PASS"
            reasons: List[str] = []
            if score <= -0.7:
                gate = "VETO"
                reasons.append("strong negative sentiment")
            elif score <= -0.4 and self.settings.ai_soft_veto:
                gate = "SOFT_VETO"
                reasons.append("soft negative sentiment")
            else:
                reasons.append("neutral or positive")

            results[symbol] = SentimentResult(score=score, gate=gate, reasons=reasons)
            provenance.append(self._build_provenance(symbol, score, gate, reasons, items))

        if provenance:
            self.db.write_ai_provenance(provenance)
        return results

    def _score_with_finbert(self, items: List[models.Catalyst]) -> float:
        # Simplified FinBERT scoring averaging logits (if available).
        tokenizer, model = self._pipeline  # type: ignore[misc]
        texts = [item.title for item in items if item.title]
        if not texts:
            return 0.0
        encoded = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")  # type: ignore[operator]
        with torch.no_grad():  # type: ignore[attr-defined]
            outputs = model(**encoded)  # type: ignore[operator]
        logits = outputs.logits  # type: ignore[attr-defined]
        probs = torch.nn.functional.softmax(logits, dim=1)  # type: ignore[attr-defined]
        # FinBERT order: [negative, neutral, positive]
        scores = probs[:, 2] - probs[:, 0]
        return float(scores.mean().item())

    def _score_with_heuristic(self, items: List[models.Catalyst]) -> float:
        score = 0.0
        count = 0
        for item in items:
            text = item.title.lower()
            word_score = 0
            for token in _POSITIVE_LEXICON:
                if token in text:
                    word_score += 1
            for token in _NEGATIVE_LEXICON:
                if token in text:
                    word_score -= 1
            if word_score != 0:
                score += word_score
                count += 1
        if count == 0:
            return 0.0
        normalized = max(min(score / count, 3.0), -3.0) / 3.0
        return float(normalized)

    def _build_provenance(
        self,
        symbol: str,
        score: float,
        gate: str,
        reasons: List[str],
        items: List[models.Catalyst],
    ) -> models.AIProvenanceRecord:
        headlines = [item.title for item in items if item.title]
        return models.AIProvenanceRecord(
            symbol=symbol,
            ts=to_epoch_seconds(now_et()),
            model_name=self.settings.ai_model,
            inputs={"headlines": headlines},
            outputs={"score": score, "gate": gate, "reasons": reasons},
            delta_applied=score,
            notes="sentiment",
        )


