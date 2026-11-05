"""Tests preventing false appointment confirmations."""

from optometry.agent.conversations import (
    CONFIRMATION_MESSAGE,
    enforce_chat_write_boundary,
)


# checks typing confirm cannot finalize a booking
def test_chat_confirm_does_not_book_appointment() -> None:
    result = enforce_chat_write_boundary(
        patient_message="confirm",
        assistant_response=("Your appointment has been confirmed for tomorrow."),
    )

    assert result == CONFIRMATION_MESSAGE
    assert "has not been booked" in result


# checks false booking success claims are blocked
def test_chat_rejects_false_booking_success() -> None:
    result = enforce_chat_write_boundary(
        patient_message="Thanks",
        assistant_response="Your appointment has been booked.",
    )

    assert result == CONFIRMATION_MESSAGE


# checks false cancellation success claims are blocked
def test_chat_rejects_false_cancellation_success() -> None:
    result = enforce_chat_write_boundary(
        patient_message="Cancel my appointment",
        assistant_response="Your appointment has been cancelled.",
    )

    assert result == CONFIRMATION_MESSAGE


# checks ordinary responses are preserved
def test_chat_preserves_regular_response() -> None:
    response = "I found three available appointment slots."

    result = enforce_chat_write_boundary(
        patient_message="Show me availability",
        assistant_response=response,
    )

    assert result == response


# checks proposals can still be presented
def test_chat_preserves_booking_proposal() -> None:
    response = "Your proposed appointment is ready for review."

    result = enforce_chat_write_boundary(
        patient_message="Book the 10:40 slot",
        assistant_response=response,
    )

    assert result == response


# checks a confirmation request is handled regardless of case
def test_chat_confirmation_is_case_insensitive() -> None:
    result = enforce_chat_write_boundary(
        patient_message="  CONFIRM  ",
        assistant_response="Okay!",
    )

    assert result == CONFIRMATION_MESSAGE
