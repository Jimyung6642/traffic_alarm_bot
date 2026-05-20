from __future__ import annotations

from dataclasses import dataclass


TAKE_SHUTTLE = "Take shuttle"
TRAFFIC_ELEVATED = "Traffic elevated, but shuttle still acceptable"
TAKE_NJ_TRANSIT = "Take NJ Transit"


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
            reason="계산기 두드려보니 셔틀보다 NJ Transit이 훨씬 이득이에요. 오늘은 기차 쪽으로 갑시다~ 🤓🚆",
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    if traffic_is_severe:
        return DecisionResult(
            recommendation=TAKE_NJ_TRANSIT,
            reason="오늘은 셔틀도 더위를 먹었는지 너무 느리네요. NJ Transit 타세요~ 🤓🚆",
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    if traffic_is_elevated:
        return DecisionResult(
            recommendation=TRAFFIC_ELEVATED,
            reason="차가 조금 밀리긴 하는데 아직 셔틀이 버틸 만해요. 커피 한 모금 마시고 셔틀 가시죠 ☕🚌",
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    return DecisionResult(
        recommendation=TAKE_SHUTTLE,
        reason="오늘은 길이 꽤 얌전해요. 셔틀 타도 무난하게 갈 수 있겠습니다~ 🚌✨",
        delay_min=delay_min,
        transit_midpoint_min=transit_midpoint,
    )
