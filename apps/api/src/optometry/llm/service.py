"""Groq LLM service."""

from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq


class LLMServiceError(Exception):
    pass


# generates a text response using groq
def generate_response(
    *,
    client: Groq,
    model: str,
    message: str,
) -> str:
    if not message.strip():
        raise ValueError("Message cannot be empty")

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an optometry appointment booking assistant. "
                        "Provide clear and concise responses. "
                        "Do not claim to book, cancel, or modify appointments."
                    ),
                },
                {"role": "user", "content": message},
            ],
            temperature=0.2,
        )
    except (APIConnectionError, APITimeoutError, APIStatusError) as exc:
        raise LLMServiceError("Groq request failed") from exc

    if not completion.choices:
        raise LLMServiceError("Groq returned no response")

    content = completion.choices[0].message.content

    if not content or not content.strip():
        raise LLMServiceError("Groq returned an empty response")

    return content.strip()
