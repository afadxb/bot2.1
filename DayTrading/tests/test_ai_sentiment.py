from __future__ import annotations

from intraday.ai.sentiment import SentimentAnalyzer
from intraday.storage import models
from intraday.utils.time import now_et, to_epoch_seconds


def test_sentiment_heuristic_scores(settings, db):
    analyzer = SentimentAnalyzer(settings, db)
    news = [
        models.NewsItem(
            symbol="AAPL",
            source="test",
            headline="Company announces strong upgrade and record growth",
            url="",
            ts=to_epoch_seconds(now_et()),
        ),
        models.NewsItem(
            symbol="TSLA",
            source="test",
            headline="Manufacturer faces lawsuit and weak outlook",
            url="",
            ts=to_epoch_seconds(now_et()),
        ),
    ]
    result = analyzer.analyze(news)
    assert result["AAPL"].score > 0
    assert result["TSLA"].score < 0

    rows = db.execute("SELECT COUNT(*) as c FROM ai_provenance").fetchone()["c"]
    assert rows == 2
