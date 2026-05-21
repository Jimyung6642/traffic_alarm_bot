from __future__ import annotations

from dataclasses import dataclass


TAKE_SHUTTLE = "셔틀"
TRAFFIC_ELEVATED = "셔틀"
TAKE_NJ_TRANSIT = "NJ 트랜짓"


@dataclass(frozen=True)
class DecisionResult:
    recommendation: str
    reason: str
    delay_min: float
    transit_midpoint_min: float


def make_decision(
    *,
    current_drive_min: float,
    baseline_min: float,
    transit_min_low: float,
    transit_min_high: float,
    warning_delay_min: float,
    severe_delay_min: float,
    transit_advantage_buffer_min: float,
) -> DecisionResult:
    delay_min = current_drive_min - baseline_min
    transit_midpoint = (transit_min_low + transit_min_high) / 2.0

    transit_is_meaningfully_better = current_drive_min > transit_midpoint + transit_advantage_buffer_min
    traffic_is_severe = delay_min >= severe_delay_min
    traffic_is_elevated = warning_delay_min < delay_min < severe_delay_min

    if transit_is_meaningfully_better:
        return DecisionResult(
            recommendation=TAKE_NJ_TRANSIT,
            reason="계산기 살짝 톡톡 해봤더니 NJ Transit이 훨씬 이득이에요. 오늘은 트랜짓 타고 슝 가요~ 🤓🚆✨",
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    if traffic_is_severe:
        return DecisionResult(
            recommendation=TAKE_NJ_TRANSIT,
            reason="오늘 셔틀길이 많이 삐끗했어요. NJ Transit으로 갈아타고 시간 지켜봅시다~ 🚆💨",
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    if traffic_is_elevated:
        return DecisionResult(
            recommendation=TRAFFIC_ELEVATED,
            reason="차가 살짝 느릿느릿하지만 아직 셔틀이 버틸 만해요. 커피 한 모금 하고 셔틀로 가요 ☕🚌✨",
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    return DecisionResult(
        recommendation=TAKE_SHUTTLE,
        reason="오늘 길이 꽤 순둥순둥해요. 셔틀 타고 편하게 가도 좋겠습니다~ 🚌🌿✨",
        delay_min=delay_min,
        transit_midpoint_min=transit_midpoint,
    )
