"""Recall log retention and eval limits."""

from pydantic import NonNegativeInt, PositiveInt

from mindgrid.core.config import AppSettings, env_field, settings_getter


class EvalSettings(AppSettings):
    recall_log_days: NonNegativeInt = env_field(
        "MINDGRID_RECALL_LOG_DAYS",
        90,
        doc="Days a question stays in the recall log (0 = do not log questions).",
    )
    max_cases: PositiveInt = env_field(
        "MINDGRID_EVAL_MAX_CASES", 500, doc="Most cases in one eval run."
    )
    judge_seconds: PositiveInt = env_field(
        "MINDGRID_EVAL_JUDGE_SECONDS", 120, doc="Longest wait for the judge on one case."
    )


get_settings = settings_getter(EvalSettings)
