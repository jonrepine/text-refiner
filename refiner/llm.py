import os
import anthropic


def get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import keyring
        key = keyring.get_password("text-refiner", "api_key")
        if key:
            return key
    except Exception:
        pass
    raise RuntimeError("No API key found. Set ANTHROPIC_API_KEY or run setup.sh.")


def refine(text: str, system_prompt: str, config: dict) -> str:
    client = anthropic.Anthropic(api_key=get_api_key())
    message = client.messages.create(
        model=config.get("model", "claude-sonnet-4-5"),
        max_tokens=config.get("max_tokens", 1024),
        system=system_prompt,
        messages=[{"role": "user", "content": text}],
        timeout=config.get("timeout_seconds", 15),
    )
    return message.content[0].text
