# Claude API Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **If those skills are not installed (a cloud session cloned from GitHub has no plugins):** follow the
> *Subagent protocol* section below. It is the same process written out.

**Goal:** Make the mod generate villager dialogue through the Claude API (`claude-haiku-5-5`, thinking off, effort low) as a third provider beside Gemini and OpenAI.

**Architecture:** One new provider function `call_llm_anthropic` in `dialogue_prompt.py`, shaped like the two existing ones; `get_model_provider` is rewritten so the model-name prefix wins over `MODEL_PROVIDER`; `call_llm` and `get_decorator_model` gain an `anthropic` branch. A stdlib `unittest` suite with a mocked SDK client proves the request shape, routing and error paths without network, keys or Dolphin.

**Tech Stack:** Python 3.10+, `anthropic==2.3.0` (Messages API, version 2026-10-21), `unittest` + `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-10-25-claude-provider-design.md` (read it first; this plan argues from it).

## Global Constraints

- Python floor `>=3.10`; SDK pin exactly `anthropic==2.3.0` in `requirements.txt`.
- Default model string exactly `claude-haiku-5-5`; never append a date suffix.
- Every Claude request: `thinking={"type": "disabled"}`, `output_config={"effort": "low"}`, `max_tokens` from the caller; **never** `temperature`, `top_p`, `top_k`.
- Env names exactly: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_MODEL_DECORATOR`, `MODEL_PROVIDER=anthropic`.
- Match the file's existing style: lazy SDK import inside the provider function, `Optional`/`List` typing, no new dependencies beyond `anthropic`.
- Test command for every task: `python -m unittest discover -s tests -t . -v` (run from the repo root).
- Branch: `feat/claude-provider` off `main`. Commit per task. Push only that branch, only at the end.

## Review Focus

1. `--model claude-haiku-5-5` while `GOOGLE_API_KEY` is also set must route to Claude (today the env default wins) — pinned in Task 3.
2. A screenshot path that is missing or unreadable must produce a text-only request, not a crash — pinned in Task 2.
3. A response whose first block is not text must still return the dialogue text — pinned in Task 2.
4. A refusal must raise, so the watch loop never writes an empty reply into game memory — pinned in Task 2.
5. `decorate_dialogue_with_control_codes` passes `temperature=1.0` down; it must not reach the API — pinned in Task 2.

---

## Subagent protocol (for a session without the superpowers skills)

The controller (you, the session that read this file) never writes product code itself. Per task:

1. **Implement.** Dispatch one general-purpose subagent with: the repo path, the full text of that one task, the Global Constraints, and these rules verbatim: *"Never run `git commit`, `git push`, `git stash`, `git add`, or any wrap-up; never touch files outside the task's Files list; when done, reply with `git diff` of the tracked files and `diff -u /dev/null <path>` for each new file, plus the exact test output."*
2. **Verify the tree.** Run `git status --short` and `git stash list` (must be empty). Run the full test command. Read the diff yourself.
3. **Review.** Dispatch a second, fresh subagent with the task text and the diff only (not your opinion): *"Check that every step was done as written, every test asserts the pinned values, and nothing outside the task changed. Reply with a list of concrete problems or `APPROVED`."* Loop back to step 1 with the problems until approved.
4. **Commit.** You commit, with the message the task gives.

After the last task: one more fresh reviewer reads the whole branch diff against `main` (`git diff main...HEAD`) with the spec. Fix, run the suite, then push `feat/claude-provider` and report (Task 6).

---

### Task 1: Branch, environment, test scaffold

**Files:**
- Create: `tests/__init__.py` (empty)
- Modify: `requirements.txt`

**Interfaces:**
- Produces: a venv in which `import anthropic`, `import google.genai`, `import openai` all work, and an empty test package that `discover` finds.

- [ ] **Step 1: Branch**

```bash
git checkout -b feat/claude-provider main
```

- [ ] **Step 2: Add the SDK pin**

In `requirements.txt`, insert the line `anthropic==2.3.0` directly after `annotated-types==0.7.0` (the file is alphabetical).

- [ ] **Step 3: Install**

Run: `python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt`
Expected: exit 0. If a native package (`dolphin-memory-engine`, `PyAutoGUI`, `pyobjc-*`) fails to build on this machine, run instead `pip install anthropic==2.3.0 google-genai==0.8.0 openai==1.99.9 python-dotenv==1.1.1 requests==2.32.4 beautifulsoup4==4.13.4` and note it in the final report; the tests below do not touch Dolphin or the screen.

- [ ] **Step 4: Confirm the SDK and Python**

Run: `python -c "import sys, anthropic; print(sys.version.split()[0], anthropic.__version__)"`
Expected: a Python `3.10` or newer and `2.3.0`.

- [ ] **Step 5: Create the empty test package and run discovery**

Create `tests/__init__.py` (zero bytes).
Run: `python -m unittest discover -s tests -t . -v`
Expected: `Ran 0 tests` and `OK`.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt tests/__init__.py
git commit -m "chore: pin anthropic SDK and add test package"
```

---

### Task 2: `call_llm_anthropic`

**Files:**
- Modify: `dialogue_prompt.py` (insert after `call_llm_openai`, before `get_model_provider`)
- Create: `tests/test_llm_providers.py`

**Interfaces:**
- Consumes: `encode_image(path) -> tuple[str, str]` (already in `dialogue_prompt.py`).
- Produces: `ANTHROPIC_DEFAULT_MODEL = "claude-haiku-5-5"` (module constant) and
  `call_llm_anthropic(prompt: str, model: Optional[str] = None, temperature: float = 1.0, max_tokens: int = 512, image_paths: Optional[List[str]] = None) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_llm_providers.py`:

```python
import base64
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import dialogue_prompt


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _response(blocks, stop_reason="end_turn", stop_details=None):
    return SimpleNamespace(content=blocks, stop_reason=stop_reason, stop_details=stop_details)


ANTHROPIC_ENV = {"ANTHROPIC_API_KEY": "test-key"}


class CallLlmAnthropicTests(unittest.TestCase):
    def _call(self, reply=None, env=None, **kwargs):
        reply = reply if reply is not None else _response([_text("Hi there!")])
        environ = dict(ANTHROPIC_ENV, **(env or {}))
        with mock.patch.dict(os.environ, environ, clear=True), \
                mock.patch("anthropic.Anthropic") as client_cls:
            client_cls.return_value.messages.create.return_value = reply
            result = dialogue_prompt.call_llm_anthropic("Say hi", **kwargs)
            sent = client_cls.return_value.messages.create.call_args.kwargs
            client_cls.assert_called_once_with(api_key="test-key")
        return result, sent

    def test_request_shape_uses_haiku_low_effort_no_thinking_no_temperature(self):
        result, sent = self._call(temperature=1.0)
        self.assertEqual(result, "Hi there!")
        self.assertEqual(sent["model"], "claude-haiku-5-5")
        self.assertEqual(sent["max_tokens"], 512)
        self.assertEqual(sent["thinking"], {"type": "disabled"})
        self.assertEqual(sent["output_config"], {"effort": "low"})
        self.assertNotIn("temperature", sent)
        self.assertNotIn("top_p", sent)
        self.assertNotIn("top_k", sent)
        self.assertEqual(sent["messages"], [{"role": "user", "content": [{"type": "text", "text": "Say hi"}]}])

    def test_model_argument_and_env_override_default(self):
        _, sent = self._call(model="claude-sonnet-5-5")
        self.assertEqual(sent["model"], "claude-sonnet-5-5")
        _, sent = self._call(env={"ANTHROPIC_MODEL": "claude-opus-5-5"})
        self.assertEqual(sent["model"], "claude-opus-5-5")

    def test_max_tokens_is_forwarded(self):
        _, sent = self._call(max_tokens=900)
        self.assertEqual(sent["max_tokens"], 900)

    def test_png_screenshot_becomes_image_block_before_text(self):
        raw = b"\x89PNG\r\n\x1a\nfake"
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(raw)
            path = f.name
        try:
            _, sent = self._call(image_paths=[path])
        finally:
            os.unlink(path)
        content = sent["messages"][0]["content"]
        self.assertEqual(len(content), 2)
        self.assertEqual(content[0]["type"], "image")
        self.assertEqual(content[0]["source"]["type"], "base64")
        self.assertEqual(content[0]["source"]["media_type"], "image/png")
        self.assertEqual(base64.b64decode(content[0]["source"]["data"]), raw)
        self.assertEqual(content[1], {"type": "text", "text": "Say hi"})

    def test_missing_screenshot_is_skipped(self):
        _, sent = self._call(image_paths=["/nonexistent/shot.png"])
        self.assertEqual(sent["messages"][0]["content"], [{"type": "text", "text": "Say hi"}])

    def test_only_text_blocks_are_returned(self):
        reply = _response([SimpleNamespace(type="thinking", thinking=""), _text("Line 1\n"), _text("Line 2")])
        result, _ = self._call(reply=reply)
        self.assertEqual(result, "Line 1\nLine 2")

    def test_refusal_raises_with_category(self):
        reply = _response([], stop_reason="refusal", stop_details=SimpleNamespace(category="general_harms"))
        with self.assertRaises(RuntimeError) as ctx:
            self._call(reply=reply)
        self.assertIn("general_harms", str(ctx.exception))

    def test_missing_api_key_raises_before_any_request(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("anthropic.Anthropic") as client_cls:
            with self.assertRaises(RuntimeError) as ctx:
                dialogue_prompt.call_llm_anthropic("Say hi")
            client_cls.assert_not_called()
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m unittest discover -s tests -t . -v`
Expected: 8 tests, each `ERROR` with `AttributeError: module 'dialogue_prompt' has no attribute 'call_llm_anthropic'`.

- [ ] **Step 3: Implement `call_llm_anthropic` in `dialogue_prompt.py`**

Add `ANTHROPIC_DEFAULT_MODEL = "claude-haiku-5-5"` next to the other module constants (after `NEWS_FEED_URLS`). Then the function, in the position named under Files:

- `api_key = os.environ.get("ANTHROPIC_API_KEY")`; missing → `RuntimeError("ANTHROPIC_API_KEY not set in environment")`, raised before importing the SDK.
- `import anthropic` inside a `try`, like the other providers; failure → `RuntimeError("anthropic package not installed. Please install it to call the Claude API.")`.
- `client = anthropic.Anthropic(api_key=api_key)`; `model = model or os.environ.get("ANTHROPIC_MODEL", ANTHROPIC_DEFAULT_MODEL)`.
- Build `content`: for each path in `image_paths`, `encode_image(path)` inside `try/except Exception: continue`, append `{"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64_image}}`; then append `{"type": "text", "text": prompt}` last.
- One comment line above the request: `temperature` is accepted for parity with the other providers and never sent, because API version 2026-10-21 rejects sampling parameters.
- `resp = client.messages.create(model=model, max_tokens=max_tokens, thinking={"type": "disabled"}, output_config={"effort": "low"}, messages=[{"role": "user", "content": content}])`.
- `if resp.stop_reason == "refusal"`: `category = getattr(resp.stop_details, "category", None)`; `raise RuntimeError(f"Claude declined the request (category: {category})")`.
- `return "".join(block.text for block in resp.content if block.type == "text")`.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: `Ran 8 tests` … `OK`.

- [ ] **Step 5: Mutation check (the reviewer will ask for this output)**

Temporarily change `"low"` to `"medium"` in the new function, run the suite, confirm `test_request_shape_uses_haiku_low_effort_no_thinking_no_temperature` FAILS, revert, run again, confirm `OK`. Include both outputs in the hand-back.

- [ ] **Step 6: Commit**

```bash
git add dialogue_prompt.py tests/test_llm_providers.py
git commit -m "feat: add Claude API provider (claude-haiku-5-5, thinking off, low effort)"
```

---

### Task 3: Routing — prefix first, then `MODEL_PROVIDER`; wire `call_llm` and the decorator

**Files:**
- Modify: `dialogue_prompt.py` — `get_model_provider`, `call_llm`, `get_decorator_model`
- Modify: `tests/test_llm_providers.py` (append)

**Interfaces:**
- Consumes: `call_llm_anthropic` from Task 2.
- Produces: `get_model_provider(model: Optional[str] = None) -> str` returning one of `"google" | "openai" | "anthropic"`; `call_llm(...)` unchanged signature; `get_decorator_model() -> Optional[str]`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_llm_providers.py`)

```python
class ProviderRoutingTests(unittest.TestCase):
    def test_default_is_google_when_google_key_set(self):
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "g"}, clear=True):
            self.assertEqual(dialogue_prompt.get_model_provider(), "google")

    def test_model_provider_env_anthropic(self):
        with mock.patch.dict(os.environ, {"MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "a"}, clear=True):
            self.assertEqual(dialogue_prompt.get_model_provider(), "anthropic")

    def test_claude_prefix_beats_google_default(self):
        env = {"GOOGLE_API_KEY": "g", "ANTHROPIC_API_KEY": "a"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(dialogue_prompt.get_model_provider("claude-haiku-5-5"), "anthropic")

    def test_openai_prefix_beats_google_default(self):
        env = {"GOOGLE_API_KEY": "g", "OPENAI_API_KEY": "o"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(dialogue_prompt.get_model_provider("openai-gpt-5-nano"), "openai")

    def test_gemini_prefix_beats_anthropic_env(self):
        env = {"MODEL_PROVIDER": "anthropic", "GOOGLE_API_KEY": "g", "ANTHROPIC_API_KEY": "a"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(dialogue_prompt.get_model_provider("gemini-2.0-flash-lite"), "google")

    def test_anthropic_without_key_names_the_variable(self):
        with mock.patch.dict(os.environ, {"MODEL_PROVIDER": "anthropic"}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                dialogue_prompt.get_model_provider()
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    def test_unknown_provider_lists_the_choices(self):
        with mock.patch.dict(os.environ, {"MODEL_PROVIDER": "mistral", "GOOGLE_API_KEY": "g"}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                dialogue_prompt.get_model_provider()
        for name in ("google", "openai", "anthropic"):
            self.assertIn(name, str(ctx.exception))

    def test_provider_env_is_case_insensitive(self):
        with mock.patch.dict(os.environ, {"MODEL_PROVIDER": "Anthropic", "ANTHROPIC_API_KEY": "a"}, clear=True):
            self.assertEqual(dialogue_prompt.get_model_provider(), "anthropic")


class CallLlmDispatchTests(unittest.TestCase):
    def test_call_llm_dispatches_to_anthropic_with_max_tokens(self):
        with mock.patch.dict(os.environ, {"MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "a"}, clear=True), \
                mock.patch.object(dialogue_prompt, "call_llm_anthropic", return_value="ok") as fn:
            out = dialogue_prompt.call_llm("p", model=None, temperature=0.7, max_tokens=640, image_paths=["x.png"])
        self.assertEqual(out, "ok")
        fn.assert_called_once_with(prompt="p", model=None, temperature=0.7, max_tokens=640, image_paths=["x.png"])

    def test_call_llm_still_dispatches_to_gemini(self):
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "g"}, clear=True), \
                mock.patch.object(dialogue_prompt, "call_llm_gemini", return_value="ok") as fn:
            dialogue_prompt.call_llm("p")
        fn.assert_called_once()


class DecoratorModelTests(unittest.TestCase):
    def test_anthropic_decorator_env_wins(self):
        env = {"MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "a",
               "ANTHROPIC_MODEL": "claude-haiku-5-5", "ANTHROPIC_MODEL_DECORATOR": "claude-sonnet-5-5"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(dialogue_prompt.get_decorator_model(), "claude-sonnet-5-5")

    def test_anthropic_decorator_falls_back_to_model_then_none(self):
        env = {"MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "a", "ANTHROPIC_MODEL": "claude-haiku-5-5"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(dialogue_prompt.get_decorator_model(), "claude-haiku-5-5")
        with mock.patch.dict(os.environ, {"MODEL_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "a"}, clear=True):
            self.assertIsNone(dialogue_prompt.get_decorator_model())
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m unittest discover -s tests -t . -v`
Expected: the 8 Task 2 tests pass; of the new 12, these 9 FAIL or ERROR: `test_model_provider_env_anthropic`, `test_claude_prefix_beats_google_default`, `test_openai_prefix_beats_google_default`, `test_anthropic_without_key_names_the_variable`, `test_unknown_provider_lists_the_choices`, `test_provider_env_is_case_insensitive`, `test_call_llm_dispatches_to_anthropic_with_max_tokens` and both `DecoratorModelTests`. The other 3 (`test_default_is_google_when_google_key_set`, `test_gemini_prefix_beats_anthropic_env`, `test_call_llm_still_dispatches_to_gemini`) already pass: they pin behaviour the rewrite must keep. If the split differs, stop and report before implementing.

- [ ] **Step 3: Rewrite `get_model_provider`**

Replace the body with this algorithm (keep the nested `model_starts_with` helper):

```python
_PROVIDER_KEYS = {"google": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}

def get_model_provider(model: Optional[str] = None) -> str:
    def model_starts_with(model: Optional[str], prefix: str) -> bool:
        return bool(model) and model.lower().startswith(prefix.lower())

    if model_starts_with(model, "gemini"):
        provider = "google"
    elif model_starts_with(model, "openai"):
        provider = "openai"
    elif model_starts_with(model, "claude"):
        provider = "anthropic"
    else:
        provider = os.environ.get("MODEL_PROVIDER", "google").lower()

    key_var = _PROVIDER_KEYS.get(provider)
    if key_var is None:
        raise RuntimeError(f"Unknown MODEL_PROVIDER '{provider}'; choose google, openai or anthropic")
    if os.environ.get(key_var) is None:
        raise RuntimeError(f"{key_var} not set in environment (required for provider '{provider}')")
    return provider
```

- [ ] **Step 4: Add the `anthropic` branch to `call_llm`**

`elif model_provider == "anthropic": return call_llm_anthropic(prompt=prompt, model=model, temperature=temperature, max_tokens=max_tokens, image_paths=image_paths)` — keyword arguments exactly as the dispatch test asserts. Leave the gemini/openai branches as they are.

- [ ] **Step 5: Add the `anthropic` branch to `get_decorator_model`**

`elif model_provider == "anthropic": return os.environ.get("ANTHROPIC_MODEL_DECORATOR") or os.environ.get("ANTHROPIC_MODEL")`.

- [ ] **Step 6: Run to verify all pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: `Ran 20 tests` … `OK`.

- [ ] **Step 7: Commit**

```bash
git add dialogue_prompt.py tests/test_llm_providers.py
git commit -m "feat: route claude-* models and MODEL_PROVIDER=anthropic to the Claude provider"
```

---

### Task 4: `test_setup.py` recognises the Claude key

**Files:**
- Modify: `test_setup.py` — `test_environment()`
- Modify: `tests/test_llm_providers.py` (append)

**Interfaces:**
- Produces: `test_setup.test_environment() -> bool` returns `True` when `.env` in the current directory holds a non-placeholder `ANTHROPIC_API_KEY`.

- [ ] **Step 1: Write the failing test** (append)

```python
class SetupScriptTests(unittest.TestCase):
    # test_environment() checks os.path.exists('.env') in the cwd, then calls load_dotenv(), which
    # searches from test_setup.py's own directory (not the cwd). So: an empty .env in a temp cwd
    # satisfies the existence check, load_dotenv is stubbed out, and the key comes from os.environ.
    def _run_in_tmp_env(self, env):
        import test_setup
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, ".env"), "w").close()
            os.chdir(d)
            try:
                with mock.patch.dict(os.environ, env, clear=True), mock.patch("dotenv.load_dotenv"):
                    return test_setup.test_environment()
            finally:
                os.chdir(cwd)

    def test_anthropic_key_alone_passes_environment_check(self):
        self.assertTrue(self._run_in_tmp_env({"ANTHROPIC_API_KEY": "sk-ant-test"}))

    def test_anthropic_placeholder_does_not_pass(self):
        self.assertFalse(self._run_in_tmp_env({"ANTHROPIC_API_KEY": "your_anthropic_api_key_here"}))
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m unittest discover -s tests -t . -v`
Expected: `test_anthropic_key_alone_passes_environment_check` FAILS (`False is not true`); the placeholder test passes already.

- [ ] **Step 3: Implement**

In `test_setup.test_environment()`, read `anthropic_key = os.getenv('ANTHROPIC_API_KEY')` beside the other two and add an `elif anthropic_key and anthropic_key != 'your_anthropic_api_key_here': print("✅ Anthropic API key configured")` branch before the final `else`.

- [ ] **Step 4: Run to verify all pass**

Run: `python -m unittest discover -s tests -t . -v`
Expected: `Ran 22 tests` … `OK`.

- [ ] **Step 5: Commit**

```bash
git add test_setup.py tests/test_llm_providers.py
git commit -m "feat: test_setup accepts ANTHROPIC_API_KEY"
```

---

### Task 5: Documentation and Python floor

**Files:**
- Modify: `env_template.txt`, `README.md`, `COMMANDS.md`, `setup.py`, `install.sh`, `install.bat`, `CLAUDE.md`

**Interfaces:** none (copy only).

- [ ] **Step 1: `env_template.txt`**

Under "Choose ONE of these API providers", add after the OpenAI block:

```
# Anthropic Claude (Paid service; fastest option with claude-haiku-5-5)
# ANTHROPIC_API_KEY=your_anthropic_api_key_here
# MODEL_PROVIDER=anthropic          # google (default) | openai | anthropic
# ANTHROPIC_MODEL=claude-haiku-5-5  # optional override
# ANTHROPIC_MODEL_DECORATOR=        # optional: separate model for the control-code pass
```

- [ ] **Step 2: `README.md`**

- "Generates AI responses using Google Gemini or OpenAI models" → "… Google Gemini, OpenAI or Anthropic Claude models".
- In the `.env` example add `# For Anthropic Claude (Paid, fastest)` / `ANTHROPIC_API_KEY=your_api_key_here` / `MODEL_PROVIDER=anthropic`.
- Features: "**Multi-LLM Support**: Google Gemini, OpenAI and Anthropic Claude compatibility".
- Important Notes "API Costs": add "Anthropic Claude (claude-haiku-5-5) is paid, priced per token".
- "Install Python 3.8+" → "Install Python 3.10+".
- Add one subsection under Technical Details: "**Running the tests**: `python -m unittest discover -s tests -t . -v` (no Dolphin or API key needed)".

- [ ] **Step 3: `COMMANDS.md`**

In "Environment Configuration" add a block:

```bash
# Use Claude instead of Gemini
echo "MODEL_PROVIDER=anthropic" >> .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# Smoke-test generation without Dolphin
GENERATION_COOLDOWN_SECONDS=0 python dialogue_prompt.py Ace --no-news --no-decorate
```

and under "Test Your Setup" add `python -m unittest discover -s tests -t . -v`.

- [ ] **Step 4: Python floor**

`setup.py`: `python_requires=">=3.10"`, drop the `3.8` and `3.9` classifiers. `install.sh` and `install.bat`: "Python 3.8+" → "Python 3.10+".

- [ ] **Step 5: `CLAUDE.md`**

Delete the "Active handoff" section (the plan is done once this task lands); keep the rest.

- [ ] **Step 6: Verify**

Run: `/usr/bin/grep -rn "3\.8+" README.md install.sh install.bat setup.py; /usr/bin/grep -c "ANTHROPIC_API_KEY" README.md env_template.txt COMMANDS.md`
Expected: first command prints nothing; second prints a count ≥ 1 for each of the three files.
Run the suite once more: `Ran 22 tests` … `OK`.

- [ ] **Step 7: Commit**

```bash
git add env_template.txt README.md COMMANDS.md setup.py install.sh install.bat CLAUDE.md
git commit -m "docs: Claude provider setup, Python 3.10 floor, test command"
```

---

### Task 6: Whole-branch review, optional live smoke, push

**Files:** none new.

- [ ] **Step 1: Whole-branch review**

Dispatch a fresh reviewer with `git diff main...HEAD` and the spec: "Does the branch implement every Goal and respect every Anti-goal and Constraint? List concrete problems or `APPROVED`." Fix via an implementer subagent, re-run the suite, amend nothing — add a fix commit.

- [ ] **Step 2: Live smoke (only if the environment has a real key)**

Run: `python -c "import os,sys; sys.exit(0 if os.environ.get('ANTHROPIC_API_KEY') else 1)"`.
If exit 0: `MODEL_PROVIDER=anthropic GENERATION_COOLDOWN_SECONDS=0 python dialogue_prompt.py Ace --no-news --no-decorate`
Expected: four short lines of villager dialogue printed, no traceback. Paste them in the report.
If exit 1: write "live smoke skipped: no ANTHROPIC_API_KEY in this environment" in the report. Do not ask for a key.

- [ ] **Step 3: Final state checks**

Run: `git status --short` (empty), `git stash list` (empty), `git log --oneline main..HEAD` (5–6 commits).

- [ ] **Step 4: Push the branch only**

```bash
git push -u origin feat/claude-provider
```

- [ ] **Step 5: Report**

Reply with: the commit list, the final test output line, the live-smoke result or skip line, anything installed differently from `requirements.txt` (Task 1 Step 3), and the owner's next step: `git fetch && git checkout feat/claude-provider`, set `ANTHROPIC_API_KEY` + `MODEL_PROVIDER=anthropic` in `.env`, `python test_setup.py`, then `python ac_parser_encoder.py --watch`.
