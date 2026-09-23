import importlib

import pytest

import app.config


def test_default_max_pdf_size(monkeypatch):
    monkeypatch.delenv("MAX_PDF_SIZE_MB", raising=False)
    importlib.reload(app.config)
    assert app.config.MAX_PDF_SIZE_MB == 10


def test_max_pdf_size_from_environment(monkeypatch):
    monkeypatch.setenv("MAX_PDF_SIZE_MB", "25")
    importlib.reload(app.config)
    assert app.config.MAX_PDF_SIZE_MB == 25


def test_max_pdf_size_rejects_non_numeric_values(monkeypatch):
    monkeypatch.setenv("MAX_PDF_SIZE_MB", "banana")
    with pytest.raises(ValueError):
        importlib.reload(app.config)


def test_max_pdf_size_rejects_non_positive_values(monkeypatch):
    monkeypatch.setenv("MAX_PDF_SIZE_MB", "0")
    with pytest.raises(ValueError):
        importlib.reload(app.config)
