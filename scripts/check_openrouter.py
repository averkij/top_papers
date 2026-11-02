"""Verify the configured OpenRouter models with small live requests."""

import math

import api


def main():
    for model in (
        "anthropic/claude-haiku-5.5",
        "anthropic/claude-sonnet-5.5",
    ):
        response = api.get_text("Reply with OK only.", api="openrouter", model=model)
        if not response.strip():
            raise RuntimeError(f"Empty response from {model}")
        print(f"PASS: {model}", flush=True)

    for model in ("openai/gpt-6-luna", "openai/gpt-6.1-terra"):
        response = api.get_structured(
            prompt="Return title 'Test' and desc 'OpenRouter integration check'.",
            cls=api.Article,
            model=model,
            temperature=0,
        )
        if "error" in response or not response.get("title") or not response.get("desc"):
            raise RuntimeError(f"Structured output failed for {model}: {response}")
        print(f"PASS: {model} structured output", flush=True)

    embedding = api.get_embedding("OpenRouter integration check")
    if len(embedding) != 256 or not all(math.isfinite(x) for x in embedding):
        raise RuntimeError("Embedding check failed")
    print("PASS: openai/text-embedding-3-small (256 dimensions)", flush=True)


if __name__ == "__main__":
    main()
