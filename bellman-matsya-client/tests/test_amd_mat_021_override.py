"""AMD-MAT-021 §2.4, D-021-4: the operator's testing override.

With BELLMAN_MATSYA_ANTHROPIC_KEY_OVER_HTTP set to exactly `accept`, the
client sends a personal Anthropic key to a plain-HTTP address that
`key_destination_allowed` refuses, and prints once per client, on standard
error, that the key is sent unencrypted; the orientation and `configure
--set-anthropic-key` say so in place of the refusal sentence. With the
variable absent or holding any other value, the refusal of §2.4 remains in
force unchanged. Under the override the request passes through no proxy,
as at a loopback address. The autouse fixture of conftest removes the variable from every
test's environment, so that the environment of whoever runs the tests
selects nothing. The fake keys and the stand-in service are those of
`test_amd_mat_021_client`; no request leaves the machine.
"""

from __future__ import annotations

import pytest

from bellman_matsya import config
from bellman_matsya.client import (
    KEY_OVER_HTTP_VARIABLE,
    MatsyaClient,
    MatsyaError,
    key_destination_allowed,
    key_over_http_accepted,
)
from conftest import TOKEN
from test_amd_mat_021_client import (  # noqa: F401  (the fixtures are registered by their import)
    ALLOWED,
    FROM_VARIABLE,
    KEY,
    REFUSED,
    REMOTE,
    VARIABLE,
    _Server,
    _destination_refusal,
    _identifier,
    _no_key_in,
    _plain_http,
    _sent,
    _text,
    at_remote,
    entered,
)

# the sentences of the amendment's §2.4, as it quotes them


def _warning(address: str) -> str:
    return (
        "Warning: BELLMAN_MATSYA_ANTHROPIC_KEY_OVER_HTTP=accept is set, so the personal Anthropic "
        f"key is sent unencrypted to {address}."
    )


def _over_http(address: str) -> str:
    return (
        "BELLMAN_MATSYA_ANTHROPIC_KEY_OVER_HTTP=accept is set, so the client sends this key "
        f"unencrypted to {address}, which uses plain HTTP."
    )


def test_only_the_exact_value_accept_sets_the_override(monkeypatch) -> None:
    """The variable is read by name; `accept` alone, without case folding or
    trimming, sets the override."""
    assert KEY_OVER_HTTP_VARIABLE == "BELLMAN_MATSYA_ANTHROPIC_KEY_OVER_HTTP"
    assert not key_over_http_accepted()
    for value in ("", "yes", "1", "true", "Accept", "ACCEPT", " accept", "accept "):
        monkeypatch.setenv(KEY_OVER_HTTP_VARIABLE, value)
        assert not key_over_http_accepted(), repr(value)
    monkeypatch.setenv(KEY_OVER_HTTP_VARIABLE, "accept")
    assert key_over_http_accepted()


def test_under_the_override_a_refused_address_passes_with_one_warning(monkeypatch, capsys) -> None:
    """`check_key_destination` raises nothing at an address that
    `key_destination_allowed` refuses, prints the warning once per client on
    standard error and nothing on standard output, never shows the key, and
    prints nothing at an allowed address or for a client without a key. Any
    other value of the variable leaves the refusal of §2.4 in force."""
    monkeypatch.setenv(KEY_OVER_HTTP_VARIABLE, "accept")
    for address in REFUSED:
        client = MatsyaClient(TOKEN, address, anthropic_api_key=KEY)
        client.check_key_destination()
        client.check_key_destination()
        out, err = capsys.readouterr()
        _no_key_in(out + err, "the warning")
        assert (out, err) == ("", _warning(address) + "\n"), address
        MatsyaClient(TOKEN, address).check_key_destination()
    for address in ALLOWED:
        MatsyaClient(TOKEN, address, anthropic_api_key=KEY).check_key_destination()
    assert tuple(capsys.readouterr()) == ("", "")
    for value in ("yes", "Accept", ""):
        monkeypatch.setenv(KEY_OVER_HTTP_VARIABLE, value)
        with pytest.raises(MatsyaError) as refused:
            MatsyaClient(TOKEN, REFUSED[0], anthropic_api_key=KEY).check_key_destination()
        assert str(refused.value) == _destination_refusal(REFUSED[0]), repr(value)
    assert tuple(capsys.readouterr()) == ("", "")


def test_under_the_override_a_command_sends_the_key_to_a_plain_http_address(
    at_remote, run, monkeypatch, tmp_path
) -> None:
    """At `REMOTE`, with the variable `accept`, `job submit` sends its
    submission with the key, prints the warning once on standard error and
    otherwise answers as at an allowed address; the orientation's credential
    line says the key is sent unencrypted; with the variable `yes` the
    refusal of §2.4 remains in force and no request is sent."""
    stand_in = at_remote
    model = _text(tmp_path, "model.md", "A household saves.\n")
    monkeypatch.setenv(VARIABLE, KEY)
    monkeypatch.setenv(KEY_OVER_HTTP_VARIABLE, "accept")

    status, out, err = run("job", "submit", str(model), "--target", "stage")
    _no_key_in(out + err, "a submission under the override")
    assert status == 0, (out, err)
    _identifier(r"^Job ([0-9a-f]{32}): queued$", out)
    assert err == _warning(REMOTE) + "\n"
    sent = _sent(stand_in)
    assert [key for route, key in sent if route == "POST /v1/model-iterations"] == ["KEY"], sent
    assert all(key == "none" for route, key in sent if route != "POST /v1/model-iterations"), sent

    status, out, err = run()
    _no_key_in(out + err, "the orientation under the override")
    assert (status, err) == (0, "")
    assert out.splitlines()[7] == FROM_VARIABLE + " " + _over_http(REMOTE)

    monkeypatch.setenv(KEY_OVER_HTTP_VARIABLE, "yes")
    status, out, err = run("job", "submit", str(model), "--target", "stage")
    assert (status, out, err) == (1, "", "Error: " + _destination_refusal(REMOTE) + "\n")
    assert stand_in.requests == []
    status, out, err = run()
    assert status == 0 and out.splitlines()[7] == FROM_VARIABLE + " " + _plain_http(REMOTE)


def test_under_the_override_no_proxy_receives_the_key(stand_in, monkeypatch, capsys) -> None:
    """At a plain-HTTP address that `key_destination_allowed` refuses, spelled
    `127.1` so that the client's real opener runs against the stand-in on the
    loopback address, with `http_proxy` naming a second server, `no_proxy`
    unset and the variable `accept`: the request with the key reaches the
    service and the proxy sees nothing, as at a loopback address; the warning
    is printed once."""
    monkeypatch.setenv(KEY_OVER_HTTP_VARIABLE, "accept")
    proxy = _Server(status=502, answer={"detail": "the proxy"})
    try:
        for name in ("NO_PROXY", "no_proxy"):
            monkeypatch.delenv(name, raising=False)
        for name in ("http_proxy", "HTTP_PROXY"):
            monkeypatch.setenv(name, proxy.url)
        address = stand_in.url.replace("127.0.0.1", "127.1")
        assert not key_destination_allowed(address)
        client = MatsyaClient(TOKEN, address, anthropic_api_key=KEY)
        answer = client.submit_job(source_text="A household saves.", target="stage")
        assert answer.get("credential_source") == "client", answer
        assert proxy.seen == []
        assert _sent(stand_in) == [("POST /v1/model-iterations", "KEY")]
        out, err = capsys.readouterr()
        _no_key_in(out + err, "the warning")
        assert (out, err) == ("", _warning(address) + "\n")
    finally:
        proxy.stop()


def test_the_override_is_read_when_the_client_is_constructed(stand_in, monkeypatch, capsys) -> None:
    """A client built while the variable is absent keeps refusing after the
    variable is set, so that the refusal and the no-proxy opener are decided
    at one moment; nothing reaches the proxy or the service. A client built
    afterwards sends the key through no proxy."""
    proxy = _Server(status=502, answer={"detail": "the proxy"})
    try:
        for name in ("NO_PROXY", "no_proxy"):
            monkeypatch.delenv(name, raising=False)
        for name in ("http_proxy", "HTTP_PROXY"):
            monkeypatch.setenv(name, proxy.url)
        address = stand_in.url.replace("127.0.0.1", "127.1")
        earlier = MatsyaClient(TOKEN, address, anthropic_api_key=KEY)
        monkeypatch.setenv(KEY_OVER_HTTP_VARIABLE, "accept")
        with pytest.raises(MatsyaError) as refused:
            earlier.submit_job(source_text="A household saves.", target="stage")
        assert str(refused.value) == _destination_refusal(address)
        assert proxy.seen == [] and stand_in.requests == []
        assert tuple(capsys.readouterr()) == ("", "")
        later = MatsyaClient(TOKEN, address, anthropic_api_key=KEY)
        later.submit_job(source_text="A household saves.", target="stage")
        assert proxy.seen == [] and _sent(stand_in) == [("POST /v1/model-iterations", "KEY")]
        out, err = capsys.readouterr()
        _no_key_in(out + err, "the warning")
        assert (out, err) == ("", _warning(address) + "\n")
    finally:
        proxy.stop()


def test_configure_names_the_override_in_place_of_the_refusal_sentence(
    new_machine, run, monkeypatch, entered
) -> None:
    """`configure --set-anthropic-key` at the built-in plain-HTTP address
    prints the override's sentence when the variable is `accept`, and the
    refusal sentence otherwise."""
    config.save_config(TOKEN)
    entered += [KEY, KEY, KEY, KEY]
    status, out, err = run("configure", "--set-anthropic-key")
    _no_key_in(out + err, "configure")
    assert (status, err) == (0, "") and _plain_http(config.DEFAULT_SERVER_URL) in out.splitlines()
    monkeypatch.setenv(KEY_OVER_HTTP_VARIABLE, "accept")
    status, out, err = run("configure", "--set-anthropic-key")
    _no_key_in(out + err, "configure under the override")
    assert (status, err) == (0, "")
    lines = out.splitlines()
    assert _over_http(config.DEFAULT_SERVER_URL) in lines and _plain_http(config.DEFAULT_SERVER_URL) not in lines
