"""Check client configuration without contacting a Matsya service."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bellman_matsya import cli, config
from bellman_matsya.client import MatsyaClient


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

    def test_default_address_is_used_when_only_the_token_is_set(self):
        os.environ["BELLMAN_MATSYA_TOKEN"] = "msy_test"
        self.assertEqual(config.load_config()["server"], config.DEFAULT_SERVER_URL)
        with patch("bellman_matsya.cli.MatsyaClient") as client:
            cli._build_client()
        # with no personal Anthropic key selected, the client holds none
        # (AMD-MAT-021 §2.2)
        client.assert_called_once_with(
            token="msy_test", server_url=config.DEFAULT_SERVER_URL, anthropic_api_key=None
        )

    def test_environment_overrides_saved_address_and_token(self):
        saved = config.save_config("saved-test-token", "https://saved.example.invalid/")
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        self.assertEqual(config.load_config()["server"], "https://saved.example.invalid")
        os.environ.update(
            BELLMAN_MATSYA_SERVER="https://override.example.invalid/",
            BELLMAN_MATSYA_TOKEN="environment-test-token",
        )
        self.assertEqual(
            config.load_config(),
            {"server": "https://override.example.invalid", "token": "environment-test-token"},
        )

    def test_the_earlier_clients_environment_does_not_configure_bellman(self):
        os.environ.update(MATSYA_TOKEN="old-test-token", MATSYA_SERVER="https://old.example.invalid")
        self.assertTrue(config.first_use())
        self.assertEqual(config.load_config(), {"server": config.DEFAULT_SERVER_URL, "token": ""})
        config.save_config("bellman-test-token", "https://bellman.example.invalid")
        self.assertEqual(
            config.load_config(),
            {"server": "https://bellman.example.invalid", "token": "bellman-test-token"},
        )

    def test_configure_prompts_only_for_token_without_network(self):
        with patch("builtins.input", side_effect=["msy_test"]) as prompt:
            # the client's opener and `urlopen` both send through `OpenerDirector.open`
            with patch("builtins.print"), patch("urllib.request.OpenerDirector.open") as network:
                cli._run_configure()
        prompt.assert_called_once_with("Enter your Matsya token: ")
        network.assert_not_called()
        self.assertEqual(config.load_config(), {"server": config.DEFAULT_SERVER_URL, "token": "msy_test"})
        self.assertNotIn("server =", config.CONFIG_FILE.read_text())

    def test_reconfiguring_token_preserves_a_saved_custom_address(self):
        config.save_config("msy_old", "https://service.example.invalid")
        os.environ["BELLMAN_MATSYA_SERVER"] = "https://temporary.example.invalid"
        with patch("builtins.input", side_effect=["msy_new"]):
            with patch("builtins.print"):
                cli._run_configure()
        self.assertEqual(config.load_config()["server"], "https://temporary.example.invalid")
        del os.environ["BELLMAN_MATSYA_SERVER"]
        self.assertEqual(
            config.load_config(),
            {"server": "https://service.example.invalid", "token": "msy_new"},
        )

    def test_temporary_address_does_not_become_saved_default(self):
        os.environ["BELLMAN_MATSYA_SERVER"] = "https://temporary.example.invalid"
        config.save_config("msy_test")
        del os.environ["BELLMAN_MATSYA_SERVER"]
        self.assertEqual(config.load_config()["server"], config.DEFAULT_SERVER_URL)
        self.assertNotIn("server =", config.CONFIG_FILE.read_text())

    def test_explicit_blank_address_is_refused(self):
        with self.assertRaises(config.ConfigurationError):
            config.save_config("msy_test", "")

    def test_methods_call_the_routes_of_spec_0_3(self):
        client = MatsyaClient("msy_test", "https://service.example.invalid")

        # `options` holds `personal_key`, which marks the three requests that
        # carry a personal Anthropic key (AMD-MAT-021 §2.3)
        def answer(method, path, body=None, **options):
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
