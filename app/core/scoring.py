"""Rule-based health score and suggestion generation."""

from __future__ import annotations

from app.core.statistics import DailyStatistics
from app.data.models import DailySummary


BASE_HEALTH_SCORE = 60
MIN_HEALTH_SCORE = 0
MAX_HEALTH_SCORE = 100


def calculate_health_score(statistics: DailyStatistics) -> int:
    """Calculate the MVP health score using the requested rule set."""

    score = BASE_HEALTH_SCORE
    average_work_minutes = statistics.average_work_session_minutes

    if statistics.break_count >= 3:
        score += 15
    if statistics.water_ml >= 1500:
        score += 15
    if average_work_minutes is not None and average_work_minutes <= 60:
        score += 10
    if statistics.break_minutes >= 20:
        score += 10

    if statistics.break_count == 0:
        score -= 25
    if statistics.water_ml < 500:
        score -= 15
    if average_work_minutes is not None and average_work_minutes > 120:
        score -= 20
    if statistics.break_minutes < 10:
        score -= 10

    return clamp_score(score)


def generate_health_suggestions(statistics: DailyStatistics) -> list[str]:
    """Generate concise rule-based health suggestions."""

    suggestions: list[str] = []
    average_work_minutes = statistics.average_work_session_minutes

    if statistics.break_count == 0:
        suggestions.append("今天還沒有休息紀錄，建議安排短休息。")
    elif statistics.break_count >= 3:
        suggestions.append("今天休息頻率良好。")
    else:
        suggestions.append("建議增加休息次數，讓工作節奏更穩定。")

    if statistics.water_ml >= 1500:
        suggestions.append("今天喝水量充足。")
    elif statistics.water_ml < 500:
        suggestions.append("今天喝水量偏低，建議增加喝水量。")
    else:
        suggestions.append("可以再多補充一些水分。")

    if average_work_minutes is None:
        if statistics.work_minutes > 0:
            suggestions.append("建議避免連續工作太久，至少每 60 分鐘休息一次。")
    elif average_work_minutes > 120:
        suggestions.append("長時間工作偏多，建議增加短休息。")
    elif average_work_minutes > 60:
        suggestions.append("建議避免連續工作超過 60 分鐘。")
    else:
        suggestions.append("今天平均工作時段控制得不錯。")

    if statistics.break_minutes >= 20:
        suggestions.append("今天休息總時間達到基本目標。")
    else:
        suggestions.append("今天休息時間偏少，建議增加短暫走動與眼睛休息。")

    suggestions.append("眼睛休息可以採用 20-20-20：每 20 分鐘看向遠方 20 秒。")
    suggestions.append("休息時建議伸展肩頸、起身走動，順手補充水分。")

    if not suggestions:
        suggestions.append("今天整體工作節奏不錯。")

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
        suggestions=generate_health_suggestions(statistics),
    )


def clamp_score(score: int) -> int:
    """Limit score to the supported 0-100 range."""

    return max(MIN_HEALTH_SCORE, min(MAX_HEALTH_SCORE, int(score)))
