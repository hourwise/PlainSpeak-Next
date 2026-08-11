"""Tests for multi-format document reader."""

import pytest
from pathlib import Path
from plainspeak.reader import read_text, read_html, read_auto, get_supported_extensions


class TestReadText:
    def test_read_plain_text(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello world", encoding="utf-8")
        text = read_text(f)
        assert text == "Hello world"

    def test_read_utf8_with_bom(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"\xef\xbb\xbfHello world")
        text = read_text(f)
        assert "Hello world" in text

    def test_read_latin1_fallback(self, tmp_path):
        f = tmp_path / "test.txt"
        # Write Latin-1 encoded text with accented characters
        f.write_bytes(b"caf\xe9 renaissance")
        text = read_text(f)
        assert "caf" in text


class TestReadHTML:
    def test_extract_visible_text(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text(
            "<html><body><p>Hello world</p><p>Second paragraph</p></body></html>"
        )
        text = read_html(f)
        assert "Hello world" in text
        assert "Second paragraph" in text

    def test_strips_scripts(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text(
            "<html><head><script>alert('xss')</script></head>"
            "<body><p>Visible text</p></body></html>"
        )
        text = read_html(f)
        assert "alert" not in text
        assert "Visible text" in text

    def test_strips_styles(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text(
            "<html><head><style>body { color: red; }</style></head>"
            "<body><p>Content</p></body></html>"
        )
        text = read_html(f)
        assert "color" not in text
        assert "Content" in text


class TestReadAuto:
    def test_auto_detect_txt(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("Hello world")
        text, fmt = read_auto(f)
        assert "Hello world" in text
        assert "plain text" in fmt.lower() or "txt" in fmt.lower()

    def test_auto_detect_md(self, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("# Heading\nContent")
        text, fmt = read_auto(f)
        assert "Heading" in text
        assert "Content" in text

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_auto("/nonexistent/path/file.txt")

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "data.xyz"
        f.write_text("test")
        text, fmt = read_auto(f)
        # Should fall back to plain text
        assert "test" in text


class TestSupportedExtensions:
    def test_returns_dict(self):
        exts = get_supported_extensions()
        assert isinstance(exts, dict)
        assert ".txt" in exts
        assert ".docx" in exts
        assert ".pdf" in exts
        assert ".html" in exts
