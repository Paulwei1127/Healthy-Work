from app.core.scoring import (
    calculate_break_volume_score_delta,
    calculate_health_score,
    calculate_water_score_delta,
    calculate_work_session_score_delta,
    create_daily_summary,
    generate_health_suggestions,
)
from app.core.statistics import (
    DailyStatistics,
    calculate_basic_water_target_ml,
    calculate_ideal_water_target_ml,
    calculate_recommended_break_minutes,
)
from app.data.models import DailySummary
from app.ui.report_dialog import format_daily_summary_report


def _statistics(
    work_minutes: int,
    water_ml: int,
    break_minutes: int = 0,
    break_count: int = 0,
    average_work_session_minutes: float | None = None,
    longest_work_session_minutes: int | None = None,
) -> DailyStatistics:
    return DailyStatistics(
        date="2026-05-22",
        work_minutes=work_minutes,
        break_minutes=break_minutes,
        break_count=break_count,
        water_ml=water_ml,
        average_work_session_minutes=average_work_session_minutes,
        basic_water_target_ml=calculate_basic_water_target_ml(work_minutes),
        ideal_water_target_ml=calculate_ideal_water_target_ml(work_minutes),
        recommended_break_minutes=calculate_recommended_break_minutes(work_minutes),
        longest_work_session_minutes=longest_work_session_minutes,
        work_session_count=1 if longest_work_session_minutes is not None else 0,
    )


def test_zero_work_minutes_does_not_heavily_penalize_low_water() -> None:
    statistics = _statistics(work_minutes=0, water_ml=0)

    assert calculate_water_score_delta(statistics) == 0
    assert calculate_health_score(statistics) is None
    assert "尚未累積工作時間" in generate_health_suggestions(statistics)[0]


def test_short_work_minutes_do_not_produce_formal_health_score() -> None:
    statistics = _statistics(work_minutes=29, water_ml=0)

    summary = create_daily_summary(statistics)

    assert summary.health_score is None
    assert "今日工作紀錄較短，先不產生正式健康分數。" in summary.suggestions


def test_enough_work_minutes_produce_formal_health_score() -> None:
    statistics = _statistics(work_minutes=30, water_ml=100)

    assert isinstance(calculate_health_score(statistics), int)


def test_eight_work_hours_basic_water_target_is_met_at_750ml() -> None:
    statistics = _statistics(work_minutes=480, water_ml=750)

    assert statistics.basic_water_target_ml == 750
    assert statistics.ideal_water_target_ml == 1000
    assert calculate_water_score_delta(statistics) == 10


def test_eight_work_hours_ideal_water_target_is_met_at_1000ml() -> None:
    statistics = _statistics(work_minutes=480, water_ml=1000)

    assert calculate_water_score_delta(statistics) == 15


def test_eight_work_hours_below_40_percent_basic_water_target_is_heavily_penalized() -> None:
    statistics = _statistics(work_minutes=480, water_ml=299)

    assert calculate_water_score_delta(statistics) == -15


def test_four_work_hours_water_targets_are_proportional() -> None:
    assert calculate_basic_water_target_ml(240) == 375
    assert calculate_ideal_water_target_ml(240) == 500


def test_water_targets_have_no_daily_cap_for_long_workdays() -> None:
    assert calculate_basic_water_target_ml(960) == 1500
    assert calculate_ideal_water_target_ml(960) == 2000
    assert calculate_basic_water_target_ml(1200) > 1500
    assert calculate_ideal_water_target_ml(1200) > 2000


def test_short_work_time_does_not_create_unreasonable_water_penalty() -> None:
    statistics = _statistics(work_minutes=10, water_ml=0)

    assert calculate_water_score_delta(statistics) == 0
    suggestions = generate_health_suggestions(statistics)
    assert "今日工作紀錄較短，先不產生正式健康分數。" in suggestions
    assert any("工作時間較短" in suggestion for suggestion in suggestions)


def test_exact_work_session_scoring_bands() -> None:
    assert (
        calculate_work_session_score_delta(
            _statistics(60, 0, longest_work_session_minutes=60)
        )
        == 10
    )
    assert (
        calculate_work_session_score_delta(
            _statistics(75, 0, longest_work_session_minutes=75)
        )
        == -3
    )
    assert (
        calculate_work_session_score_delta(
            _statistics(100, 0, longest_work_session_minutes=100)
        )
        == -10
    )
    assert (
        calculate_work_session_score_delta(
            _statistics(121, 0, longest_work_session_minutes=121)
        )
        == -20
    )


def test_average_work_session_fallback_suggestion_is_explicitly_estimated() -> None:
    statistics = _statistics(
        work_minutes=160,
        water_ml=300,
        break_minutes=10,
        break_count=2,
        average_work_session_minutes=80,
    )

    suggestions = generate_health_suggestions(statistics)

    assert any("推估" in suggestion for suggestion in suggestions)
    assert any("平均工作區段約 80 分鐘" in suggestion for suggestion in suggestions)


def test_precise_work_session_suggestion_does_not_use_estimated_wording() -> None:
    statistics = _statistics(
        work_minutes=200,
        water_ml=400,
        break_minutes=20,
        break_count=2,
        average_work_session_minutes=150,
        longest_work_session_minutes=55,
    )

    suggestions = generate_health_suggestions(statistics)

    assert calculate_work_session_score_delta(statistics) == 10
    assert any("最長連續工作 55 分鐘" in suggestion for suggestion in suggestions)
    assert not any("推估" in suggestion for suggestion in suggestions)


def test_water_suggestion_contains_work_time_targets_and_actual_water() -> None:
    statistics = _statistics(work_minutes=480, water_ml=620)

    suggestion = generate_health_suggestions(statistics)[0]

    assert "8 小時" in suggestion
    assert "750 ml" in suggestion
    assert "1000 ml" in suggestion
    assert "620 ml" in suggestion


def test_break_volume_uses_work_time_proportional_target() -> None:
    statistics = _statistics(work_minutes=480, water_ml=750, break_minutes=20)

    assert statistics.recommended_break_minutes == 40
    assert calculate_break_volume_score_delta(statistics) == -3
    assert "建議休息約 40 分鐘" in generate_health_suggestions(statistics)[2]


def test_daily_summary_includes_new_scoring_targets() -> None:
    statistics = _statistics(
        work_minutes=240,
        water_ml=400,
        break_minutes=20,
        break_count=2,
        average_work_session_minutes=120,
    )

    summary = create_daily_summary(statistics)

    assert summary.basic_water_target_ml == 375
    assert summary.ideal_water_target_ml == 500
    assert summary.recommended_break_minutes == 20
    assert summary.work_session_count == 0
    assert summary.suggestions


def test_text_report_uses_friendly_missing_work_session_text() -> None:
    summary = DailySummary(
        date="2026-05-22",
        work_minutes=120,
        break_minutes=0,
        break_count=0,
        water_ml=0,
        average_work_session_minutes=None,
        health_score=60,
        suggestions=[],
    )

    report = format_daily_summary_report(summary)

    assert "N/A" not in report
    assert "平均每次工作時長：尚無工作區段紀錄" in report
    assert "最長連續工作：尚無工作區段紀錄" in report
    assert "工作區段次數：尚無工作區段紀錄" in report
    assert "健康度評分：60 / 100" in report


def test_text_report_says_not_worked_when_work_minutes_are_zero() -> None:
    summary = DailySummary(
        date="2026-05-22",
        work_minutes=0,
        break_minutes=0,
        break_count=0,
        water_ml=0,
        average_work_session_minutes=None,
        health_score=None,
        suggestions=[],
    )

    report = format_daily_summary_report(summary)

    assert "平均每次工作時長：今天尚未工作" in report
    assert "最長連續工作：今天尚未工作" in report
    assert "工作區段次數：今天尚未工作" in report
    assert "健康度評分：今天尚未工作" in report
    assert "60 / 100" not in report


def test_text_report_says_not_enough_data_for_short_work() -> None:
    summary = DailySummary(
        date="2026-05-22",
        work_minutes=20,
        break_minutes=0,
        break_count=0,
        water_ml=0,
        average_work_session_minutes=None,
        health_score=None,
        suggestions=[],
    )

    report = format_daily_summary_report(summary)

    assert "健康度評分：資料較少，暫不評分" in report
    assert "60 / 100" not in report
    assert "None" not in report


def test_text_report_ignores_legacy_score_when_no_work_was_recorded() -> None:
    summary = DailySummary(
        date="2026-05-22",
        work_minutes=0,
        break_minutes=0,
        break_count=0,
        water_ml=0,
        average_work_session_minutes=None,
        health_score=60,
        suggestions=[],
    )

    report = format_daily_summary_report(summary)

    assert "健康度評分：今天尚未工作" in report
    assert "60 / 100" not in report
    assert "N/A" not in report
    assert "None" not in report


def test_text_report_ignores_legacy_score_when_work_data_is_too_short() -> None:
    summary = DailySummary(
        date="2026-05-22",
        work_minutes=20,
        break_minutes=0,
        break_count=0,
        water_ml=0,
        average_work_session_minutes=None,
        health_score=60,
        suggestions=[],
    )

    report = format_daily_summary_report(summary)

    assert "健康度評分：資料較少，暫不評分" in report
    assert "60 / 100" not in report
    assert "N/A" not in report
    assert "None" not in report


def test_text_report_shows_score_when_work_data_is_enough() -> None:
    summary = DailySummary(
        date="2026-05-22",
        work_minutes=30,
        break_minutes=0,
        break_count=0,
        water_ml=0,
        average_work_session_minutes=None,
        health_score=72,
        suggestions=[],
    )

    report = format_daily_summary_report(summary)

    assert "健康度評分：72 / 100" in report
