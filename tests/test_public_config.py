"""Публичная конфигурация frontend не раскрывает секреты и безопасно рендерит HTML."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config  # noqa: E402
from control.api import RuntimeConfigStaticFiles, create_app  # noqa: E402
from control.public_config import public_config_script, render_public_html  # noqa: E402
from control.store import ControlStore  # noqa: E402


def _set_public_config(monkeypatch, *, blank: bool = False) -> None:
    values = {
        "BOT_NAME": "MeSync Test",
        "BOT_AVATAR_URL": "https://cdn.example/avatar.png?a=1&b=2",
        "APP_URL": "https://service.example",
        "BOT_URLS": {
            "max": "https://max.ru/test_bot?ref=docs",
            "tg": "https://t.me/test_bot",
        },
        "BOT_HANDLES": {"max": "@test_bot", "tg": "@test_bot"},
        "SUPPORT_TG_URL": "https://t.me/test_support",
        "SUPPORT_TG_HANDLE": "@test_support",
        "SUPPORT_EMAIL": "support@example.com",
        "LEGAL_PROVIDER_NAME_RU": "ООО «Тест & Ко»",
        "LEGAL_PROVIDER_NAME_EN": "Test & Co LLC",
        "LEGAL_TAX_ID": "0000000000",
        "LEGAL_REGISTRATION_ID": "0000000000000",
        "LEGAL_TERMS_VERSION": "2026-01-01",
        "LEGAL_PRIVACY_VERSION": "2026-01-02",
        "LANDING_DESCRIPTION": "Описание <тестовой> страницы & сервиса",
        "LANDING_OFFER_TITLE": "Пробный период",
        "LANDING_OFFER_TEXT": "Условия & подробности",
        "LANDING_ANALYTICS_NOTICE": "Используется аналитика & cookies",
        "VK_ADS_PIXEL_ID": "1234567",
        "VK_ADS_UTM_SOURCE": "vkads",
        "VK_ADS_UTM_MEDIUM": "cpc",
    }
    if blank:
        values.update({
            "BOT_AVATAR_URL": "",
            "BOT_URLS": {"max": "", "tg": ""},
            "BOT_HANDLES": {"max": "", "tg": ""},
            "SUPPORT_TG_URL": "",
            "SUPPORT_TG_HANDLE": "",
            "SUPPORT_EMAIL": "",
            "LEGAL_PROVIDER_NAME_RU": "",
            "LEGAL_PROVIDER_NAME_EN": "",
            "LEGAL_TAX_ID": "",
            "LEGAL_REGISTRATION_ID": "",
            "LANDING_OFFER_TITLE": "",
            "LANDING_OFFER_TEXT": "",
            "VK_ADS_PIXEL_ID": "",
        })
    for name, value in values.items():
        monkeypatch.setattr(config, name, value)


def test_public_config_script_is_valid_and_script_safe(monkeypatch):
    _set_public_config(monkeypatch)
    monkeypatch.setattr(config, "BOT_NAME", "</script><strong>Test & Co</strong>")

    script = public_config_script()

    assert "</script>" not in script
    assert "\\u003c" in script
    payload = script.removeprefix("window.__MESYNC_PUBLIC_CONFIG__=").removesuffix(";\n")
    parsed = json.loads(payload)
    assert parsed["botName"] == "</script><strong>Test & Co</strong>"
    assert parsed["botLinks"]["tg"] == "https://t.me/test_bot"
    assert parsed["support"]["email"] == "support@example.com"
    assert parsed["landing"]["description"] == "Описание <тестовой> страницы & сервиса"
    assert parsed["trackers"]["vkAds"] == {
        "enabled": True, "pixelId": "1234567", "utmSource": "vkads"}
    assert "LEGAL_PROVIDER_NAME_RU" not in script


def test_render_public_html_fills_links_support_and_legal(monkeypatch):
    _set_public_config(monkeypatch)
    source = "\n".join([
        "<title>__MESYNC_BOT_NAME__</title>",
        "__MESYNC_FAVICON_LINKS__",
        "__MESYNC_BROWSER_AVATAR__",
        "__MESYNC_BROWSER_BOT_LINKS__",
        "__MESYNC_LEGAL_OFFER_INTRO_RU__",
        "__MESYNC_LEGAL_OFFER_INTRO_EN__",
        "__MESYNC_LEGAL_REQUISITES_RU__",
        "__MESYNC_LEGAL_REQUISITES_EN__",
        "__MESYNC_LEGAL_CONTROLLER_RU__",
        "__MESYNC_LEGAL_CONTROLLER_EN__",
        "__MESYNC_SUPPORT_CONTACT_RU__",
        "__MESYNC_SUPPORT_CONTACT_EN__",
        "__MESYNC_APP_URL__",
        "__MESYNC_LANDING_DESCRIPTION__",
        "__MESYNC_LANDING_OFFER__",
        "__MESYNC_LANDING_ANALYTICS_NOTICE__",
        "__MESYNC_LANDING_JSON_LD__",
        "__MESYNC_TRACKER_DATA_RU__",
        "__MESYNC_TRACKER_DATA_EN__",
        "__MESYNC_TRACKER_PURPOSE_RU__",
        "__MESYNC_TRACKER_PURPOSE_EN__",
        "__MESYNC_TRACKER_THIRD_PARTY_RU__",
        "__MESYNC_TRACKER_THIRD_PARTY_EN__",
        "__MESYNC_TRACKER_COOKIES_RU__",
        "__MESYNC_TRACKER_COOKIES_EN__",
    ])

    rendered = render_public_html(source)

    assert "__MESYNC_" not in rendered
    assert "ООО «Тест &amp; Ко»" in rendered
    assert "Test &amp; Co LLC" in rendered
    assert "support@example.com" in rendered
    assert "https://max.ru/test_bot?ref=docs&amp;start=web" in rendered
    assert "https://t.me/test_bot?start=web" in rendered
    assert "https://cdn.example/avatar.png?a=1&amp;b=2" in rendered
    assert "Описание &lt;тестовой&gt; страницы &amp; сервиса" in rendered
    assert "Пробный период" in rendered and "Условия &amp; подробности" in rendered
    assert "Используется аналитика &amp; cookies" in rendered
    assert "Top.Mail.Ru" in rendered
    assert '"description":"Описание \\u003cтестовой\\u003e страницы \\u0026 сервиса"' in rendered


def test_render_public_html_has_neutral_blank_state(monkeypatch):
    _set_public_config(monkeypatch, blank=True)
    source = "\n".join([
        "__MESYNC_BROWSER_AVATAR__",
        "__MESYNC_FAVICON_LINKS__",
        "__MESYNC_BROWSER_BOT_LINKS__",
        "__MESYNC_LEGAL_REQUISITES_RU__",
        "__MESYNC_SUPPORT_CONTACT_RU__",
        "__MESYNC_LANDING_OFFER__",
        "__MESYNC_LANDING_ANALYTICS_NOTICE__",
        "__MESYNC_TRACKER_THIRD_PARTY_RU__",
        "__MESYNC_TRACKER_COOKIES_RU__",
    ])

    rendered = render_public_html(source)

    assert "__MESYNC_" not in rendered
    assert "Ссылки на ботов не настроены" in rendered
    assert "Сведения заполняются владельцем развёртывания" in rendered
    assert "Контакты для обращений задаются владельцем" in rendered
    assert 'href=""' not in rendered
    assert "Top.Mail.Ru" not in rendered
    assert "static-entry-offer" not in rendered


def test_public_config_endpoint_uses_current_runtime_values(tmp_path, monkeypatch):
    _set_public_config(monkeypatch)
    app = create_app(ControlStore(tmp_path / "control.json"))

    with TestClient(app) as client:
        response = client.get("/api/public-config.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("application/javascript")
    assert '"botName":"MeSync Test"' in response.text
    assert "LEGAL_PROVIDER_NAME_RU" not in response.text


def test_vk_landing_redirect_preserves_attribution(tmp_path, monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    _set_public_config(monkeypatch)
    app = create_app(ControlStore(tmp_path / "control.json"))
    with TestClient(app) as client:
        response = client.get(
            "/vk?rb_clickid=click-123&utm_campaign=campaign-7&utm_source=spoof"
            "&utm_medium=spoof",
            follow_redirects=False,
        )

    assert response.status_code == 302
    target = urlsplit(response.headers["location"])
    assert target.path == "/"
    assert parse_qs(target.query) == {
        "rb_clickid": ["click-123"],
        "utm_campaign": ["campaign-7"],
        "utm_source": ["vkads"],
        "utm_medium": ["cpc"],
    }


def test_runtime_static_files_render_html_only(tmp_path, monkeypatch):
    _set_public_config(monkeypatch)
    (tmp_path / "index.html").write_text(
        "<h1>__MESYNC_BOT_NAME__</h1>__MESYNC_BROWSER_BOT_LINKS__",
        encoding="utf-8",
    )
    (tmp_path / "asset.txt").write_text("__MESYNC_BOT_NAME__", encoding="utf-8")
    app = FastAPI()
    app.mount("/", RuntimeConfigStaticFiles(directory=tmp_path, html=True))

    with TestClient(app) as client:
        page = client.get("/")
        asset = client.get("/asset.txt")

    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "<h1>MeSync Test</h1>" in page.text
    assert "https://t.me/test_bot?start=web" in page.text
    assert asset.text == "__MESYNC_BOT_NAME__"


def test_all_public_html_templates_render_without_placeholders(monkeypatch):
    _set_public_config(monkeypatch, blank=True)
    root = Path(__file__).resolve().parents[1] / "web"
    templates = [root / "index.html", *sorted((root / "public").rglob("*.html"))]

    for template in templates:
        rendered = render_public_html(template.read_text(encoding="utf-8"))
        assert "__MESYNC_" not in rendered, template
        assert "%MESYNC_" not in rendered, template


def test_built_public_pages_use_runtime_config(tmp_path, monkeypatch):
    dist = config.ROOT / "web" / "dist"
    if not dist.is_dir():
        pytest.skip("web/dist is built by the frontend job")
    _set_public_config(monkeypatch)
    app = create_app(ControlStore(tmp_path / "control.json"))
    paths = (
        "/",
        "/legal/",
        "/legal/terms/",
        "/legal/privacy/",
        "/pay-return.html",
        "/terms.html",
        "/ya_market",
    )

    with TestClient(app) as client:
        responses = {path: client.get(path) for path in paths}
        admin = client.get("/admin/")
        script = client.get("/api/public-config.js")

    for path, response in responses.items():
        assert response.status_code == 200, path
        assert "__MESYNC_" not in response.text, path
        assert "%MESYNC_" not in response.text, path
    assert "MeSync Test" in responses["/"].text
    assert "Описание &lt;тестовой&gt; страницы &amp; сервиса" in responses["/"].text
    assert "Пробный период" in responses["/"].text
    assert "Используется аналитика &amp; cookies" in responses["/"].text
    assert "ООО «Тест &amp; Ко»" in responses["/legal/terms/"].text
    assert "Top.Mail.Ru" in responses["/legal/privacy/"].text
    assert admin.status_code == 200
    assert "/api/public-config.js" in admin.text
    assert "/admin/api/public-config.js" not in admin.text
    assert '"botName":"MeSync Test"' in script.text
    assert '"pixelId":"1234567"' in script.text
