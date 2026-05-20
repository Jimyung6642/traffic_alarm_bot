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
            reason="Current shuttle estimate is meaningfully longer than your configured NJ Transit estimate.",
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    if traffic_is_severe:
        return DecisionResult(
            recommendation=TAKE_NJ_TRANSIT,
            reason="Traffic is much heavier than your normal shuttle baseline.",
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    if traffic_is_elevated:
        return DecisionResult(
            recommendation=TRAFFIC_ELEVATED,
            reason="Traffic is elevated but not severe enough to strongly prefer NJ Transit.",
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    return DecisionResult(
        recommendation=TAKE_SHUTTLE,
        reason="Traffic is close to your normal shuttle baseline.",
        delay_min=delay_min,
        transit_midpoint_min=transit_midpoint,
    )
