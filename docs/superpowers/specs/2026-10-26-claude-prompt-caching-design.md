# Claude prompt caching: research and design

**Date:** 2026-10-26
**Status:** draft, awaiting owner approval. Builds on `2026-10-25-claude-provider-design.md` (branch
`feat/claude-provider`). Everything marked *my call* is the planner's; the open questions at the end are the owner's.

## Research findings

Sources: [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) and
[Pricing](https://platform.claude.com/docs/en/about-claude/pricing) (both read 2026-10-26), plus the installed
`anthropic==2.3.0` SDK.

| Fact | Value | Source |
|---|---|---|
| Minimum cacheable prefix, Claude Haiku 5.5 | 512 tokens. Shorter prefixes are silently not cached (no error) | caching docs |
| Haiku 5.5 prices (prompts up to 100k tokens) | input $0.10, 5m cache write $0.125, 1h write $0.20, cache hit $0.01, output $0.50 per MTok | pricing page |
| Default TTL | 5 minutes, refreshed free on every hit; `"ttl": "1h"` costs 2x input on write | caching docs |
| Prefix rule | cache covers `tools`, then `system`, then `messages`, up to the block marked `cache_control`; a hit needs an exact match of everything before the breakpoint | caching docs |
| Breakpoints | up to 4 explicit `cache_control` blocks; or one top-level `cache_control` on the request ("automatic caching"), which marks the last cacheable block | caching docs |
| Invalidation | changing `thinking` or `output_config.effort` invalidates message blocks and may invalidate system blocks; adding or removing images invalidates message blocks only | caching docs |
| Usage fields | `usage.cache_creation_input_tokens`, `usage.cache_read_input_tokens`, `usage.input_tokens` (tokens after the last breakpoint) | caching docs; SDK `Usage` model |
| Isolation | never shared across organizations; per workspace on the Claude API | caching docs |
| SDK support | `Messages.create` accepts `system` (blocks with `cache_control`) and a top-level `cache_control` | `inspect.signature` on SDK 2.3.0 |
| Latency | docs promise improved time-to-first-token "for long documents"; no figures for short prefixes | caching docs |

## What our prompts look like (measured on this branch)

- **Decorator** (`_format_control_code_decorator_prompt`): 2,277 characters, of which 2,129 are fixed guidelines.
  The guidelines come *after* the variable input lines today, so nothing is cacheable as built. Token count is
  estimated at 530 to 710 (about 3 to 4 characters per token for control-code-heavy text). That is close enough to
  the 512 minimum that the plan measures it live before writing code.
- **Dialogue** (`format_dialogue_prompt`, 220 villagers): the per-villager stable part (header, instructions, style
  targets, quote, appearance, personality and house notes) is 2,968 characters at the median (p10 2,235, p90 4,156);
  212 of 220 villagers are at or over 2,048 characters. But the time-of-day block sits in the middle of it, and the
  gossip stage instructions and topic/tone lines are interleaved with the stable instructions, so today the cacheable
  prefix ends after about 1,134 characters (well under 512 tokens).

## Why naive caching makes it worse

Adding only the top-level `cache_control` puts the breakpoint on the single user text block. That block changes
on every call (time, input lines), so every call pays the 1.25x write price and no call ever hits. Caching has to be
paired with splitting the stable text into its own block placed first.

## What it saves (honest numbers)

- **Decorator, per generation, on a hit:** about 550 tokens x ($0.10 - $0.01) / MTok = **$0.00005**. The one write
  per 5-minute window costs about $0.000014 extra. During active play nearly every decorator call after the first
  hits, because the text is the same for every villager.
- **Dialogue, per same-villager repeat within 5 minutes:** about 740 tokens x $0.09 / MTok = **$0.00007**.
- **Per 1,000 generations:** roughly $0.05 (decorator) plus up to $0.07 (dialogue repeats). Money is not the reason
  to do this.
- **Latency:** this is the owner's priority, and the docs give no number for prefixes this short. Expect a small
  time-to-first-token gain, not a step change. Phase 1 adds a usage log line so the gain is observed, not assumed.

Informational, outside this spec: the larger speed levers are the second sequential round trip (generate, then
decorate) and the SDK's `speed` parameter, whose availability on Haiku 5.5 is not verified here.

## Intent

Cache the parts of each Claude request that never change, so repeated calls skip re-processing them, without
changing what villagers say and without making any call more expensive than today.

## Goals (Phase 1, this spec's plan)

- The decorator's fixed guidelines go to Claude as one `system` text block with `cache_control: {"type":
  "ephemeral"}`; the variable input lines go in the user message.
- `call_llm` and the three provider functions take an optional `system: Optional[str] = None`. Claude sends it as
  the cached system block. Gemini and OpenAI receive `f"{system}\n\n{prompt}"` as their prompt (*my call*: keeps
  their request code untouched; the only change for them is that the decorator guidelines now come before the input
  lines instead of after).
- With `LLM_LOG_USAGE=1`, every Claude call prints one line:
  `[claude usage] model=<m> in=<n> cache_write=<n> cache_read=<n> out=<n>`.
- Before any code is written, a live two-call check proves the decorator system block is cacheable (second call
  reports `cache_read_input_tokens > 0`). If it is not, Phase 1 stops and reports.

## Non-goals

- Dialogue prompt caching (Phase 2, below): it changes prompt order for every provider and only pays off on
  same-villager repeats.
- 1-hour TTL (2x write; a play session's gaps between generations are well under 5 minutes, so the free refresh
  covers it).
- Top-level automatic caching (see "Why naive caching makes it worse").
- Any change to Gemini or OpenAI beyond the decorator text order.

## Anti-goals

- Never put anything that varies per call (lines, time, speaker, gossip, randomness) into the cached system text.
  Tests pin that two decorator calls send byte-identical system text.
- Never vary `thinking` or `output_config` between calls (it would invalidate the cache); they stay the constants
  from the provider spec.
- Never send `temperature`, `top_p` or `top_k` (unchanged rule).
- A prefix under the minimum must degrade to today's behaviour, never to an error: the API does this already, and
  the plan does not add any check that could fail on it.

## Constraints (verbatim values)

| Item | Value |
|---|---|
| System block shape | `[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]` |
| No `system` given | request has no `system` key and no top-level `cache_control` (byte-identical to today) |
| Non-Claude join | `f"{system}\n\n{prompt}"` |
| Decorator system text | the current `guidelines` string, moved verbatim to module constant `DECORATOR_SYSTEM` |
| Decorator user text | `f"Input lines (verbatim):\n{raw_lines}\n\nNow return the decorated lines in order:"` |
| Usage log env | `LLM_LOG_USAGE=1` (anything else: silent) |
| Tests | stdlib `unittest`, no network, no key; same command as before |

## Phase 2 (deferred, recorded so it is not re-researched)

Split `format_dialogue_prompt` (and `format_spotlight_prompt`) into a stable system part (instructions without the
gossip lines, style targets without tone/topic, header, quote, appearance, personality and house notes) and a variable
user part (gossip instructions, tone, topic, time, news, screenshot note, the "talking to josh" line, gossip status).
The screenshot image stays in the user message; per the docs, images invalidate message blocks only, so the system
cache survives. **Gate:** run Phase 1 with `LLM_LOG_USAGE=1` through a normal play session and count how often the same
villager is generated twice within 5 minutes. Do Phase 2 only if that is common. It changes prompt order for Gemini
and OpenAI too, so it needs the owner's sign-off.

## Open questions for the owner

1. Is the guidelines-first decorator order acceptable for Gemini and OpenAI, or should they keep today's exact text?
2. `LLM_LOG_USAGE` as the variable name, printing to stdout like the rest of the watch loop: OK?
3. Phase 2 now, or after the gate?

## Verification

With a real key: run the plan's two-call gate, then
`MODEL_PROVIDER=anthropic LLM_LOG_USAGE=1 GENERATION_COOLDOWN_SECONDS=0 python dialogue_prompt.py Ace --no-news`
twice within 5 minutes. The second run's decorator line must show `cache_read` > 0 and `cache_write=0`.
