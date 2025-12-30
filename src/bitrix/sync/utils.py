from datetime import datetime, timedelta
from typing import Sequence

from src.db.models import Stage


def format_stage_changing(all_stages: Sequence[Stage], from_stage_id: int, to_stage_id: int) -> str:
    stage_message = ""
    stage_icon = "✅"
    for stage in all_stages:
        if stage.id == from_stage_id:
            stage_message += f"{'❇️' if stage_icon == '✅' else '⏫'}{stage.title}\n"
        else:
            stage_message += f"{stage_icon}{stage.title}\n"

        if stage.id == to_stage_id:
            stage_icon = "🔄"

    return stage_message


def calc_work_hours(start_time: datetime, now_time: datetime, weekends: list[int], start_wh: int, end_wh: int) -> float:
    if now_time <= start_time:
        return 0.0

    hours_in_full_day = end_wh - start_wh
    hours = 0.0

    if start_time.date() == now_time.date():
        if start_time.weekday() in weekends:
            return 0.0

        st_t = max(start_time, start_time.replace(hour=start_wh, minute=0, second=0, microsecond=0))
        en_t = min(now_time, now_time.replace(hour=end_wh, minute=0, second=0, microsecond=0))

        if st_t >= en_t:
            return 0.0

        hours += (en_t - st_t).total_seconds() / 3600
        return hours

    if start_time.weekday() not in weekends:  # first day
        st_t = max(start_time, start_time.replace(hour=start_wh, minute=0, second=0, microsecond=0))
        en_t = start_time.replace(hour=end_wh, minute=0, second=0, microsecond=0)
        if st_t < en_t:
            hours += (en_t - st_t).total_seconds() / 3600

    if now_time.weekday() not in weekends:  # last day
        st_t = now_time.replace(hour=start_wh, minute=0, second=0, microsecond=0)
        en_t = min(now_time, now_time.replace(hour=end_wh, minute=0, second=0, microsecond=0))
        if st_t < en_t:
            hours += (en_t - st_t).total_seconds() / 3600

    current_time = start_time + timedelta(days=1)
    while current_time.date() < now_time.date():
        if current_time.weekday() not in weekends:
            hours += hours_in_full_day
        current_time += timedelta(days=1)

    return hours
