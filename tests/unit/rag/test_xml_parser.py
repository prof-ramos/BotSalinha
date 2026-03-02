"""Unit tests for RepomixXMLParser."""

from pathlib import Path

import pytest

from src.rag.parser.xml_parser import (
    LANGUAGE_MAP,
    RagFileNotFoundError,
    RagInvalidFormatError,
    RepomixXMLParser,
    XMLParseError,
)


@pytest.mark.unit
class TestRepomixXMLParserInit:
    """Tests for RepomixXMLParser initialization."""

    def test_init_valid_file(self, tmp_path) -> None:
        """Should initialize successfully with a valid .xml file path."""
        # Create a temporary XML file
        xml_file = tmp_path / "test.xml"
        xml_file.write_text('<?xml version="1.0"?><root></root>')

        parser = RepomixXMLParser(xml_file)

        assert parser._file_path == xml_file

    def test_init_file_not_found(self, tmp_path) -> None:
        """Should raise RagFileNotFoundError when file doesn't exist."""
        non_existent = tmp_path / "nonexistent.xml"

        with pytest.raises(RagFileNotFoundError) as exc_info:
            RepomixXMLParser(non_existent)

        assert "File not found" in str(exc_info.value)

    def test_init_invalid_extension(self, tmp_path) -> None:
        """Should raise RagInvalidFormatError for non-.xml files."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("some text")

        with pytest.raises(RagInvalidFormatError) as exc_info:
            RepomixXMLParser(txt_file)

        assert "Expected .xml file" in str(exc_info.value)

    def test_init_with_string_path(self, tmp_path) -> None:
        """Should accept string path instead of Path object."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text('<?xml version="1.0"?><root></root>')

        # Pass string path instead of Path object
        parser = RepomixXMLParser(str(xml_file))

        assert isinstance(parser._file_path, Path)


@pytest.mark.unit
class TestRepomixXMLParserParse:
    """Tests for RepomixXMLParser.parse method."""

    @pytest.mark.asyncio
    async def test_parse_basic(self, tmp_path) -> None:
        """Should parse XML and return list of dicts."""
        xml_content = '''<?xml version="1.0"?>
<output>
    <file path="src/main.py">def hello():
    print("Hello World")
</file>
    <file path="src/utils.ts">const x = 42;</file>
</output>'''
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(xml_content)

        parser = RepomixXMLParser(xml_file)
        result = await parser.parse()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["file_path"] == "src/main.py"
        assert result[0]["language"] == "python"
        assert "def hello():" in result[0]["text"]
        assert result[1]["file_path"] == "src/utils.ts"
        assert result[1]["language"] == "typescript"

    @pytest.mark.asyncio
    async def test_parse_empty_xml(self, tmp_path) -> None:
        """Should return empty list for XML with no file elements."""
        xml_content = '<?xml version="1.0"?><output></output>'
        xml_file = tmp_path / "empty.xml"
        xml_file.write_text(xml_content)

        parser = RepomixXMLParser(xml_file)
        result = await parser.parse()

        assert result == []

    @pytest.mark.asyncio
    async def test_parse_with_missing_path_attribute(self, tmp_path) -> None:
        """Should handle file elements without path attribute."""
        xml_content = '''<?xml version="1.0"?>
<output>
    <file>content without path</file>
</output>'''
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(xml_content)

        parser = RepomixXMLParser(xml_file)
        result = await parser.parse()

        assert len(result) == 1
        assert result[0]["file_path"] == "unknown"

    @pytest.mark.asyncio
    async def test_parse_line_numbers(self, tmp_path) -> None:
        """Should correctly calculate line_start and line_end."""
        xml_content = '''<?xml version="1.0"?>
<output>
    <file path="test.py">line1
line2
line3
</file>
</output>'''
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(xml_content)

        parser = RepomixXMLParser(xml_file)
        result = await parser.parse()

        assert len(result) == 1
        assert result[0]["line_start"] == 1
        assert result[0]["line_end"] == 3  # 3 newlines = 4 lines, but stripped

    @pytest.mark.asyncio
    async def test_parse_empty_text_content(self, tmp_path) -> None:
        """Should handle empty text content in file elements (1-based indexing)."""
        xml_content = '''<?xml version="1.0"?>
<output>
    <file path="empty.py"></file>
    <file path="whitespace.py">   </file>
</output>'''
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(xml_content)

        parser = RepomixXMLParser(xml_file)
        result = await parser.parse()

        assert len(result) == 2
        assert result[0]["text"] == ""
        assert result[1]["text"] == ""
        # 1-based indexing even for empty files
        assert result[0]["line_start"] == 1
        assert result[0]["line_end"] == 0  # empty content = 0 lines
        assert result[1]["line_start"] == 1
        assert result[1]["line_end"] == 0  # whitespace stripped = empty

    @pytest.mark.asyncio
    async def test_parse_invalid_xml(self, tmp_path) -> None:
        """Should raise XMLParseError for invalid XML."""
        xml_content = 'this is not valid XML <<>>'
        xml_file = tmp_path / "invalid.xml"
        xml_file.write_text(xml_content)

        parser = RepomixXMLParser(xml_file)

        with pytest.raises(XMLParseError) as exc_info:
            await parser.parse()

        assert "Failed to parse XML file" in str(exc_info.value)


@pytest.mark.unit
class TestRepomixXMLParserLanguageDetection:
    """Tests for language detection from file extensions."""

    def test_detect_language_python(self) -> None:
        """Should detect Python language from .py extension."""
        assert LANGUAGE_MAP.get(".py") == "python"

    def test_detect_language_typescript(self) -> None:
        """Should detect TypeScript language from .ts and .tsx extensions."""
        assert LANGUAGE_MAP.get(".ts") == "typescript"
        assert LANGUAGE_MAP.get(".tsx") == "typescript"

    def test_detect_language_javascript(self) -> None:
        """Should detect JavaScript language from .js and .jsx extensions."""
        assert LANGUAGE_MAP.get(".js") == "javascript"
        assert LANGUAGE_MAP.get(".jsx") == "javascript"

    def test_detect_language_yaml(self) -> None:
        """Should detect YAML language from .yaml and .yml extensions."""
        assert LANGUAGE_MAP.get(".yaml") == "yaml"
        assert LANGUAGE_MAP.get(".yml") == "yaml"

    def test_detect_language_json(self) -> None:
        """Should detect JSON language from .json extension."""
        assert LANGUAGE_MAP.get(".json") == "json"

    def test_detect_language_markdown(self) -> None:
        """Should detect Markdown language from .md extension."""
        assert LANGUAGE_MAP.get(".md") == "markdown"

    @pytest.mark.asyncio
    async def test_detect_language_unknown_extension(self, tmp_path) -> None:
        """Should return 'text' for unknown file extensions."""
        xml_content = '''<?xml version="1.0"?>
<output>
    <file path="file.unknown">content</file>
</output>'''
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(xml_content)

        parser = RepomixXMLParser(xml_file)
        result = await parser.parse()

        assert result[0]["language"] == "text"


@pytest.mark.unit
class TestRepomixXMLParserExtractFileElement:
    """Tests for _extract_file_element method (tested via parse)."""

    @pytest.mark.asyncio
    async def test_extract_file_element_with_all_fields(self, tmp_path) -> None:
        """Should extract all fields from file element."""
        xml_content = '''<?xml version="1.0"?>
<output>
    <file path="src/core/agent.py">class Agent:
    pass
</file>
</output>'''
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(xml_content)

        parser = RepomixXMLParser(xml_file)
        result = await parser.parse()

        assert len(result) == 1
        file_data = result[0]
        assert "file_path" in file_data
        assert "language" in file_data
        assert "text" in file_data
        assert "line_start" in file_data
        assert "line_end" in file_data
        assert file_data["file_path"] == "src/core/agent.py"
        assert file_data["language"] == "python"
        assert "class Agent:" in file_data["text"]

    @pytest.mark.asyncio
    async def test_extract_multiple_files(self, tmp_path) -> None:
        """Should extract multiple file elements correctly."""
        xml_content = '''<?xml version="1.0"?>
<output>
    <file path="a.py">content A</file>
    <file path="b.py">content B</file>
    <file path="c.py">content C</file>
</output>'''
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(xml_content)

        parser = RepomixXMLParser(xml_file)
        result = await parser.parse()

        assert len(result) == 3
        assert result[0]["file_path"] == "a.py"
        assert result[1]["file_path"] == "b.py"
        assert result[2]["file_path"] == "c.py"
        assert result[0]["text"] == "content A"
        assert result[1]["text"] == "content B"
        assert result[2]["text"] == "content C"

    @pytest.mark.asyncio
    async def test_text_stripping(self, tmp_path) -> None:
        """Should strip whitespace from text content."""
        xml_content = '''<?xml version="1.0"?>
<output>
    <file path="test.py">
    indented content
    </file>
</output>'''
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(xml_content)

        parser = RepomixXMLParser(xml_file)
        result = await parser.parse()

        # Text should be stripped
        assert result[0]["text"] == "indented content"
        assert not result[0]["text"].startswith(" ")
        assert not result[0]["text"].endswith(" ")
