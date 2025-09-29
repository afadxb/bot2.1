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

    def analyze(self, news_items: Iterable[models.NewsItem]) -> Dict[str, SentimentResult]:
        news_map: Dict[str, List[models.NewsItem]] = {}
        for item in news_items:
            news_map.setdefault(item.symbol, []).append(item)

        results: Dict[str, SentimentResult] = {}
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
            self._persist(symbol, score, gate, reasons, items)

        return results

    def _score_with_finbert(self, items: List[models.NewsItem]) -> float:
        # Simplified FinBERT scoring averaging logits (if available).
        tokenizer, model = self._pipeline  # type: ignore[misc]
        texts = [item.headline for item in items if item.headline]
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

    def _score_with_heuristic(self, items: List[models.NewsItem]) -> float:
        score = 0.0
        count = 0
        for item in items:
            text = item.headline.lower()
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

    def _persist(
        self,
        symbol: str,
        score: float,
        gate: str,
        reasons: List[str],
        items: List[models.NewsItem],
    ) -> None:
        payload = {
            "symbol": symbol,
            "run_ts": to_epoch_seconds(now_et()),
            "raw_text": "\n".join(item.headline for item in items if item.headline),
            "model": self.settings.ai_model,
            "score": score,
            "gate": gate,
            "reasons": reasons,
        }
        self.db.execute(
            "INSERT INTO ai_provenance(symbol, run_ts, raw_text, model, score, gate, reasons) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                payload["symbol"],
                payload["run_ts"],
                payload["raw_text"],
                payload["model"],
                payload["score"],
                payload["gate"],
                json.dumps(payload["reasons"]),
            ),
        )


import json  # placed at bottom to avoid circular import during module load
