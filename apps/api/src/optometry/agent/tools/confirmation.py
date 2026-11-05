"""Atomic one-time confirmations for agent write operations."""

from datetime import UTC, datetime
from decimal import Decimal
from secrets import token_urlsafe
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field
from redis import Redis
from redis.exceptions import RedisError

CONFIRMATION_TTL_SECONDS = 300
Action = Literal["book", "cancel"]


# atomically approves a pending confirmation
_APPROVE_SCRIPT = """
-- confirmation:approve
local pending_key = KEYS[1]
local approved_key = KEYS[2]
local patient_id = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

local raw = redis.call("GET", pending_key)
if not raw then
    return 0
end

local record = cjson.decode(raw)
if record.patient_id ~= patient_id then
    return 0
end

local stored = redis.call(
    "SET", approved_key, raw, "EX", ttl, "NX"
)
if not stored then
    return 0
end

redis.call("DEL", pending_key)
return 1
"""


# atomically validates and consumes an approval
_CONSUME_SCRIPT = """
-- confirmation:consume
local approved_key = KEYS[1]
local patient_id = tonumber(ARGV[1])
local action = ARGV[2]

local raw = redis.call("GET", approved_key)
if not raw then
    return nil
end

local record = cjson.decode(raw)

if record.patient_id ~= patient_id then
    return nil
end

if record.action ~= action then
    return nil
end

redis.call("DEL", approved_key)
return raw
"""


class BookingDetails(BaseModel):
    model_config = ConfigDict(frozen=True)

    clinic_id: int = Field(gt=0)
    optometrist_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    start_at: datetime
    appointment_price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class CancellationDetails(BaseModel):
    model_config = ConfigDict(frozen=True)

    appointment_id: int = Field(gt=0)


class ConfirmationRecord(BaseModel):
    patient_id: int = Field(gt=0)
    action: Action
    details: dict[str, Any]


def _key(stage: str, token: str) -> str:
    return f"agent:confirmation:{stage}:{token}"


def prepare_confirmation(
    *,
    client: Redis,
    patient_id: int,
    action: Action,
    details: BookingDetails | CancellationDetails,
) -> str:
    if patient_id <= 0:
        raise ValueError("An authenticated patient is required")

    if (action == "book") != isinstance(details, BookingDetails):
        raise ValueError("Confirmation details do not match the action")

    if isinstance(details, BookingDetails):
        if details.start_at.tzinfo is None or details.start_at.utcoffset() is None:
            raise ValueError("Booking time must include a timezone offset")

        details = details.model_copy(
            update={"start_at": details.start_at.astimezone(UTC)}
        )

    record = ConfirmationRecord(
        patient_id=patient_id,
        action=action,
        details=details.model_dump(mode="json"),
    )

    token = token_urlsafe(32)

    try:
        stored = client.set(
            _key("pending", token),
            record.model_dump_json(),
            ex=CONFIRMATION_TTL_SECONDS,
            nx=True,
        )
    except RedisError as exc:
        raise RuntimeError("Confirmation storage is unavailable") from exc

    if not stored:
        raise RuntimeError("Could not create confirmation")

    return token


def confirm_request(
    *,
    client: Redis,
    patient_id: int,
    token: str,
) -> bool:
    if patient_id <= 0 or not token:
        return False

    try:
        result = cast(
            int,
            client.eval(
                _APPROVE_SCRIPT,
                2,
                _key("pending", token),
                _key("approved", token),
                str(patient_id),
                str(CONFIRMATION_TTL_SECONDS),
            ),
        )
    except RedisError as exc:
        raise RuntimeError("Confirmation storage is unavailable") from exc

    return result == 1


def consume_confirmation(
    *,
    client: Redis,
    patient_id: int,
    token: str,
    action: Action,
) -> BookingDetails | CancellationDetails:
    if patient_id <= 0 or not token:
        raise PermissionError("Authenticated, approved action required")

    try:
        raw = cast(
            bytes | str | None,
            client.eval(
                _CONSUME_SCRIPT,
                1,
                _key("approved", token),
                str(patient_id),
                action,
            ),
        )
    except RedisError as exc:
        raise RuntimeError("Confirmation storage is unavailable") from exc

    if raw is None:
        raise PermissionError("Confirmation missing, expired, or invalid")

    record = ConfirmationRecord.model_validate_json(raw)

    if action == "book":
        return BookingDetails.model_validate(record.details)

    return CancellationDetails.model_validate(record.details)
