# Claude API provider — design

**Date:** 2026-10-25
**Status:** approved by the owner in conversation (default model and speed priority are the owner's words; everything marked *my call* is the planner's).

## Intent

Add the Claude API as a third dialogue provider next to Google Gemini and OpenAI, so the mod can run on
`claude-haiku-5-5` with the lowest possible latency. Villager dialogue is 4 short lines generated while the
player is in a conversation; the only thing that matters is how fast a usable reply comes back.

## Goals

- `MODEL_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` makes every existing entry point (`ac_parser_encoder.py --watch`,
  `--write`, `dialogue_prompt.py <speaker>`) generate through Claude, screenshots included.
- Default model `claude-haiku-5-5`, thinking off, effort `low` (owner: "Not much thinking is used, it's all
  about speed").
- `--model claude-...` selects Claude even when a Google or OpenAI key is also configured.
- The decorator (second pass that inserts control codes) can run on its own Claude model via
  `ANTHROPIC_MODEL_DECORATOR`, mirroring `GOOGLE_MODEL_DECORATOR` / `OPENAI_MODEL_DECORATOR`.
- A test suite that runs without Dolphin, without network and without an API key, so a cloud session can
  prove the integration.

## Non-goals

- No change to Gemini or OpenAI behaviour beyond the routing fix below.
- No streaming, caching, tool use, structured outputs or multi-turn state: one prompt in, text out.
- No new CLI flags. Configuration stays in `.env`, matching the other providers.

## Anti-goals

- Never write an empty or refused reply into game memory: a Claude refusal must raise like any other API
  error so the watch loop's existing `except Exception` path skips the write.
- Never send sampling parameters: the Claude API (version `2026-10-21`, SDK 2.x default) returns 400 for any
  `temperature` / `top_p` / `top_k`.

## Constraints (verbatim values)

| Item | Value |
|---|---|
| SDK | `anthropic==2.3.0` (PyPI latest on 2026-10-25); SDK 2.x speaks API version `2026-10-21` |
| Python floor | `>=3.10` (the SDK requires it; the repo said 3.8+ — *my call* to bump `setup.py`, README, install scripts) |
| Default model | `claude-haiku-5-5` (env override `ANTHROPIC_MODEL`) |
| Request shape | `thinking={"type": "disabled"}`, `output_config={"effort": "low"}`, `max_tokens` forwarded from the caller (512 default), **no** `temperature` |
| Image input | base64 `image` content blocks, media type from `encode_image()` (`image/png` or `image/jpeg`), placed before the text block |
| Env vars | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_MODEL_DECORATOR`, `MODEL_PROVIDER=anthropic` |
| Tests | stdlib `unittest` + `unittest.mock`; run with `python -m unittest discover -s tests -t . -v` |

## The parts that were decided

### 1. `call_llm_anthropic` in `dialogue_prompt.py`

Same signature as `call_llm_gemini` / `call_llm_openai`:
`(prompt, model=None, temperature=1.0, max_tokens=512, image_paths=None) -> str`.
`temperature` is accepted for parity and never sent. Lazy `import anthropic` inside the function, the way the
other two providers import their SDKs. Reads text by block `type` (a response may start with a non-text
block). `stop_reason == "refusal"` raises `RuntimeError` naming `stop_details.category`. Missing or unreadable
screenshot paths are skipped, as the other providers do.

Why thinking off rather than adaptive + low effort (*my call*): the Haiku 5.5 guidance prefers effort as the
lever, but thinking off is accepted at `low` and is the only setting that guarantees zero thinking tokens
before the first dialogue line. If leaked reasoning text ever shows up in-game, the one-line fix is
`thinking={"type": "adaptive"}` with effort still `low`.

### 2. Routing in `get_model_provider(model)`

Today the function checks `MODEL_PROVIDER` (default `google`) before the model-name prefix, so `--model
openai-…` with a Google key still routes to Gemini. The rewrite checks the prefix first, then the env default:

- prefix `gemini` → `google`; `openai` → `openai`; `claude` → `anthropic`
- otherwise `MODEL_PROVIDER` (default `google`)
- the chosen provider's key must be set, else `RuntimeError` naming the exact variable
- unknown `MODEL_PROVIDER` → `RuntimeError` listing `google|openai|anthropic`

`call_llm` gains an `anthropic` branch and forwards `max_tokens` to it (the other branches keep ignoring it,
as today). `get_decorator_model` gains `ANTHROPIC_MODEL_DECORATOR or ANTHROPIC_MODEL`.

### 3. `test_setup.py`

`test_environment()` also accepts a configured `ANTHROPIC_API_KEY` (placeholder value
`your_anthropic_api_key_here` does not count).

### 4. Docs

README provider list, `.env` example and API-cost line; `env_template.txt` third key block;
`COMMANDS.md` environment section; Python 3.10+ wherever 3.8+ is stated.

## Left to the builder

- Exact wording of error messages beyond the variable names the tests pin.
- Test file layout inside `tests/` (one file is fine).
- Whether to keep `anthropic` imported lazily or at module top (lazy matches the file; keep lazy).

## Verification the owner will do

After pulling the branch: `cp env_template.txt .env`, set `ANTHROPIC_API_KEY` and `MODEL_PROVIDER=anthropic`,
run `python test_setup.py`, then `GENERATION_COOLDOWN_SECONDS=0 python dialogue_prompt.py Ace --no-news
--no-decorate` (prints 4 lines, no Dolphin needed), then the real thing: `python ac_parser_encoder.py --watch`.
