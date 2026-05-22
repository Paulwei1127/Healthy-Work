from app.core.statistics import calculate_daily_statistics
from app.data.models import BreakRecord


def test_daily_statistics_only_counts_records_for_target_date() -> None:
    records = [
        BreakRecord(
            id="old",
            date="2026-05-20",
            start_time="2026-05-20T10:00:00",
            end_time="2026-05-20T10:10:00",
            duration_minutes=10,
            water_ml=300,
        ),
        BreakRecord(
            id="new",
            date="2026-05-21",
            start_time="2026-05-21T10:00:00",
            end_time="2026-05-21T10:05:00",
            duration_minutes=5,
            water_ml=200,
        ),
    ]

    statistics = calculate_daily_statistics(
        date="2026-05-21",
        work_minutes=45,
        break_records=records,
    )

    assert statistics.break_minutes == 5
    assert statistics.break_count == 1
    assert statistics.water_ml == 200
    assert statistics.average_work_session_minutes == 45
    assert statistics.basic_water_target_ml == 70
    assert statistics.ideal_water_target_ml == 94
    assert statistics.recommended_break_minutes == 4
