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
