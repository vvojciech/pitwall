import json
import unittest

from pitwall.timeline import parse

CLAUDE = [
    {"type": "user", "timestamp": "2026-10-10T08:00:00Z", "message": {"role": "user", "content": "Fix the login redirect"}},
    {"type": "assistant", "timestamp": "2026-10-10T08:00:05Z", "message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "The redirect lives in auth.ts.\nMore."},
        {"type": "text", "text": "Reading the auth module."},
        {"type": "tool_use", "name": "Read", "input": {"file_path": "/a/src/auth.ts"}},
    ]}},
    {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "file text"}]}},
    {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "Task", "input": {"description": "Search for callers"}}]}},
    {"type": "user", "message": {"role": "user", "content": "<task-notification>x</task-notification>"}},
]

CODEX = [
    {"type": "response_item", "timestamp": "2026-10-10T08:00:00Z", "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "<skills>"}]}},
    {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Add a dark mode"}]}},
    {"type": "response_item", "payload": {"type": "reasoning", "summary": [{"type": "summary_text", "text": "Plan the theme tokens"}]}},
    {"type": "response_item", "payload": {"type": "function_call", "name": "shell", "arguments": json.dumps({"command": ["bash", "-lc", "npm test"]})}},
    {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "apply_patch", "input": "*** Begin Patch\n*** Update File: src/theme.ts\n"}},
    {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": 'const r = await tools.exec_command({cmd:"touch \\"a b.txt\\""}); text(r);\n'}},
    {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Done. Dark mode is on."}]}},
]


def lines(records):
    return [json.dumps(r) for r in records] + ["not json"]


class LastReplyTests(unittest.TestCase):
    def test_claude_last_reply_is_complete(self):
        from pitwall.timeline import last_reply
        records = CLAUDE + [{"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Line one.\nLine two. APPROVED"}]}}]
        self.assertEqual(last_reply(lines(records)), "Line one.\nLine two. APPROVED")

    def test_codex_last_reply(self):
        from pitwall.timeline import last_reply
        self.assertEqual(last_reply(lines(CODEX)), "Done. Dark mode is on.")


class TimelineTests(unittest.TestCase):
    def test_claude_transcript(self):
        items = parse(lines(CLAUDE))
        self.assertEqual([(i["kind"], i["text"]) for i in items], [
            ("prompt", "Fix the login redirect"),
            ("thinking", "The redirect lives in auth.ts."),
            ("text", "Reading the auth module."),
            ("tool", "Read auth.ts"),
            ("agent", "Task Search for callers"),
        ])

    def test_codex_transcript(self):
        items = parse(lines(CODEX))
        self.assertEqual([(i["kind"], i["text"]) for i in items], [
            ("prompt", "Add a dark mode"),
            ("thinking", "Plan the theme tokens"),
            ("tool", "shell npm test"),
            ("tool", "apply_patch src/theme.ts"),
            ("tool", 'Bash touch "a b.txt"'),
            ("text", "Done. Dark mode is on."),
        ])

    def test_limit_keeps_the_newest(self):
        self.assertEqual(parse(lines(CLAUDE), limit=2)[-1]["kind"], "agent")
        self.assertEqual(len(parse(lines(CLAUDE), limit=2)), 2)


if __name__ == "__main__":
    unittest.main()
