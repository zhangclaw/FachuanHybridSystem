"""Tests for apps.automation.services.scraper.sites.court_zxfw_login_private.login_service."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from apps.automation.services.scraper.sites.court_zxfw_login_private.login_service import (
    CourtZxfwHttpLoginService,
    _normalize_public_key,
    _sm2_encrypt,
)


class TestNormalizePublicKey:
    def test_04_prefix_130_chars(self) -> None:
        hex_key = "04" + "ab" * 64  # 04 + 128 hex chars = 130 total
        result = _normalize_public_key(hex_key)
        assert len(result) == 128
        assert not result.startswith("04")

    def test_128_chars_no_prefix(self) -> None:
        hex_key = "ab" * 64
        result = _normalize_public_key(hex_key)
        assert len(result) == 128
        assert result == hex_key

    def test_invalid_length_raises(self) -> None:
        with pytest.raises(ValueError, match="公钥格式不正确"):
            _normalize_public_key("abcd")

    def test_uppercase_input_is_lowercased(self) -> None:
        hex_key = "AB" * 64
        result = _normalize_public_key(hex_key)
        assert result == "ab" * 64

    def test_strips_whitespace(self) -> None:
        hex_key = "  " + "ab" * 64 + "  "
        result = _normalize_public_key(hex_key)
        assert result == "ab" * 64


class TestSm2Encrypt:
    def test_encrypt_returns_hex_string(self) -> None:
        public_key = "ab" * 64
        with patch("apps.automation.services.scraper.sites.court_zxfw_login_private.login_service.sm2") as mock_sm2:
            mock_cipher = MagicMock()
            mock_cipher.encrypt.return_value = b"\x00\x01\x02"
            mock_sm2.CryptSM2.return_value = mock_cipher

            result = _sm2_encrypt("test_password", public_key)
        assert isinstance(result, str)
        int(result, 16)  # Should not raise

    def test_encrypt_raises_on_empty_result(self) -> None:
        public_key = "ab" * 64
        with patch("apps.automation.services.scraper.sites.court_zxfw_login_private.login_service.sm2") as mock_sm2:
            mock_cipher = MagicMock()
            mock_cipher.encrypt.return_value = b""
            mock_sm2.CryptSM2.return_value = mock_cipher

            with pytest.raises(ValueError, match="SM2 加密结果为空"):
                _sm2_encrypt("test", public_key)

    def test_encrypt_raises_on_unknown_type(self) -> None:
        public_key = "ab" * 64
        with patch("apps.automation.services.scraper.sites.court_zxfw_login_private.login_service.sm2") as mock_sm2:
            mock_cipher = MagicMock()
            mock_cipher.encrypt.return_value = 12345
            mock_sm2.CryptSM2.return_value = mock_cipher

            with pytest.raises(TypeError, match="SM2 加密返回未知类型"):
                _sm2_encrypt("test", public_key)

    def test_encrypt_string_result(self) -> None:
        public_key = "ab" * 64
        with patch("apps.automation.services.scraper.sites.court_zxfw_login_private.login_service.sm2") as mock_sm2:
            mock_cipher = MagicMock()
            mock_cipher.encrypt.return_value = "deadbeef"
            mock_sm2.CryptSM2.return_value = mock_cipher

            result = _sm2_encrypt("test", public_key)
        assert result == "deadbeef"


class TestCourtZxfwHttpLoginService:
    def test_init_default_recognizer(self) -> None:
        with patch(
            "apps.automation.services.scraper.core.captcha_recognizer.DdddocrRecognizer"
        ) as mock_rec:
            mock_rec.return_value = MagicMock()
            svc = CourtZxfwHttpLoginService()
        assert svc._recognizer is not None

    def test_init_custom_recognizer(self) -> None:
        mock_rec = MagicMock()
        svc = CourtZxfwHttpLoginService(captcha_recognizer=mock_rec)
        assert svc._recognizer is mock_rec

    def test_recognize_captcha_strips_prefix(self) -> None:
        svc = CourtZxfwHttpLoginService(captcha_recognizer=MagicMock())
        svc._recognizer.recognize.return_value = "ABC123"
        raw_b64 = base64.b64encode(b"image-data").decode()
        prefixed = f"data:image/jpeg;base64,{raw_b64}"
        result = svc._recognize_captcha(prefixed)
        assert result == "ABC123"
        svc._recognizer.recognize.assert_called_once_with(b"image-data")

    def test_login_returns_failure_after_max_retries(self) -> None:
        svc = CourtZxfwHttpLoginService(captcha_recognizer=MagicMock())

        with patch.object(svc, "_build_client") as mock_build:
            mock_client = MagicMock()
            mock_build.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_build.return_value.__exit__ = MagicMock(return_value=False)

            pk_resp = MagicMock()
            pk_resp.json.return_value = {"code": 200, "data": "ab" * 64}
            pk_resp.raise_for_status = MagicMock()

            captcha_resp = MagicMock()
            captcha_b64 = base64.b64encode(b"captcha-image").decode()
            captcha_resp.json.return_value = {"code": 200, "data": {"id": "c1", "jpg": f"data:image/jpeg;base64,{captcha_b64}"}}
            captcha_resp.raise_for_status = MagicMock()

            login_resp = MagicMock()
            login_resp.json.return_value = {"code": 500, "message": "验证码错误"}
            login_resp.raise_for_status = MagicMock()

            mock_client.get.side_effect = [pk_resp, captcha_resp, captcha_resp, captcha_resp]
            mock_client.post.return_value = login_resp

            svc._recognizer.recognize.return_value = "1234"

            result = svc.login("user", "pass", max_retries=3)
        assert result["success"] is False
        assert "3 次" in result["message"]

    def test_login_returns_failure_when_captcha_not_recognized(self) -> None:
        svc = CourtZxfwHttpLoginService(captcha_recognizer=MagicMock())

        with patch.object(svc, "_build_client") as mock_build:
            mock_client = MagicMock()
            mock_build.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_build.return_value.__exit__ = MagicMock(return_value=False)

            pk_resp = MagicMock()
            pk_resp.json.return_value = {"code": 200, "data": "ab" * 64}
            pk_resp.raise_for_status = MagicMock()

            captcha_resp = MagicMock()
            captcha_b64 = base64.b64encode(b"captcha-image").decode()
            captcha_resp.json.return_value = {"code": 200, "data": {"id": "c1", "jpg": f"data:image/jpeg;base64,{captcha_b64}"}}
            captcha_resp.raise_for_status = MagicMock()

            mock_client.get.side_effect = [pk_resp, captcha_resp, captcha_resp, captcha_resp]
            svc._recognizer.recognize.return_value = None

            result = svc.login("user", "pass", max_retries=3)
        assert result["success"] is False

    def test_login_success(self) -> None:
        svc = CourtZxfwHttpLoginService(captcha_recognizer=MagicMock())

        with patch.object(svc, "_build_client") as mock_build:
            mock_client = MagicMock()
            mock_build.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_build.return_value.__exit__ = MagicMock(return_value=False)

            pk_resp = MagicMock()
            pk_resp.json.return_value = {"code": 200, "data": "ab" * 64}
            pk_resp.raise_for_status = MagicMock()

            captcha_resp = MagicMock()
            captcha_b64 = base64.b64encode(b"captcha-image").decode()
            captcha_resp.json.return_value = {"code": 200, "data": {"id": "c1", "jpg": f"data:image/jpeg;base64,{captcha_b64}"}}
            captcha_resp.raise_for_status = MagicMock()

            login_resp = MagicMock()
            login_resp.json.return_value = {
                "code": 200,
                "data": {"token": "tok123", "userId": "u1", "username": "testuser"},
            }
            login_resp.raise_for_status = MagicMock()

            mock_client.get.side_effect = [pk_resp, captcha_resp]
            mock_client.post.return_value = login_resp
            svc._recognizer.recognize.return_value = "ABCD"

            result = svc.login("user", "pass", max_retries=3)
        assert result["success"] is True
        assert result["token"] == "tok123"
        assert result["userId"] == "u1"
