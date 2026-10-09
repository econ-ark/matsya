"""Check client configuration without contacting a Matsya service."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from matsya import cli, config
from matsya.client import MatsyaClient


class ClientConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        folder = Path(self.directory.name)
        for target, value in (("CONFIG_DIR", folder), ("CONFIG_FILE", folder / "config.toml")):
            held = patch.object(config, target, value)
            held.start()
            self.addCleanup(held.stop)
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def test_missing_address_prevents_a_client_request(self):
        os.environ["MATSYA_TOKEN"] = "msy_test"
        with self.assertRaisesRegex(config.ConfigurationError, "MATSYA_SERVER"):
            config.load_config()
        with patch("matsya.cli.MatsyaClient") as client, patch("sys.stderr"):
            with self.assertRaises(SystemExit) as stopped:
                cli._build_client()
        self.assertEqual(stopped.exception.code, 1)
        client.assert_not_called()

    def test_environment_overrides_saved_address_and_token(self):
        saved = config.save_config("saved-test-token", "https://saved.example.invalid/")
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        self.assertEqual(config.load_config()["server"], "https://saved.example.invalid")
        os.environ.update(
            MATSYA_SERVER="https://override.example.invalid/",
            MATSYA_TOKEN="environment-test-token",
        )
        self.assertEqual(
            config.load_config(),
            {"server": "https://override.example.invalid", "token": "environment-test-token"},
        )

    def test_configure_saves_explicit_address_without_network(self):
        with patch("builtins.input", side_effect=["msy_test", "https://service.example.invalid"]):
            # the client's opener and `urlopen` both send through `OpenerDirector.open`
            with patch("builtins.print"), patch("urllib.request.OpenerDirector.open") as network:
                cli._run_configure()
        network.assert_not_called()
        self.assertEqual(config.load_config()["server"], "https://service.example.invalid")
        with self.assertRaises(config.ConfigurationError):
            config.save_config("msy_test", "")

    def test_methods_call_the_routes_of_spec_0_3(self):
        client = MatsyaClient("msy_test", "https://service.example.invalid")

        def answer(method, path, body=None):
            return {"id": "t1", "state": "finished" if "/turns/" in path else "converged"}

        with patch.object(client, "_request", side_effect=answer) as request:
            client.index()
            client.search("states")
            client.passage("p1")
            client.submit_job(source_text="A household saves.", target="stage")
            client.job("j1")
            client.wait_job("j1", interval=0)
            client.cancel_job("j1")
            client.new_session("model name")
            client.add_entry("model name", "states")
            client.session("model name")
            client.select_job("model name", "j1")
            client.ask("model name", "What is a stage?", interval=0)
        self.assertEqual(
            [call.args[:2] for call in request.call_args_list],
            [
                ("GET", "/v1/index"),
                ("POST", "/v1/search"),
                ("GET", "/v1/passages/p1"),
                ("POST", "/v1/model-iterations"),
                ("GET", "/v1/model-iterations/j1?view=products"),
                ("GET", "/v1/model-iterations/j1?view=products"),
                ("POST", "/v1/model-iterations/j1/cancel"),
                ("POST", "/v1/sessions"),
                ("POST", "/v1/sessions/model%20name/entries"),
                ("GET", "/v1/sessions/model%20name"),
                ("POST", "/v1/sessions/model%20name/selected-job"),
                ("POST", "/v1/sessions/model%20name/turns"),
                ("GET", "/v1/sessions/model%20name/turns/t1"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
