# animal-crossing-llm-mod

Python mod that reads Animal Crossing (GameCube, Dolphin) dialogue memory, asks an LLM for new villager lines,
and writes them back. Entry point `ac_parser_encoder.py`; prompts and provider calls live in `dialogue_prompt.py`.

## Commands

- Tests (no Dolphin, no network, no key): `python -m unittest discover -s tests -t . -v`
- Generation smoke without Dolphin: `GENERATION_COOLDOWN_SECONDS=0 python dialogue_prompt.py Ace --no-news --no-decorate`
- Setup check: `python test_setup.py`
- Full command reference: `COMMANDS.md`

## Rules

- Providers are selected in `dialogue_prompt.get_model_provider`; a new provider = one `call_llm_<name>` function
  shaped like the existing ones + a branch there, in `call_llm`, and in `get_decorator_model`.
- Never send `temperature` / `top_p` / `top_k` to the Claude API (version 2026-10-21 rejects them).
- Subagents never commit, push, stash or run wrap-up; the controlling session commits per task.
- Feature work goes on a branch and is pushed as that branch; `main` is merged by the owner.
