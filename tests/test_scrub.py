import subprocess
import sys
from pathlib import Path

import pytest

from lip.scrub import scan_paths, scan_text

ROOT = Path(__file__).resolve().parent.parent
A = "a1B2c3D4e5F6g7H8i9J0"

# Fixtures are concatenated at runtime so no secret-shaped literal sits in the repo.
POSITIVE = {
    "email": "mail bob" + "@" + "example.com",
    "ipv4": "host 10.1.2.3 up",
    "windows_path": "C:" + r"\Users\\" + "bob",
    "unix_home_path": "see /ho" + "me/bob/x",
    "aws_key": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
    "github_token": "gh" + "p_" + A + "K1L2",
    "sk_key": "s" + "k-" + A + "K1L2",
    "slack_token": "xo" + "xb-" + "1234567890-abc",
    "private_key": "-----BEGIN RSA PRIV" + "ATE KEY-----",
    "generic_secret": "api_" + "key = " + A + "K1L2",
    "bearer_token": "Bearer " + A + "K1L2",
    "password": "pass" + "word = hunter22x",
    "hf_token": "h" + "f_" + A + "K1L2",
    "jwt": "ey" + "Jhbgci.ey" + "Jzdwii.abcde-_f",
    "unc_path": "\\\\" + "srv" + "\\" + "share",
}
NEGATIVE = {
    "email": "use name at host",
    "ipv4": "version 1.2.3.4 and v10.0.0.1, 127.0.0.1, 0.0.0.0",
    "windows_path": r"C:\Program Files\x",
    "unix_home_path": "relative/home/x",
    "aws_key": "AK" + "IA short",
    "github_token": "gh" + "p_ short",
    "sk_key": "sk-short",
    "slack_token": "xo" + "xb-1",
    "private_key": "-----BEGIN CERTIFICATE-----",
    "generic_secret": "token = short",
    "bearer_token": "Bearer short",
    "password": "pass" + "word = ",
    "hf_token": "h" + "f_short",
    "jwt": "ey" + "Jhbgci.notjwt",
    "unc_path": r"a\b and path\to",
}


@pytest.mark.parametrize("name", POSITIVE)
def test_positive(name):
    assert (1, name) in scan_text(POSITIVE[name])


@pytest.mark.parametrize("name", NEGATIVE)
def test_negative(name):
    assert name not in [n for _, n in scan_text(NEGATIVE[name])]


def test_noreply_allowed():
    ok = "109470566+voy-ager" + "@" + "users.noreply.github.com"
    assert scan_text(ok) == []
    assert scan_text("12345" + "@" + "users.noreply.github.com") == []


def test_value_not_reported(tmp_path):
    (tmp_path / "a.md").write_text("x\n" + POSITIVE["github_token"])
    assert scan_paths([tmp_path]) == [(tmp_path / "a.md", 2, "github_token")]


def test_binary_fails_png_ok(tmp_path):
    (tmp_path / "b.bin").write_bytes(b"\0\1")
    (tmp_path / "c.png").write_bytes(b"\0\1")
    assert scan_paths([tmp_path]) == [(tmp_path / "b.bin", 0, "unreadable")]


def run_cli(cwd, *args):
    cmd = [sys.executable, str(ROOT / "scripts" / "scrub_check.py"), *args]
    env = {"PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, check=False)


def test_pycache_skipped(tmp_path):
    d = tmp_path / "__pycache__"
    d.mkdir()
    (d / "x.pyc").write_bytes(b"\0")
    (tmp_path / "y.pyc").write_bytes(b"\0")
    assert scan_paths([tmp_path]) == []


def test_cli_exit_codes(tmp_path):
    assert run_cli(tmp_path).returncode == 0  # no results/ or docs/
    clean = tmp_path / "clean.json"
    clean.write_text('{"a": 1}')
    assert run_cli(tmp_path, str(clean)).returncode == 0
    dirty = tmp_path / "dirty.csv"
    dirty.write_text(POSITIVE["email"])
    r = run_cli(tmp_path, str(dirty))
    assert r.returncode == 1
    assert "dirty.csv:1: email" in r.stdout
    assert "example.com" not in r.stdout
