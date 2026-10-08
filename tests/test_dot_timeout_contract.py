"""Regression contract for the dot send timeout boundary."""

import re
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "skills"
    / "dot"
    / "scripts"
    / "dot_chrome.mjs"
)


class DotTimeoutContractTest(unittest.TestCase):
    def test_timeout_aborts_before_send_click_can_start(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("let aborted = false;", source)

        timeout = re.search(
            r"launchTimer = setTimeout\(\(\) => \{(?P<body>.*?)\}, 120000\);",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(timeout)
        timeout_body = timeout.group("body")
        self.assertLess(
            timeout_body.index("aborted = true;"),
            timeout_body.index("reject(new Unavailable('timeout'));"),
        )

        send_start = source.index("async function send(")
        click_start = source.index("clicked = true;", send_start)
        send_prefix = source[send_start:click_start]
        self.assertTrue(
            send_prefix.rstrip().endswith("if (aborted) return;"),
            "send must check the timeout flag immediately before marking the click as started",
        )


if __name__ == "__main__":
    unittest.main()
