from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from google_weather import CurrentWeather, DailyWeather


TAKE_SHUTTLE = "셔틀"
TRAFFIC_ELEVATED = "셔틀"
TAKE_NJ_TRANSIT = "NJ 트랜짓"
TRAFFIC_PROFILE_SMOOTH = "smooth"
TRAFFIC_PROFILE_ELEVATED = "elevated"
TRAFFIC_PROFILE_TRANSIT = "transit"


@dataclass(frozen=True)
class DecisionResult:
    traffic_profile: str
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
            traffic_profile=TRAFFIC_PROFILE_TRANSIT,
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    if traffic_is_severe:
        return DecisionResult(
            traffic_profile=TRAFFIC_PROFILE_TRANSIT,
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    if traffic_is_elevated:
        return DecisionResult(
            traffic_profile=TRAFFIC_PROFILE_ELEVATED,
            delay_min=delay_min,
            transit_midpoint_min=transit_midpoint,
        )

    return DecisionResult(
        traffic_profile=TRAFFIC_PROFILE_SMOOTH,
        delay_min=delay_min,
        transit_midpoint_min=transit_midpoint,
    )


def recommendation_for_traffic_profile(traffic_profile: str) -> str:
    if traffic_profile == TRAFFIC_PROFILE_TRANSIT:
        return TAKE_NJ_TRANSIT
    if traffic_profile == TRAFFIC_PROFILE_ELEVATED:
        return TRAFFIC_ELEVATED
    return TAKE_SHUTTLE


def compose_reason(
    *,
    decision: DecisionResult,
    now: datetime,
    current_weather: CurrentWeather | None = None,
    daily_weather: DailyWeather | None = None,
) -> str:
    weather_profile = _classify_weather(current_weather=current_weather, daily_weather=daily_weather)
    variants = WEATHER_TRAFFIC_REASONS[(decision.traffic_profile, weather_profile)]
    return _choose_variant(variants, seed=_reason_seed(now, decision, weather_profile))


def _classify_weather(
    *,
    current_weather: CurrentWeather | None,
    daily_weather: DailyWeather | None,
) -> str:
    if current_weather is None and daily_weather is None:
        return "unavailable"

    condition_text = " ".join(
        item.condition.lower()
        for item in (current_weather, daily_weather)
        if item is not None and item.condition
    )
    precipitation = max(
        (
            value
            for value in (
                current_weather.precipitation_percent if current_weather else None,
                daily_weather.precipitation_percent if daily_weather else None,
            )
            if value is not None
        ),
        default=0,
    )
    current_feels_like = current_weather.feels_like_degrees if current_weather else None
    current_temp = current_weather.temperature_degrees if current_weather else None
    high = daily_weather.high_degrees if daily_weather else None
    low = daily_weather.low_degrees if daily_weather else None

    if precipitation >= 45 or any(
        marker in condition_text
        for marker in ("rain", "shower", "storm", "thunder", "snow", "sleet", "hail")
    ):
        return "wet"
    if _at_or_above((current_feels_like, current_temp, high), 85):
        return "hot"
    if _at_or_below((current_feels_like, current_temp, low), 35):
        return "cold"
    if "wind" in condition_text:
        return "windy"
    return "mild"


def _at_or_above(values: tuple[float | None, ...], threshold: float) -> bool:
    return any(value is not None and value >= threshold for value in values)


def _at_or_below(values: tuple[float | None, ...], threshold: float) -> bool:
    return any(value is not None and value <= threshold for value in values)


def _choose_variant(variants: tuple[str, ...], *, seed: str) -> str:
    seed_value = sum(ord(character) for character in seed)
    return variants[seed_value % len(variants)]


def _reason_seed(now: datetime, decision: DecisionResult, weather_profile: str) -> str:
    return f"{now.date().isoformat()}:{decision.traffic_profile}:{round(decision.delay_min)}:{weather_profile}"


WEATHER_TRAFFIC_REASONS: dict[tuple[str, str], tuple[str, ...]] = {
    ("smooth", "unavailable"): (
        "오늘 길이 꽤 순둥순둥해요. 날씨 정보는 잠깐 숨었지만 셔틀 타고 편하게 가도 좋겠습니다~ 🚌🌿✨",
        "교통이 얌전한 편이에요. 날씨는 직접 한 번만 확인하고 셔틀로 사뿐히 출발해요 🚌✨",
        "셔틀길이 귀엽게 잘 풀려 있어요. 날씨만 살짝 확인하고 가면 좋겠습니다 🌤️🚌",
    ),
    ("smooth", "mild"): (
        "날씨도 길도 착한 편이에요. 셔틀 타고 사뿐히 출발하면 딱 좋겠습니다 🚌🌿",
        "비 소식도 크지 않고 차도 얌전해요. 오늘 셔틀 조합 꽤 귀엽게 괜찮아요 ✨🚌",
        "이동 조건이 전체적으로 보송보송해요. 셔틀로 가볍게 슝 출발해요 🌤️🚌",
    ),
    ("smooth", "wet"): (
        "길은 괜찮은데 하늘이 촉촉 모드예요. 우산 챙기고 셔틀로 보송하게 가요 ☔🚌",
        "교통은 나쁘지 않은데 날씨가 살짝 장난칠 수 있어요. 젖지 않게 준비하고 셔틀 탑시다 🌧️✨",
        "차는 잘 빠지는 편이라 셔틀은 좋아요. 대신 우산 하나 꼭 챙겨요 ☔🚌",
    ),
    ("smooth", "hot"): (
        "길은 괜찮지만 햇살이 열일 중이에요. 물 챙기고 셔틀로 시원하게 가요 🧊🚌",
        "교통은 무난한데 체감온도가 높아요. 셔틀 기다릴 땐 그늘 쪽으로 쏙 들어가요 ☀️🕶️",
        "셔틀 흐름은 괜찮아요. 더위만 살짝 달래주면 오늘도 무난합니다 💧🚌",
    ),
    ("smooth", "cold"): (
        "길은 괜찮지만 공기가 쌀쌀해요. 따뜻하게 감싸고 셔틀 타러 가요 🧣🚌",
        "셔틀은 무난한 선택이에요. 밖에서 기다릴 때 춥지 않게 포근템 챙겨요 🧤✨",
        "교통은 얌전한 편이에요. 겉옷만 잘 챙기면 셔틀이 딱 좋아 보여요 🧥🚌",
    ),
    ("smooth", "windy"): (
        "차는 괜찮은데 바람이 살랑보다 조금 세요. 정류장에선 옷만 꼭 여며요 🌬️🚌",
        "길은 셔틀 편이고 바람이 살짝 변수예요. 머리카락만 잘 붙잡고 갑시다 💨✨",
        "교통은 편안한 쪽이에요. 바람만 조심하면 셔틀로 충분해요 🚌🌬️",
    ),
    ("elevated", "unavailable"): (
        "차가 살짝 느릿느릿하지만 아직 셔틀이 버틸 만해요. 날씨만 한 번 확인하고 커피랑 같이 출발해요 ☕🚌✨",
        "교통이 조금 답답해도 셔틀 선택은 아직 괜찮아요. 날씨 체크만 살짝 하고 가요 🚌🌤️",
        "셔틀길이 완전 빠르진 않지만 감당 가능한 정도예요. 날씨만 확인하고 얌전히 출발합시다 🚌✨",
    ),
    ("elevated", "mild"): (
        "차는 살짝 밀리지만 날씨가 착해서 셔틀 기다림도 괜찮아 보여요 🌿🚌",
        "길이 조금 느릿해도 날씨는 무난해요. 오늘은 셔틀로 귀엽게 버텨봅시다 ☕🚌",
        "교통은 살짝 답답하지만 날씨가 안정적이에요. 셔틀 선택 아직 좋아요 ✨🚌",
    ),
    ("elevated", "wet"): (
        "차도 살짝 밀리고 하늘도 촉촉해요. 그래도 환승길보다 셔틀이 더 포근해 보여요 ☔🚌",
        "교통과 비 소식이 둘 다 애매하지만, 셔틀에 앉아서 가는 쪽이 마음 편해요 🌧️🚌",
        "길도 날씨도 완벽하진 않아요. 우산 챙기고 셔틀로 안전하게 사뿐히 가요 ☔✨",
    ),
    ("elevated", "hot"): (
        "차가 조금 밀리고 더위도 있어요. 그래도 걷고 갈아타는 것보다 셔틀이 더 편해 보여요 🧊🚌",
        "더운 날에 교통도 살짝 답답해요. 물 챙기고 셔틀 에어컨을 믿어봅시다 💧🚌",
        "대기 시간이 덥게 느껴질 수 있어요. 그래도 계산상 셔틀이 아직 괜찮아요 ☀️🚌",
    ),
    ("elevated", "cold"): (
        "차는 조금 밀리지만 추운 날 환승 동선은 더 피곤해요. 셔틀로 포근하게 가요 🧣🚌",
        "쌀쌀해서 밖에서 오래 움직이면 힘들 수 있어요. 셔틀이 아직 든든합니다 🧤✨",
        "교통이 완전 좋진 않아도 추위까지 생각하면 셔틀 선택이 괜찮아요 🧥🚌",
    ),
    ("elevated", "windy"): (
        "차가 조금 밀리고 바람도 있어요. 그래도 환승보다 셔틀 대기가 더 단순해 보여요 🌬️🚌",
        "오늘은 길도 바람도 살짝 삐죽한 조합이에요. 그래도 셔틀이 아직 낫습니다 💨🚌",
        "바람 때문에 이동 동선을 줄이는 게 좋아 보여요. 셔틀로 얌전히 가요 🚌✨",
    ),
    ("transit", "unavailable"): (
        "셔틀길이 오늘은 꽤 삐끗했어요. 날씨는 따로 한 번 확인하고 NJ Transit으로 슝 가는 게 좋아요 🚆✨",
        "계산기 톡톡 해보니 NJ Transit이 더 이득이에요. 날씨만 체크하고 트랜짓으로 갑시다 🤓🚆",
        "오늘은 셔틀보다 트랜짓 쪽이 더 든든해요. 날씨 확인하고 NJ Transit으로 빠르게 움직여요 🚆💨",
    ),
    ("transit", "mild"): (
        "날씨가 무난해서 환승길도 크게 부담 없겠어요. 오늘은 NJ Transit으로 슝 가요 🚆✨",
        "교통이 셔틀 편이 아니라서, 날씨 괜찮을 때 NJ Transit으로 똑똑하게 가는 게 좋아요 🌿🚆",
        "밖으로 조금 움직이기 괜찮은 날씨예요. 오늘은 트랜짓 선택이 예쁩니다 🚆💫",
    ),
    ("transit", "wet"): (
        "비나 눈 가능성이 있어도 셔틀 지연이 더 큰 변수예요. 우산 챙기고 NJ Transit으로 가요 ☔🚆",
        "날씨가 애매하지만 교통이 더 문제예요. 방수 준비하고 트랜짓으로 보송하게 갑시다 🌧️🚆",
        "환승길이 조금 번거로워도 셔틀 지연을 피하는 게 이득이에요. 우산은 꼭 챙겨요 ☔✨",
    ),
    ("transit", "hot"): (
        "덥긴 하지만 셔틀 지연이 더 손해예요. 물 챙기고 NJ Transit으로 빠르게 슝 가요 💧🚆",
        "더운 날 오래 막힌 셔틀은 피곤할 수 있어요. 오늘은 트랜짓으로 시원하게 갑시다 🧊🚆",
        "체감온도는 신경 쓰이지만 시간 계산상 NJ Transit이 더 좋아 보여요 ☀️🚆",
    ),
    ("transit", "cold"): (
        "춥긴 해도 셔틀 지연이 커서 NJ Transit이 더 나아요. 따뜻하게 입고 출발해요 🧣🚆",
        "날씨는 쌀쌀하지만 교통이 더 큰 문제예요. 오늘은 트랜짓 쪽으로 사뿐히 가요 🧤🚆",
        "밖에서 조금 춥더라도 막힌 셔틀보다 NJ Transit이 나은 계산이에요 🧥✨",
    ),
    ("transit", "windy"): (
        "바람은 있지만 셔틀 지연이 더 부담이에요. 동선 짧게 잡고 NJ Transit으로 가요 🌬️🚆",
        "오늘은 바람보다 교통이 더 큰 변수예요. 트랜짓 선택이 더 든든해 보여요 💨🚆",
        "환승길 바람은 신경 쓰이지만, 시간상 NJ Transit이 더 낫겠습니다 🚆✨",
    ),
}
