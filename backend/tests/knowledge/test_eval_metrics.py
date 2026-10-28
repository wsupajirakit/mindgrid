"""Eval metrics: matching, ranking scores, abstention."""

from mindgrid.knowledge.evals import metrics


def test_matching_by_title_or_heading() -> None:
    assert metrics.matches("macro", "Macro notes.md", "Rates")
    assert metrics.matches("macro#rates", "Macro notes.md", "Rates")
    assert not metrics.matches("macro#credit", "Macro notes.md", "Rates")


def test_ranked_scores() -> None:
    s = metrics.score(["#rates"], [("m", "Credit"), ("m", "Rates")], k=5)
    assert (s.hit, s.recall, s.mrr) == (1.0, 1.0, 0.5)
    assert 0 < s.ndcg < 1
    miss = metrics.score(["#rates"], [("m", "Credit")], k=5)
    assert (miss.hit, miss.mrr, miss.ndcg) == (0.0, 0.0, 0.0)


def test_off_topic_case_rewards_returning_nothing() -> None:
    assert metrics.score([], [], k=5).abstained is True
    assert metrics.score([], [("m", "Rates")], k=5).abstained is False


def test_summary_separates_on_and_off_topic() -> None:
    scores = [
        metrics.score(["#rates"], [("m", "Rates")], k=5),
        metrics.score([], [], k=5),
        metrics.score([], [("m", "x")], k=5),
    ]
    out = metrics.summary(scores)
    assert (out["cases"], out["hit_at_k"], out["mrr"], out["abstention"]) == (3, 1.0, 1.0, 0.5)
