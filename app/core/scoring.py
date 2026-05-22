"""Rule-based health score and suggestion generation."""

from __future__ import annotations

from app.core.statistics import DailyStatistics
from app.data.models import DailySummary


BASE_HEALTH_SCORE = 60
MIN_HEALTH_SCORE = 0
MAX_HEALTH_SCORE = 100

BASIC_DAILY_WATER_ML = 1500
IDEAL_DAILY_WATER_ML = 2000
AWAKE_HOURS_PER_DAY = 16
MIN_WORK_MINUTES_FOR_WATER_SCORING = 30
MIN_WORK_MINUTES_FOR_HEALTH_SCORE = 30

WORK_SESSION_TARGET_MINUTES = 60
WORK_SESSION_MINOR_LIMIT_MINUTES = 90
WORK_SESSION_MAJOR_LIMIT_MINUTES = 120
BREAK_MINUTES_PER_WORK_HOUR = 5


def calculate_health_score(statistics: DailyStatistics) -> int | None:
    """Calculate the health score using proportional water and rest rules."""

    if statistics.work_minutes < MIN_WORK_MINUTES_FOR_HEALTH_SCORE:
        return None

    score = BASE_HEALTH_SCORE
    score += calculate_water_score_delta(statistics)
    score += calculate_work_session_score_delta(statistics)
    score += calculate_break_volume_score_delta(statistics)
    return clamp_score(score)


def calculate_water_score_delta(statistics: DailyStatistics) -> int:
    """Score water intake against targets scaled by recorded work time."""

    if statistics.work_minutes < MIN_WORK_MINUTES_FOR_WATER_SCORING:
        return 0

    basic_target = statistics.basic_water_target_ml
    ideal_target = statistics.ideal_water_target_ml
    if basic_target <= 0 or ideal_target <= 0:
        return 0

    if statistics.water_ml >= ideal_target:
        return 15
    if statistics.water_ml >= basic_target:
        return 10
    if statistics.water_ml >= basic_target * 0.7:
        return 0
    if statistics.water_ml >= basic_target * 0.4:
        return -8
    return -15


def calculate_work_session_score_delta(statistics: DailyStatistics) -> int:
    """Score rest rhythm, preferring exact work sessions when available."""

    if statistics.work_minutes == 0:
        return 0

    if statistics.longest_work_session_minutes is not None:
        return _score_longest_work_session(statistics.longest_work_session_minutes)

    average_work_minutes = statistics.average_work_session_minutes
    if average_work_minutes is None:
        if statistics.work_minutes > WORK_SESSION_TARGET_MINUTES:
            return -25
        return 0

    return _score_longest_work_session(average_work_minutes)


def calculate_break_volume_score_delta(statistics: DailyStatistics) -> int:
    """Score total break time as a secondary target scaled by work time."""

    if statistics.work_minutes < MIN_WORK_MINUTES_FOR_WATER_SCORING:
        return 0

    target = statistics.recommended_break_minutes
    if target <= 0:
        return 0

    if statistics.break_minutes >= target:
        return 10
    if statistics.break_minutes >= target * 0.5:
        return -3
    return -10


def generate_health_suggestions(statistics: DailyStatistics) -> list[str]:
    """Generate concrete rule-based health suggestions."""

    suggestions = [
        _build_water_suggestion(statistics),
        _build_work_session_suggestion(statistics),
        _build_break_volume_suggestion(statistics),
        "眼睛休息可以採用 20-20-20：每 20 分鐘看向遠方 20 秒。",
        "休息時建議伸展肩頸、起身走動，順手補充水分。",
    ]
    if 0 < statistics.work_minutes < MIN_WORK_MINUTES_FOR_HEALTH_SCORE:
        suggestions.insert(0, "今日工作紀錄較短，先不產生正式健康分數。")
    return suggestions


def create_daily_summary(statistics: DailyStatistics) -> DailySummary:
    """Build a DailySummary from calculated statistics and scoring rules."""

    return DailySummary(
        date=statistics.date,
        work_minutes=statistics.work_minutes,
        break_minutes=statistics.break_minutes,
        break_count=statistics.break_count,
        water_ml=statistics.water_ml,
        average_work_session_minutes=statistics.average_work_session_minutes,
        health_score=calculate_health_score(statistics),
        basic_water_target_ml=statistics.basic_water_target_ml,
        ideal_water_target_ml=statistics.ideal_water_target_ml,
        recommended_break_minutes=statistics.recommended_break_minutes,
        longest_work_session_minutes=statistics.longest_work_session_minutes,
        work_session_count=statistics.work_session_count,
        suggestions=generate_health_suggestions(statistics),
    )


def clamp_score(score: int) -> int:
    """Limit score to the supported 0-100 range."""

    return max(MIN_HEALTH_SCORE, min(MAX_HEALTH_SCORE, int(score)))


def _score_longest_work_session(work_session_minutes: float) -> int:
    if work_session_minutes <= WORK_SESSION_TARGET_MINUTES:
        return 10
    if work_session_minutes <= WORK_SESSION_MINOR_LIMIT_MINUTES:
        return -3
    if work_session_minutes <= WORK_SESSION_MAJOR_LIMIT_MINUTES:
        return -10
    return -20


def _build_water_suggestion(statistics: DailyStatistics) -> str:
    if statistics.work_minutes == 0:
        return (
            f"今天尚未累積工作時間，因此不計算工作期間喝水目標；"
            f"目前記錄 {statistics.water_ml} ml。"
        )

    work_text = _format_duration(statistics.work_minutes)
    base = (
        f"你今天工作 {work_text}，工作期間基本喝水目標約 "
        f"{statistics.basic_water_target_ml} ml、理想目標約 "
        f"{statistics.ideal_water_target_ml} ml；目前記錄 {statistics.water_ml} ml，"
    )

    if statistics.work_minutes < MIN_WORK_MINUTES_FOR_WATER_SCORING:
        return base + "工作時間較短，先不因喝水量扣分，保持順手補水即可。"
    if statistics.water_ml >= statistics.ideal_water_target_ml:
        return base + "已達理想目標，工作期間水分補充不錯。"
    if statistics.water_ml >= statistics.basic_water_target_ml:
        return base + "已達基本目標，可以再補一杯水接近理想狀態。"
    if statistics.water_ml >= statistics.basic_water_target_ml * 0.7:
        return base + "接近基本目標，可以再補一杯水。"
    return base + "低於基本目標，建議接下來主動補充水分。"


def _build_work_session_suggestion(statistics: DailyStatistics) -> str:
    if statistics.work_minutes == 0:
        return "今天尚未累積工作時間，暫不評估連續工作節奏。"

    if statistics.longest_work_session_minutes is not None:
        longest = statistics.longest_work_session_minutes
        if longest <= WORK_SESSION_TARGET_MINUTES:
            return (
                f"今天最長連續工作 {longest} 分鐘，符合 60 分鐘內休息的目標；"
                "可以提早休息，讓節奏更穩。"
            )
        if longest <= WORK_SESSION_MINOR_LIMIT_MINUTES:
            return (
                f"今天最長連續工作 {longest} 分鐘，略高於 60 分鐘目標；"
                "下次可以在提醒出現時先休息一下。"
            )
        return (
            f"今天最長連續工作 {longest} 分鐘，偏長；"
            "建議連續工作 60 分鐘內安排短休息。"
        )

    average = statistics.average_work_session_minutes
    if average is None:
        return (
            f"目前沒有休息紀錄，只能判斷你今天已工作 {_format_duration(statistics.work_minutes)}；"
            "可以提早休息，但不建議連續工作超過 60 分鐘。"
        )

    average_minutes = round(average)
    if average <= WORK_SESSION_TARGET_MINUTES:
        return (
            f"目前只能用平均值推估，你的平均工作區段約 {average_minutes} 分鐘，"
            "大致符合 60 分鐘內休息的目標；可以提早休息，維持穩定節奏。"
        )
    if average <= WORK_SESSION_MINOR_LIMIT_MINUTES:
        return (
            f"目前只能用平均值推估，你的平均工作區段約 {average_minutes} 分鐘，"
            "可能略長；建議連續工作 60 分鐘內安排短休息。"
        )
    return (
        f"目前只能用平均值推估，你的平均工作區段約 {average_minutes} 分鐘，"
        "可能偏長；建議避免連續工作超過 60 分鐘。"
    )


def _build_break_volume_suggestion(statistics: DailyStatistics) -> str:
    if statistics.work_minutes == 0:
        return "今天尚未累積工作時間，因此不計算休息總量目標。"

    target = statistics.recommended_break_minutes
    if statistics.work_minutes < MIN_WORK_MINUTES_FOR_WATER_SCORING:
        return (
            f"今天工作時間較短，以每工作 1 小時至少休息 {BREAK_MINUTES_PER_WORK_HOUR} 分鐘估算，"
            f"建議休息約 {target} 分鐘；目前記錄 {statistics.break_minutes} 分鐘。"
        )

    base = (
        f"以每工作 1 小時至少休息 {BREAK_MINUTES_PER_WORK_HOUR} 分鐘估算，"
        f"今天建議休息約 {target} 分鐘；目前記錄 {statistics.break_minutes} 分鐘，"
    )
    if statistics.break_minutes >= target:
        return base + "休息總量合理。"
    return base + "休息總量偏少，可以增加短暫走動與眼睛休息。"


def _format_duration(minutes: int) -> str:
    normalized = max(0, int(minutes))
    hours, remaining_minutes = divmod(normalized, 60)
    if hours and remaining_minutes:
        return f"{hours} 小時 {remaining_minutes} 分鐘"
    if hours:
        return f"{hours} 小時"
    return f"{remaining_minutes} 分鐘"
