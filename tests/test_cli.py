from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "canvas.py"


class CanvasCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_init_validate_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            init = self.run_cli(
                "-root",
                tmp,
                "init",
                "-id",
                "CLI Smoke",
                "-scope",
                "thread",
                "-purpose",
                "cli test",
                "-human-action",
                "approve_cli",
                "-agent-action",
                "summarize_cli",
                "-promotion-target",
                "cli-report",
                "-associated-thread",
                "thread-cli",
                "-associated-thread",
                "thread-shared",
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            created = json.loads(init.stdout)
            self.assertEqual(created["id"], "cli-smoke")
            self.assertEqual(created["human_actions"], ["approve_cli"])
            self.assertEqual(created["agent_actions"], ["summarize_cli"])
            self.assertEqual(created["promotion_targets"], ["cli-report"])
            self.assertEqual(created["associatedThreads"], ["thread-cli", "thread-shared"])

            list_result = self.run_cli("-root", tmp, "list", "-thread-id", "thread-cli")
            self.assertEqual(list_result.returncode, 0, list_result.stdout)
            self.assertEqual([item["id"] for item in json.loads(list_result.stdout)], ["cli-smoke"])

            associate = self.run_cli("-root", tmp, "associate-thread", "-id", "cli-smoke", "-thread-id", "thread-extra")
            self.assertEqual(associate.returncode, 0, associate.stdout)
            associate_payload = json.loads(associate.stdout)
            self.assertEqual(associate_payload["associatedThreads"], ["thread-cli", "thread-shared", "thread-extra"])
            self.assertEqual(associate_payload["last_updated_from_thread"], "thread-extra")

            validate = self.run_cli("-root", tmp, "validate", "-id", "cli-smoke")
            self.assertEqual(validate.returncode, 0, validate.stdout)
            self.assertTrue(json.loads(validate.stdout)["valid"])

            export = self.run_cli("-root", tmp, "export-html", "-id", "cli-smoke")
            self.assertEqual(export.returncode, 0, export.stdout)
            export_payload = json.loads(export.stdout)
            html_path = Path(export_payload["html_path"])
            data_path = Path(export_payload["data_path"])
            self.assertTrue(html_path.exists())
            self.assertTrue(data_path.exists())

            promote = self.run_cli(
                "-root",
                tmp,
                "promote",
                "-id",
                "cli-smoke",
                "-target",
                "cli-report",
                "-reference",
                "outputs/cli-report.md",
            )
            self.assertEqual(promote.returncode, 0, promote.stdout)
            self.assertEqual(json.loads(promote.stdout)["promotions"][-1]["target"], "cli-report")

            archive = self.run_cli("-root", tmp, "archive", "-id", "cli-smoke")
            self.assertEqual(archive.returncode, 0, archive.stdout)
            self.assertEqual(json.loads(archive.stdout)["lifecycle"], "archived")

    def test_invalid_scope_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("-root", tmp, "init", "-id", "Bad", "-scope", "invalid")
            self.assertNotEqual(result.returncode, 0)

    def test_verb_commands_cover_canvas_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            created = self.run_json(
                "-root",
                tmp,
                "init",
                "-id",
                "Verb CLI",
                "-scope",
                "thread",
                "-associated-thread",
                "thread-tool",
                "-promotion-target",
                "tool-report",
            )
            self.assertEqual(created["id"], "verb-cli")

            listed = self.run_json("-root", tmp, "list", "-thread-id", "thread-tool")
            self.assertEqual([item["id"] for item in listed], ["verb-cli"])

            associated = self.run_json("-root", tmp, "associate-thread", "-id", "verb-cli", "-thread-id", "thread-extra")
            self.assertEqual(associated["associatedThreads"], ["thread-tool", "thread-extra"])

            updated = self.run_json("-root", tmp, "update-state", "-id", "verb-cli", "-set", "status=ready")
            self.assertEqual(updated["state"]["status"], "ready")

            state_file = Path(tmp) / "state-update.json"
            state_file.write_text(json.dumps({"nested": {"status": "merged"}}), encoding="utf-8")
            merged = self.run_json("-root", tmp, "update-state", "-id", "verb-cli", "-merge-file", str(state_file))
            self.assertEqual(merged["state"]["nested"]["status"], "merged")

            fetched = self.run_json("-root", tmp, "get", "-id", "verb-cli")
            self.assertEqual(fetched["scope"], "thread")

            validation = self.run_json("-root", tmp, "validate", "-id", "verb-cli")
            self.assertTrue(validation["valid"])

            exported = self.run_json("-root", tmp, "export-html", "-id", "verb-cli")
            self.assertTrue(Path(exported["html_path"]).exists())

            promoted = self.run_json(
                "-root",
                tmp,
                "promote",
                "-id",
                "verb-cli",
                "-target",
                "tool-report",
                "-reference",
                "outputs/tool-report.md",
            )
            self.assertEqual(promoted["promotions"][-1]["target"], "tool-report")

            archived = self.run_json("-root", tmp, "archive", "-id", "verb-cli")
            self.assertEqual(archived["lifecycle"], "archived")

    def test_help_aliases_show_structured_reference(self) -> None:
        for flag in ["--help", "-h", "-?"]:
            result = self.run_cli(flag)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Commands:", result.stdout)
            self.assertIn("Examples:", result.stdout)
            self.assertIn("update-state", result.stdout)

        command_help = self.run_cli("init", "-?")
        self.assertEqual(command_help.returncode, 0, command_help.stderr)
        self.assertIn("-id", command_help.stdout)
        self.assertIn("-scope", command_help.stdout)

    def test_server_lifecycle_routes_and_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.run_json("-root", tmp, "init", "-id", "Alpha Board", "-scope", "user", "-purpose", "Alpha planning")
            self.run_json("-root", tmp, "init", "-id", "Beta Board", "-scope", "user", "-purpose", "Beta planning")
            self.run_json("-root", tmp, "export-html", "-id", "alpha-board")
            state: dict[str, object] | None = None
            try:
                state = self.run_json("-root", tmp, "serve", "-port", "0")
                self.assertTrue(state["running"])
                port = int(state["port"])
                self.assertGreater(port, 0)
                base = f"http://127.0.0.1:{port}"

                index_html = self.fetch_text(f"{base}/")
                self.assertIn("Canvas index", index_html)
                self.assertIn("/server-state.json", index_html)

                server_state = json.loads(self.fetch_text(f"{base}/server-state.json"))
                self.assertEqual([item["id"] for item in server_state["canvases"]], ["alpha-board", "beta-board"])
                self.assertEqual(server_state["port"], port)

                canvases = json.loads(self.fetch_text(f"{base}/api/canvases"))
                self.assertEqual([item["id"] for item in canvases], ["alpha-board", "beta-board"])

                alpha_state = json.loads(self.fetch_text(f"{base}/api/canvas/alpha-board/state"))
                self.assertEqual(alpha_state["metadata"]["id"], "alpha-board")

                alpha_html = self.fetch_text(f"{base}/canvas/alpha-board/")
                self.assertIn("canvas-data.js", alpha_html)

                opened = self.run_json("-root", tmp, "open", "-id", "alpha-board")
                self.assertEqual(opened["url"], f"{base}/canvas/alpha-board/")

                self.run_json("-root", tmp, "update-state", "-id", "alpha-board", "-set", "status=changed")
                refreshed_state = json.loads((Path(tmp) / ".server.json").read_text(encoding="utf-8"))
                self.assertEqual(refreshed_state["port"], port)
                self.assertEqual([item["id"] for item in refreshed_state["canvases"]], ["alpha-board", "beta-board"])

                status = self.run_json("-root", tmp, "server-status")
                self.assertTrue(status["running"])
            finally:
                if state is not None:
                    stopped = self.run_json("-root", tmp, "server-stop")
                    self.assertFalse(stopped["running"])

    def run_json(self, *args: str) -> dict[str, object] | list[dict[str, object]]:
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def fetch_text(url: str) -> str:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read().decode("utf-8")


if __name__ == "__main__":
    unittest.main()
