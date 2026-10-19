"""AI 调用：DeepSeek 默认先“思考”，思考也占输出额度，小额度的调用（测试连接、整理文件）会报“回复达到长度上限”。
这里确认：思考开着（默认）时在额度上多留思考额度、不关思考；关了思考才发 thinking=disabled；其他接口不加额外字段；正文为空又被截断时放宽一次额度重试。假网络，不碰真实接口。"""
import io
import json
import unittest
from unittest.mock import patch

from rpg import ai


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def reply(content, finish="stop"):
    return FakeResp(json.dumps({"choices": [{"message": {"content": content}, "finish_reason": finish}]}).encode("utf-8"))


class ThinkingTest(unittest.TestCase):
    def run_chat(self, base, replies, thinking=True, **kw):
        sent = []

        def fake(req, timeout=0):
            sent.append(json.loads(req.data.decode("utf-8")))
            return replies.pop(0)
        cfg = {"api_key": "k", "base_url": base, "model": "m", "vision_model": "", "vision_api_key": "", "vision_base_url": "", "thinking": thinking}
        with patch.object(ai, "settings", return_value=cfg), patch.object(ai.net, "urlopen", side_effect=fake):
            return ai.chat([{"role": "user", "content": "你好"}], **kw), sent

    def test_deepseek_thinks_by_default_with_extra_room(self):
        out, sent = self.run_chat("https://api.deepseek.com", [reply("连接成功")], max_tokens=200)
        self.assertEqual(out, "连接成功")
        self.assertNotIn("thinking", sent[0])                                     # 没关思考
        self.assertEqual(sent[0]["max_tokens"], 200 + ai.THINK_ROOM)               # 思考也占额度，所以多留
        _, sent = self.run_chat("https://api.deepseek.com", [reply("x")], max_tokens=31000)
        self.assertEqual(sent[0]["max_tokens"], 32000)

    def test_deepseek_thinking_can_be_turned_off(self):
        _, sent = self.run_chat("https://api.deepseek.com", [reply("好")], thinking=False, max_tokens=300)
        self.assertEqual(sent[0]["thinking"], {"type": "disabled"})
        self.assertEqual(sent[0]["max_tokens"], 300)

    def test_other_providers_do_not_get_the_field(self):
        _, sent = self.run_chat("https://api.openai.com/v1", [reply("ok")])
        self.assertNotIn("thinking", sent[0])

    def test_empty_truncated_reply_is_retried_once_with_more_room(self):
        out, sent = self.run_chat("https://x.example/v1", [reply("", "length"), reply("好", "stop")], max_tokens=200)
        self.assertEqual(out, "好")
        self.assertEqual([s["max_tokens"] for s in sent], [200, 800])   # 非 DeepSeek：不加思考额度，空正文才放宽

    def test_truncated_reply_with_text_still_errors_and_retry_happens_only_once(self):
        with self.assertRaises(ai.AIError):
            self.run_chat("https://x.example/v1", [reply("半截", "length")])
        with self.assertRaises(ai.AIError):
            self.run_chat("https://x.example/v1", [reply("", "length"), reply("", "length")], max_tokens=200)


if __name__ == "__main__":
    unittest.main()
