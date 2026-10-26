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


if __name__ == "__main__":
    unittest.main()
