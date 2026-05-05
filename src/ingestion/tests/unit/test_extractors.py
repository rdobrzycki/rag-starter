"""Unit tests for extractor registry."""

import json
from unittest.mock import patch

import pandas as pd

from lambda_handler.processing.extractors import (
    CsvExtractor,
    DocxExtractor,
    ExcelExtractor,
    ExtractorRegistry,
    JsonExtractor,
    PdfExtractor,
    PlainTextExtractor,
    default_extractor_registry,
)


class TestPdfExtractor:
    """Tests for PdfExtractor."""

    def test_extract_simple_pdf(self):
        """Test extraction from simple PDF (mocked)."""
        extractor = PdfExtractor()
        assert hasattr(extractor, "extract")
        assert callable(extractor.extract)


class TestDocxExtractor:
    """Tests for DocxExtractor."""

    def test_extract_simple_docx(self):
        """Test extraction from simple DOCX (mocked)."""
        extractor = DocxExtractor()
        assert hasattr(extractor, "extract")
        assert callable(extractor.extract)


class TestPlainTextExtractor:
    """Tests for PlainTextExtractor."""

    def test_extract_utf8_text(self):
        """Test extraction from UTF-8 text."""
        extractor = PlainTextExtractor()
        data = "Hello, world!\nThis is a test.".encode("utf-8")
        text = extractor.extract(data, "test.txt")
        assert text == "Hello, world!\nThis is a test."

    def test_extract_with_unicode(self):
        """Test extraction with Unicode characters."""
        extractor = PlainTextExtractor()
        data = "Hello 世界! Café ☕".encode("utf-8")
        text = extractor.extract(data, "test.txt")
        assert "世界" in text
        assert "Café" in text
        assert "☕" in text

    def test_extract_with_invalid_utf8(self):
        """Test extraction with invalid UTF-8 (errors='ignore')."""
        extractor = PlainTextExtractor()
        data = b"Hello \xff\xfe World"
        text = extractor.extract(data, "test.txt")
        assert "Hello" in text
        assert "World" in text

    def test_extract_empty_file(self):
        """Test extraction from empty file."""
        extractor = PlainTextExtractor()
        text = extractor.extract(b"", "empty.txt")
        assert text == ""


class TestExtractorRegistry:
    """Tests for ExtractorRegistry."""

    def test_register_and_get(self):
        """Test registering and retrieving extractors."""
        registry = ExtractorRegistry()
        extractor = PlainTextExtractor()
        registry.register(".txt", extractor)
        assert registry.get(".txt") is extractor

    def test_get_nonexistent_extension(self):
        """Test getting extractor for unregistered extension."""
        assert ExtractorRegistry().get(".xyz") is None

    def test_case_insensitive_extension(self):
        """Test extension lookup is case-insensitive."""
        registry = ExtractorRegistry()
        extractor = PlainTextExtractor()
        registry.register(".TXT", extractor)
        assert registry.get(".txt") is extractor

    def test_register_overwrites_existing(self):
        """Test registering same extension twice overwrites."""
        registry = ExtractorRegistry()
        registry.register(".txt", PlainTextExtractor())
        registry.register(".txt", PdfExtractor())
        assert isinstance(registry.get(".txt"), PdfExtractor)

    def test_extensions_list(self):
        """Test getting list of registered extensions."""
        registry = ExtractorRegistry()
        registry.register(".pdf", PdfExtractor())
        registry.register(".txt", PlainTextExtractor())
        registry.register(".docx", DocxExtractor())
        extensions = registry.extensions()
        assert len(extensions) == 3
        assert ".pdf" in extensions
        assert ".txt" in extensions
        assert ".docx" in extensions

    def test_empty_registry_extensions(self):
        """Test extensions list for empty registry."""
        assert ExtractorRegistry().extensions() == []

    def test_multiple_extensions_same_extractor(self):
        """Test registering same extractor for multiple extensions."""
        registry = ExtractorRegistry()
        extractor = PlainTextExtractor()
        registry.register(".txt", extractor)
        registry.register(".md", extractor)
        assert registry.get(".txt") is extractor
        assert registry.get(".md") is extractor


class TestDefaultExtractorRegistry:
    """Tests for default_extractor_registry factory."""

    def test_default_registry_has_pdf(self):
        """Test default registry includes PDF extractor."""
        registry = default_extractor_registry()
        extractor = registry.get(".pdf")
        assert extractor is not None
        assert isinstance(extractor, PdfExtractor)

    def test_default_registry_has_docx(self):
        """Test default registry includes DOCX extractor."""
        registry = default_extractor_registry()
        extractor = registry.get(".docx")
        assert extractor is not None
        assert isinstance(extractor, DocxExtractor)

    def test_default_registry_has_plain_text(self):
        """Test default registry includes plain text extractors."""
        registry = default_extractor_registry()
        for ext in [".txt", ".md", ".html", ".htm"]:
            extractor = registry.get(ext)
            assert extractor is not None
            assert isinstance(extractor, PlainTextExtractor)

    def test_default_registry_all_extensions(self):
        """Test default registry has all expected extensions."""
        registry = default_extractor_registry()
        expected = [".pdf", ".docx", ".txt", ".md", ".html", ".htm"]
        for ext in expected:
            assert ext in registry.extensions()

    def test_default_registry_unknown_extension(self):
        """Test default registry returns None for unknown extension."""
        assert default_extractor_registry().get(".xyz") is None

    def test_default_registry_case_insensitive(self):
        """Test default registry works with uppercase extensions."""
        extractor = default_extractor_registry().get(".PDF")
        assert extractor is not None
        assert isinstance(extractor, PdfExtractor)


class TestCsvExtractor:
    """Tests for CsvExtractor."""

    def test_extract_basic_csv(self):
        """Test extraction from basic comma-separated CSV."""
        extractor = CsvExtractor()
        data = b"Product,Price,Stock\nWidget,10,5\nGadget,20,3"
        text = extractor.extract(data, "test.csv")

        assert "Row 1: Product=Widget, Price=10, Stock=5" in text
        assert "Row 2: Product=Gadget, Price=20, Stock=3" in text

    def test_extract_tab_delimited_csv(self):
        """Test extraction from tab-delimited CSV."""
        extractor = CsvExtractor()
        data = b"Name\tAge\tCity\nAlice\t30\tNYC\nBob\t25\tLA"
        text = extractor.extract(data, "test.tsv")

        assert "Row 1:" in text
        assert "Name=Alice" in text
        assert "Age=30" in text
        assert "City=NYC" in text

    def test_extract_empty_csv(self):
        """Test extraction from empty CSV."""
        extractor = CsvExtractor()
        text = extractor.extract(b"", "empty.csv")
        assert text == ""

    def test_extract_csv_with_headers_only(self):
        """Test extraction from CSV with only headers."""
        extractor = CsvExtractor()
        data = b"Column1,Column2,Column3"
        text = extractor.extract(data, "headers.csv")
        # Empty dataframe (no data rows)
        assert text == ""

    def test_extract_malformed_csv(self):
        """Test extraction from malformed CSV returns empty."""
        extractor = CsvExtractor()
        data = b"\xff\xfe invalid binary data"
        text = extractor.extract(data, "malformed.csv")
        assert text == ""

    def test_extract_csv_with_unicode(self):
        """Test extraction from CSV with Unicode characters."""
        extractor = CsvExtractor()
        data = "Name,City\nJosé,São Paulo\n田中,東京".encode("utf-8")
        text = extractor.extract(data, "unicode.csv")

        assert "José" in text
        assert "São Paulo" in text
        assert "田中" in text
        assert "東京" in text


class TestJsonExtractor:
    """Tests for JsonExtractor."""

    def test_extract_simple_json_object(self):
        """Test extraction from simple JSON object."""
        extractor = JsonExtractor()
        data = json.dumps({"name": "John Doe", "age": 30, "city": "NYC"}).encode("utf-8")
        text = extractor.extract(data, "test.json")

        assert "name: John Doe" in text
        assert "age: 30" in text
        assert "city: NYC" in text

    def test_extract_nested_json_object(self):
        """Test extraction from nested JSON object."""
        extractor = JsonExtractor()
        data = json.dumps(
            {
                "user": {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "settings": {"theme": "dark", "notifications": True},
                }
            }
        ).encode("utf-8")
        text = extractor.extract(data, "nested.json")

        assert "user.name: Alice" in text
        assert "user.email: alice@example.com" in text
        assert "user.settings.theme: dark" in text
        assert "user.settings.notifications: True" in text

    def test_extract_json_with_array(self):
        """Test extraction from JSON with arrays."""
        extractor = JsonExtractor()
        data = json.dumps(
            {"items": [{"name": "Widget", "price": 10.99}, {"name": "Gadget", "price": 20.50}]}
        ).encode("utf-8")
        text = extractor.extract(data, "array.json")

        assert "items[0].name: Widget" in text
        assert "items[0].price: 10.99" in text
        assert "items[1].name: Gadget" in text
        assert "items[1].price: 20.5" in text

    def test_extract_json_with_primitive_array(self):
        """Test extraction from JSON with array of primitives."""
        extractor = JsonExtractor()
        data = json.dumps({"tags": ["python", "aws", "lambda"]}).encode("utf-8")
        text = extractor.extract(data, "tags.json")

        assert "tags[0]: python" in text
        assert "tags[1]: aws" in text
        assert "tags[2]: lambda" in text

    def test_extract_empty_json_object(self):
        """Test extraction from empty JSON object."""
        extractor = JsonExtractor()
        data = b"{}"
        text = extractor.extract(data, "empty.json")
        assert text == ""

    def test_extract_malformed_json(self):
        """Test extraction from malformed JSON returns empty."""
        extractor = JsonExtractor()
        data = b"{invalid json syntax"
        text = extractor.extract(data, "malformed.json")
        assert text == ""

    def test_extract_json_with_unicode(self):
        """Test extraction from JSON with Unicode characters."""
        extractor = JsonExtractor()
        data = json.dumps({"message": "Hello 世界! Café ☕"}).encode("utf-8")
        text = extractor.extract(data, "unicode.json")

        assert "message:" in text
        assert "世界" in text
        assert "Café" in text
        assert "☕" in text


class TestExcelExtractor:
    """Tests for ExcelExtractor."""

    def test_extractor_has_extract_method(self):
        """Test ExcelExtractor has extract method."""
        extractor = ExcelExtractor()
        assert hasattr(extractor, "extract")
        assert callable(extractor.extract)

    def test_extract_malformed_excel(self):
        """Test extraction from malformed Excel returns empty."""
        extractor = ExcelExtractor()
        data = b"not an excel file"
        text = extractor.extract(data, "malformed.xlsx")
        assert text == ""

    @patch("lambda_handler.processing.extractors.pd.read_excel")
    def test_extract_uses_openpyxl_for_xlsx(self, mock_read_excel):
        """Test .xlsx files are parsed with openpyxl engine."""
        extractor = ExcelExtractor()
        mock_read_excel.return_value = {
            "Sheet1": pd.DataFrame({"Product": ["Widget"], "Price": [10]})
        }

        text = extractor.extract(b"fake-xlsx", "report.xlsx")

        assert "=== Sheet: Sheet1 ===" in text
        mock_read_excel.assert_called_once()
        assert mock_read_excel.call_args.kwargs["engine"] == "openpyxl"

    @patch("lambda_handler.processing.extractors.pd.read_excel")
    def test_extract_uses_xlrd_for_xls(self, mock_read_excel):
        """Test .xls files are parsed with xlrd engine."""
        extractor = ExcelExtractor()
        mock_read_excel.return_value = {
            "Sheet1": pd.DataFrame({"Product": ["Widget"], "Price": [10]})
        }

        text = extractor.extract(b"fake-xls", "report.xls")

        assert "=== Sheet: Sheet1 ===" in text
        mock_read_excel.assert_called_once()
        assert mock_read_excel.call_args.kwargs["engine"] == "xlrd"


class TestDefaultExtractorRegistryNewFormats:
    """Tests for default_extractor_registry with new formats."""

    def test_default_registry_has_csv(self):
        """Test default registry includes CSV extractor."""
        registry = default_extractor_registry()
        extractor = registry.get(".csv")
        assert extractor is not None
        assert isinstance(extractor, CsvExtractor)

    def test_default_registry_has_json(self):
        """Test default registry includes JSON extractor."""
        registry = default_extractor_registry()
        extractor = registry.get(".json")
        assert extractor is not None
        assert isinstance(extractor, JsonExtractor)

    def test_default_registry_has_xlsx(self):
        """Test default registry includes XLSX extractor."""
        registry = default_extractor_registry()
        extractor = registry.get(".xlsx")
        assert extractor is not None
        assert isinstance(extractor, ExcelExtractor)

    def test_default_registry_has_xls(self):
        """Test default registry includes XLS extractor."""
        registry = default_extractor_registry()
        extractor = registry.get(".xls")
        assert extractor is not None
        assert isinstance(extractor, ExcelExtractor)

    def test_default_registry_all_new_extensions(self):
        """Test default registry has all new file extensions."""
        registry = default_extractor_registry()
        extensions = registry.extensions()

        assert ".csv" in extensions
        assert ".json" in extensions
        assert ".xlsx" in extensions
        assert ".xls" in extensions
