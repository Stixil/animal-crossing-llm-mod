# Claude Prompt Caching (Phase 1: decorator) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **If those skills are not installed (a cloud session cloned from GitHub has no plugins):** follow the
> *Subagent protocol* section below.
>
> **Do not start until the owner has approved the spec** (`docs/superpowers/specs/2026-10-26-claude-prompt-caching-design.md`,
> including its open questions).

**Goal:** Send the decorator's fixed guidelines to Claude as one cached `system` block, so every decorator call after
the first in a 5-minute window reads them from cache, and log cache usage so the effect is visible.

**Architecture:** `call_llm` and the three provider functions gain `system: Optional[str] = None`.
`call_llm_anthropic` sends it as a `system` block with `cache_control`; Gemini and OpenAI prepend it to the prompt.
The decorator's guidelines move verbatim into a module constant `DECORATOR_SYSTEM`. An opt-in usage line
(`LLM_LOG_USAGE=1`) prints Claude's cache read/write token counts.

**Tech Stack:** Python 3.10+, `anthropic==2.3.0`, `unittest` + `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-10-26-claude-prompt-caching-design.md` (read it first).

## Global Constraints

- All constraints of the provider plan still hold: `thinking={"type": "disabled"}`, `output_config={"effort": "low"}`,
  never `temperature` / `top_p` / `top_k`, lazy SDK import, `Optional`/`List` typing, no new dependencies.
- System block exactly `[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]`. No top-level
  `cache_control`. No `"ttl"`.
- When `system` is not given, the Claude request has no `system` key (byte-identical to today).
- Non-Claude providers: `prompt = f"{system}\n\n{prompt}"` when `system` is given; nothing else changes in them.
- `DECORATOR_SYSTEM` holds the current `guidelines` string verbatim and nothing that varies per call.
- Test command for every task: `python -m unittest discover -s tests -t . -v` (from the repo root, venv active).
- Live commands (Task 1, Task 6) read the key from `AC_ANTHROPIC_API_KEY` and unset `ANTHROPIC_BASE_URL`:
  prefix them with `env -u ANTHROPIC_BASE_URL ANTHROPIC_API_KEY="$AC_ANTHROPIC_API_KEY"`. Never print the key.
- Branch: `feat/claude-prompt-caching` off `feat/claude-provider` (or off `main` once that branch is merged). Commit
  per task. Push only that branch, only at the end. No em-dashes in docs.

## Review Focus

1. The cached system text must be byte-identical across decorator calls with different lines (Task 4 pins it).
2. Without `system`, the Claude request must be exactly what the provider branch sends today (Task 2 pins it).
3. `call_llm` must forward `system` to every provider, and the existing dispatch test must be updated, not deleted (Task 3).
4. The usage line must never crash on a response without `usage`, and must stay silent unless `LLM_LOG_USAGE=1` (Task 2).
5. The live gate (Task 1) decides whether the feature is worth building; a reviewer should see its raw numbers.

---

## Subagent protocol (for a session without the superpowers skills)

The controller (the session that read this file) never writes product code itself. Per task:

1. **Implement.** Dispatch one general-purpose subagent with: the repo path, the full text of that one task, the Global
   Constraints, and these rules verbatim: *"Never run `git commit`, `git push`, `git stash`, `git add`, or any wrap-up;
   never touch files outside the task's Files list; when done, reply with `git diff` of the tracked files and
   `diff -u /dev/null <path>` for each new file, plus the exact test output."*
2. **Verify the tree.** Run `git status --short` and `git stash list` (must be empty). Run the full test command. Read
   the diff yourself.
3. **Review.** Dispatch a second, fresh subagent with the task text and the diff only (not your opinion): *"Check that
   every step was done as written, every test asserts the pinned values, and nothing outside the task changed. Reply
   with a list of concrete problems or `APPROVED`."* Loop back to step 1 with the problems until approved.
4. **Commit.** You commit, with the message the task gives.

After the last task: one more fresh reviewer reads `git diff feat/claude-provider...HEAD` (or `main...HEAD`) with the
spec. Fix, run the suite, then push `feat/claude-prompt-caching` and report (Task 6).

---

### Task 1: Branch and live cacheability gate

**Files:** none committed. The gate script lives in the session scratchpad.

- [ ] **Step 1: Branch**

```bash
git checkout -b feat/claude-prompt-caching feat/claude-provider
```

(Skip if the branch already exists with only the spec and plan commits on top of `feat/claude-provider`.)

- [ ] **Step 2: Key present?**

Run: `python -c "import os,sys; sys.exit(0 if os.environ.get('AC_ANTHROPIC_API_KEY') else 1)"`
If exit 1: STOP. Report "gate not run: no AC_ANTHROPIC_API_KEY in this session" and do not start Task 2.

- [ ] **Step 3: Two-call gate**

Write this to `<scratchpad>/cache_gate.py` and run it from the repo root with
`env -u ANTHROPIC_BASE_URL ANTHROPIC_API_KEY="$AC_ANTHROPIC_API_KEY" python <scratchpad>/cache_gate.py`:

```python
import anthropic
import dialogue_prompt as d

p = d._format_control_code_decorator_prompt("X")
start = p.index("Instructions:\n") + len("Instructions:\n")
system = p[start:p.index("\n\nNow return")]
client = anthropic.Anthropic()


def once(lines):
    r = client.messages.create(
        model="claude-haiku-5-5", max_tokens=16,
        thinking={"type": "disabled"}, output_config={"effort": "low"},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": [{"type": "text", "text":
            f"Input lines (verbatim):\n{lines}\n\nNow return the decorated lines in order:"}]}],
    )
    u = r.usage
    print(f"in={u.input_tokens} cache_write={u.cache_creation_input_tokens} cache_read={u.cache_read_input_tokens}")
    return u


a = once("<Press A>Hello there!")
b = once("<Press A>Nice weather today.")
print("PASS" if b.cache_read_input_tokens and b.cache_read_input_tokens > 0 else "FAIL")
```

Expected: first line `cache_write` > 0 (or `cache_read` > 0 if another run warmed it), second line `cache_read` > 0,
last line `PASS`. Cost: under $0.001.

If `FAIL` with both counters 0 on both calls: the guidelines are under the 512-token minimum. STOP and report the
three printed lines; Phase 1 is not worth building as specified.

- [ ] **Step 4: Record**

Keep the three printed lines for the final report. Delete the script. No commit for this task.

---

### Task 2: `call_llm_anthropic` takes a cached `system` and logs usage

**Files:**
- Modify: `dialogue_prompt.py` (`call_llm_anthropic` only)
- Modify: `tests/test_llm_providers.py` (add methods to `CallLlmAnthropicTests`)

**Interfaces:**
- Produces: `call_llm_anthropic(prompt, model=None, temperature=1.0, max_tokens=512, image_paths=None, system: Optional[str] = None) -> str`.

- [ ] **Step 1: Write the failing tests**

Add these methods to `CallLlmAnthropicTests`, after `test_missing_api_key_raises_before_any_request`:

```python
    def test_system_is_sent_as_one_cached_block(self):
        _, sent = self._call(system="Static rules")
        self.assertEqual(sent["system"], [{"type": "text", "text": "Static rules", "cache_control": {"type": "ephemeral"}}])
        self.assertEqual(sent["messages"], [{"role": "user", "content": [{"type": "text", "text": "Say hi"}]}])
        self.assertNotIn("cache_control", sent)

    def test_no_system_key_without_system(self):
        _, sent = self._call()
        self.assertNotIn("system", sent)
        self.assertNotIn("cache_control", sent)

    def test_usage_line_printed_only_when_enabled(self):
        usage = SimpleNamespace(input_tokens=40, output_tokens=60, cache_creation_input_tokens=0, cache_read_input_tokens=610)
        reply = SimpleNamespace(content=[_text("ok")], stop_reason="end_turn", stop_details=None, usage=usage)
        with mock.patch("builtins.print") as p:
            self._call(reply=reply)
        p.assert_not_called()
        with mock.patch("builtins.print") as p:
            self._call(reply=reply, env={"LLM_LOG_USAGE": "1"})
        line = p.call_args.args[0]
        for part in ("claude-haiku-5-5", "in=40", "cache_write=0", "cache_read=610", "out=60"):
            self.assertIn(part, line)

    def test_usage_logging_tolerates_missing_usage(self):
        result, _ = self._call(env={"LLM_LOG_USAGE": "1"})
        self.assertEqual(result, "Hi there!")
```

- [ ] **Step 2: Run to verify they fail**

Expected: `test_system_is_sent_as_one_cached_block` ERRORs (`unexpected keyword argument 'system'`) and
`test_usage_line_printed_only_when_enabled` ERRORs (`print` was never called, so `call_args` is `None`); the other two
already pass. All 22 earlier tests pass.

- [ ] **Step 3: Implement**

In `call_llm_anthropic`:
- Add `system: Optional[str] = None` as the last parameter.
- Build the request as a dict with the existing five keys, then
  `if system: request["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]`, then
  `resp = client.messages.create(**request)`. One comment line above the `if`: the system block is the only cache
  breakpoint, so its text must be identical on every call.
- After the refusal check, before the return:
  `if os.environ.get("LLM_LOG_USAGE") == "1":` take `usage = getattr(resp, "usage", None)`; if not `None`, print
  `f"[claude usage] model={model} in={usage.input_tokens} cache_write={usage.cache_creation_input_tokens or 0} cache_read={usage.cache_read_input_tokens or 0} out={usage.output_tokens}"`.

- [ ] **Step 4: Run to verify all pass**

Expected: `Ran 26 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add dialogue_prompt.py tests/test_llm_providers.py
git commit -m "feat: Claude provider sends an optional cached system block and logs cache usage"
```

---

### Task 3: `call_llm` forwards `system` to every provider

**Files:**
- Modify: `dialogue_prompt.py` (`call_llm_gemini`, `call_llm_openai`, `call_llm`)
- Modify: `tests/test_llm_providers.py`

**Interfaces:**
- Produces: `call_llm(prompt, model=None, temperature=1.0, max_tokens=512, image_paths=None, system: Optional[str] = None) -> str`;
  `call_llm_gemini(..., system=None)` and `call_llm_openai(..., system=None)`.

- [ ] **Step 1: Update one existing assertion and add tests**

In `test_call_llm_dispatches_to_anthropic_with_max_tokens`, change the final assertion to
`fn.assert_called_once_with(prompt="p", model=None, temperature=0.7, max_tokens=640, image_paths=["x.png"], system=None)`.

Append:

```python
class SystemPassthroughTests(unittest.TestCase):
    def test_call_llm_forwards_system_to_anthropic(self):
        with mock.patch.dict(os.environ, {"MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "a"}, clear=True), \
                mock.patch.object(dialogue_prompt, "call_llm_anthropic", return_value="ok") as fn:
            dialogue_prompt.call_llm("p", system="S")
        self.assertEqual(fn.call_args.kwargs["system"], "S")

    def test_call_llm_forwards_system_to_gemini(self):
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "g"}, clear=True), \
                mock.patch.object(dialogue_prompt, "call_llm_gemini", return_value="ok") as fn:
            dialogue_prompt.call_llm("p", system="S")
        self.assertEqual(fn.call_args.kwargs["system"], "S")

    def test_gemini_prepends_system_to_prompt(self):
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "g"}, clear=True), \
                mock.patch("google.genai.Client") as client_cls:
            client_cls.return_value.models.generate_content.return_value = SimpleNamespace(text="ok")
            dialogue_prompt.call_llm_gemini("p", system="S")
            contents = client_cls.return_value.models.generate_content.call_args.kwargs["contents"]
        self.assertEqual(contents, ["S\n\np"])

    def test_openai_prepends_system_to_prompt(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "o"}, clear=True), \
                mock.patch("openai.OpenAI") as client_cls:
            client_cls.return_value.responses.create.return_value = SimpleNamespace(output_text="ok")
            dialogue_prompt.call_llm_openai("p", system="S")
            sent = client_cls.return_value.responses.create.call_args.kwargs
        self.assertEqual(sent["input"][0]["content"][0]["text"], "S\n\np")

    def test_gemini_prompt_unchanged_without_system(self):
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "g"}, clear=True), \
                mock.patch("google.genai.Client") as client_cls:
            client_cls.return_value.models.generate_content.return_value = SimpleNamespace(text="ok")
            dialogue_prompt.call_llm_gemini("p")
            contents = client_cls.return_value.models.generate_content.call_args.kwargs["contents"]
        self.assertEqual(contents, ["p"])
```

- [ ] **Step 2: Run to verify they fail**

Expected: the updated dispatch test and the four `system=` tests FAIL or ERROR; `test_gemini_prompt_unchanged_without_system`
passes already.

- [ ] **Step 3: Implement**

- `call_llm_gemini` and `call_llm_openai`: add `system: Optional[str] = None` as the last parameter; first line of the
  body `if system: prompt = f"{system}\n\n{prompt}"`. Nothing else in them changes.
- `call_llm`: add `system: Optional[str] = None` as the last parameter and pass `system=system` in all three branches
  (keep every existing keyword argument as it is).

- [ ] **Step 4: Run to verify all pass**

Expected: `Ran 31 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add dialogue_prompt.py tests/test_llm_providers.py
git commit -m "feat: call_llm forwards an optional system prompt to every provider"
```

---

### Task 4: The decorator sends its guidelines as the cached system prompt

**Files:**
- Modify: `dialogue_prompt.py` (`_format_control_code_decorator_prompt`, `decorate_dialogue_with_control_codes`, new
  constant `DECORATOR_SYSTEM` directly above `_format_control_code_decorator_prompt`)
- Modify: `tests/test_llm_providers.py` (append)

**Interfaces:**
- Produces: `DECORATOR_SYSTEM: str`; `_format_control_code_decorator_prompt(raw_lines: str) -> str` now returns only
  the user part.

- [ ] **Step 1: Write the failing tests** (append)

```python
class DecoratorCachingTests(unittest.TestCase):
    def test_two_decorator_calls_send_identical_system_text(self):
        with mock.patch.dict(os.environ, {"MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "a"}, clear=True), \
                mock.patch.object(dialogue_prompt, "call_llm", return_value="x") as fn:
            dialogue_prompt.decorate_dialogue_with_control_codes("Line A")
            dialogue_prompt.decorate_dialogue_with_control_codes("Line B")
        first, second = fn.call_args_list
        self.assertEqual(first.kwargs["system"], dialogue_prompt.DECORATOR_SYSTEM)
        self.assertEqual(second.kwargs["system"], dialogue_prompt.DECORATOR_SYSTEM)
        self.assertIn("Line A", first.kwargs["prompt"])
        self.assertIn("Line B", second.kwargs["prompt"])

    def test_decorator_user_prompt_shape(self):
        self.assertEqual(
            dialogue_prompt._format_control_code_decorator_prompt("L1\nL2"),
            "Input lines (verbatim):\nL1\nL2\n\nNow return the decorated lines in order:",
        )

    def test_decorator_system_keeps_every_guideline_and_nothing_variable(self):
        for marker in ("You are a dialogue formatter", "<NPC Expression [CC] [EEEE]>",
                       "Output only the decorated lines, nothing else."):
            self.assertIn(marker, dialogue_prompt.DECORATOR_SYSTEM)
        self.assertNotIn("Input lines", dialogue_prompt.DECORATOR_SYSTEM)

    def test_decorator_system_stays_long_enough_to_cache(self):
        # Haiku 5.5 caches prefixes of 512+ tokens; the Task 1 gate passed at today's length (2,129 chars).
        self.assertGreaterEqual(len(dialogue_prompt.DECORATOR_SYSTEM), 2000)
```

- [ ] **Step 2: Run to verify they fail**

Expected: all four ERROR or FAIL (`DECORATOR_SYSTEM` does not exist; the user prompt still contains the guidelines).

- [ ] **Step 3: Implement**

- Move the `guidelines = (...)` string out of `_format_control_code_decorator_prompt`, unchanged character for
  character, into module constant `DECORATOR_SYSTEM`. Keep the function's docstring.
- `_format_control_code_decorator_prompt` returns
  `f"Input lines (verbatim):\n{raw_lines}\n\nNow return the decorated lines in order:"`.
- `decorate_dialogue_with_control_codes`: `call_llm(prompt=prompt, model=decorator_model, temperature=temperature, system=DECORATOR_SYSTEM)`.

- [ ] **Step 4: Verify the text moved verbatim**

Run: `git diff -U0 dialogue_prompt.py | grep '^[-+] *"' | sed 's/^[-+] *//' | sort | uniq -u`
Expected: no output (every guideline line removed from the function reappears unchanged in the constant).

- [ ] **Step 5: Run to verify all pass**

Expected: `Ran 35 tests` … `OK`.

- [ ] **Step 6: Commit**

```bash
git add dialogue_prompt.py tests/test_llm_providers.py
git commit -m "feat: decorator guidelines go to Claude as a cached system prompt"
```

---

### Task 5: Documentation

**Files:**
- Modify: `env_template.txt`, `COMMANDS.md`

- [ ] **Step 1: `env_template.txt`**

After the Anthropic block, add (comment on its own line; no inline comment after a value):

```
# Print Claude token usage, including prompt-cache reads and writes, after every call
# LLM_LOG_USAGE=1
```

- [ ] **Step 2: `COMMANDS.md`**

Under the "Use Claude Instead of Gemini" block, add:

```bash
# See prompt caching work: run twice within 5 minutes; the second run's decorator line shows cache_read > 0
MODEL_PROVIDER=anthropic LLM_LOG_USAGE=1 GENERATION_COOLDOWN_SECONDS=0 python dialogue_prompt.py Ace --no-news
```

- [ ] **Step 3: Verify**

Run: `grep -c "LLM_LOG_USAGE" env_template.txt COMMANDS.md` (each ≥ 1), `grep -n "—" env_template.txt COMMANDS.md`
(no new hits), and the suite (`Ran 35 tests` … `OK`).

- [ ] **Step 4: Commit**

```bash
git add env_template.txt COMMANDS.md
git commit -m "docs: LLM_LOG_USAGE and how to see prompt caching"
```

---

### Task 6: Whole-branch review, live check, push

- [ ] **Step 1: Whole-branch review**

Fresh reviewer with `git diff feat/claude-provider...HEAD` (or `main...HEAD`) and the spec: "Does the branch implement
every Goal and respect every Anti-goal and Constraint? List concrete problems or `APPROVED`." Fix via an implementer
subagent, re-run the suite, add a fix commit (never amend).

- [ ] **Step 2: Live check (only if `AC_ANTHROPIC_API_KEY` is set)**

Run twice, within 5 minutes:

```bash
env -u ANTHROPIC_BASE_URL ANTHROPIC_API_KEY="$AC_ANTHROPIC_API_KEY" MODEL_PROVIDER=anthropic LLM_LOG_USAGE=1 GENERATION_COOLDOWN_SECONDS=0 python dialogue_prompt.py Ace --no-news
```

Expected per run: two `[claude usage]` lines (generation, then decorator) and decorated dialogue, no traceback. On the
second run the decorator line shows `cache_read` > 0 and `cache_write=0`. Paste both runs' usage lines in the report.
If the key is missing: write "live check skipped: no AC_ANTHROPIC_API_KEY in this session". Do not ask for a key.

- [ ] **Step 3: Final state checks**

`git status --short` (empty), `git stash list` (empty), `git log --oneline feat/claude-provider..HEAD`.

- [ ] **Step 4: Push the branch only**

```bash
git push -u origin feat/claude-prompt-caching
```

- [ ] **Step 5: Report**

Commit list, final test line, the Task 1 gate lines, the live-check usage lines or skip line, and whether the Phase 2
gate (spec) now has data: how many same-villager repeats within 5 minutes the owner saw.
