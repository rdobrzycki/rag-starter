from __future__ import annotations

from lambda_handler.utils.hashing import sha256_text


def test_sha256_text_is_stable():
    h1 = sha256_text("hello")
    h2 = sha256_text("hello")
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_text_different_inputs():
    assert sha256_text("hello") != sha256_text("world")


def test_sha256_text_handles_unicode():
    h = sha256_text("cafĂ© ĂŒber")
    assert len(h) == 64
