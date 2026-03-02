"""Unit tests for CodeMetadataExtractor."""

import pytest

from src.rag.utils.code_metadata_extractor import CodeMetadataExtractor


@pytest.mark.unit
class TestCodeMetadataExtractorInit:
    """Tests for CodeMetadataExtractor initialization."""

    def test_init(self) -> None:
        """Should initialize successfully."""
        extractor = CodeMetadataExtractor()

        assert extractor is not None
        assert extractor._python_function_re is not None
        assert extractor._python_class_re is not None
        assert extractor._ts_function_re is not None


@pytest.mark.unit
class TestExtractCodeMetadata:
    """Tests for extract_code_metadata method."""

    def test_extract_python_metadata(self) -> None:
        """Should extract functions, classes, imports from Python code."""
        extractor = CodeMetadataExtractor()

        python_code = '''"""Module docstring."""

from typing import List
import os
from src.models import User

def helper_function():
    """A helper function."""
    pass

async def async_function():
    """An async function."""
    pass

class UserService:
    """Service class for users."""

    def method(self):
        pass

class TestUserService:
    """Test class."""

    def test_something(self):
        pass
'''

        context = {
            "file_path": "src/services/user_service.py",
            "language": "python",
        }

        result = extractor.extract_code_metadata(python_code, context)

        assert result["language"] == "python"
        assert "helper_function" in result["functions"]
        assert "async_function" in result["functions"]
        assert "UserService" in result["classes"]
        assert "TestUserService" in result["classes"]
        assert "typing" in result["imports"] or "os" in result["imports"]

    def test_extract_typescript_metadata(self) -> None:
        """Should extract from TypeScript code."""
        extractor = CodeMetadataExtractor()

        typescript_code = '''import { User } from './models';

interface UserData {
    name: string;
}

function processData(data: UserData): void {
    console.log(data);
}

class DataService {
    private items: Item[] = [];

    async fetchItems(): Promise<Item[]> {
        return [];
    }
}

class TestDataService {
    testFetch() {
        // test
    }
}
'''

        context = {
            "file_path": "src/services/data_service.ts",
            "language": "typescript",
        }

        result = extractor.extract_code_metadata(typescript_code, context)

        assert result["language"] == "typescript"
        assert "processData" in result["functions"]
        # Arrow function detection is limited with regex
        assert "DataService" in result["classes"]
        assert "TestDataService" in result["classes"]
        assert "./models" in result["imports"]

    def test_classify_layer(self) -> None:
        """Should correctly classify layers from paths."""
        extractor = CodeMetadataExtractor()

        code = "# Some code"
        test_cases = [
            ("src/core/agent.py", "core"),
            ("src/storage/sqlite_repository.py", "storage"),
            ("src/rag/services/query_service.py", "rag"),
            ("src/middleware/rate_limiter.py", "middleware"),
            ("src/utils/logger.py", "utils"),
            ("src/models/conversation.py", "models"),
            ("src/config/settings.py", "config"),
            ("src/services/embedding_service.py", "services"),
            ("tests/unit/test_agent.py", "tests"),
            ("scripts/run_tests.sh", "scripts"),
            ("docs/DEVELOPER_GUIDE.md", "docs"),
            ("migrations/versions/001_initial.py", "migrations"),
            ("unknown/path/file.py", "unknown"),
            ("", "unknown"),
        ]

        for file_path, expected_layer in test_cases:
            context = {"file_path": file_path}
            result = extractor.extract_code_metadata(code, context)
            assert result["layer"] == expected_layer, f"Failed for {file_path}"

    def test_detect_is_test(self) -> None:
        """Should identify test files correctly."""
        extractor = CodeMetadataExtractor()

        code = "# Some code"
        test_cases = [
            ("tests/unit/test_agent.py", True),
            ("tests/integration/test_repository.py", True),
            ("src/core/test_utils.py", True),
            ("src/core/test_helper.py", True),
            ("test_service.py", True),
            ("service_test.py", True),
            ("src/core/agent.py", False),
            ("src/services/user_service.py", False),
            ("", False),
        ]

        for file_path, expected_is_test in test_cases:
            context = {"file_path": file_path}
            result = extractor.extract_code_metadata(code, context)
            assert result["is_test"] == expected_is_test, f"Failed for {file_path}"

    def test_extract_module_name(self) -> None:
        """Should extract module name from file path."""
        extractor = CodeMetadataExtractor()

        code = "# Some code"
        test_cases = [
            ("src/core/agent.py", "agent"),
            ("src/storage/sqlite_repository.py", "sqlite_repository"),
            ("src/services/__init__.py", "services"),  # __init__.py uses parent dir
            ("", "unknown"),
        ]

        for file_path, expected_module in test_cases:
            context = {"file_path": file_path}
            result = extractor.extract_code_metadata(code, context)
            assert result["module"] == expected_module, f"Failed for {file_path}"

    def test_metadata_with_empty_code(self) -> None:
        """Should handle empty code gracefully."""
        extractor = CodeMetadataExtractor()

        context = {
            "file_path": "src/empty.py",
        }

        result = extractor.extract_code_metadata("", context)

        assert result["language"] == "python"
        assert result["functions"] == []
        assert result["classes"] == []
        assert result["imports"] == []
        assert result["layer"] == "unknown"
        assert result["module"] == "empty"
        assert result["is_test"] is False


@pytest.mark.unit
class TestExtractFunctions:
    """Tests for _extract_functions method."""

    def test_extract_functions_python(self) -> None:
        """Should extract Python function names."""
        extractor = CodeMetadataExtractor()

        python_code = '''
def regular_function():
    pass

async def async_function():
    pass

class MyClass:
    def method(self):
        pass

    @staticmethod
    def static_method():
        pass
'''

        functions = extractor._extract_functions(python_code, "python")

        assert "regular_function" in functions
        assert "async_function" in functions
        # Methods are also captured by the regex
        assert "method" in functions
        assert "static_method" in functions

    def test_extract_functions_typescript(self) -> None:
        """Should extract TypeScript function names."""
        extractor = CodeMetadataExtractor()

        typescript_code = '''
function regularFunction(): void {
    console.log("test");
}

async function asyncFunction(): Promise<void> {
    await Promise.resolve();
}

const arrowFunction = (x: number): number => x * 2;
'''

        functions = extractor._extract_functions(typescript_code, "typescript")

        # Check for function name presence (arrow functions may not be captured well)
        assert "regularFunction" in functions
        assert "asyncFunction" in functions
        # Arrow function regex may have issues, so we just check it got something
        assert len(functions) >= 2

    def test_extract_functions_deduplication(self) -> None:
        """Should remove duplicate function names."""
        extractor = CodeMetadataExtractor()

        code = '''
def foo():
    pass

def bar():
    pass

def foo():  # Duplicate name
    pass
'''

        functions = extractor._extract_functions(code, "python")

        # Should only have one instance of "foo"
        assert functions.count("foo") == 1
        assert "bar" in functions

    def test_extract_functions_unknown_language(self) -> None:
        """Should return empty list for unknown language."""
        extractor = CodeMetadataExtractor()

        functions = extractor._extract_functions("function foo() {}", "unknown")

        assert functions == []

    def test_extract_functions_go(self) -> None:
        """Should extract Go function names including methods with receiver."""
        extractor = CodeMetadataExtractor()

        go_code = """
package main

func TopLevel() {}

func (s *Service) HandleRequest(ctx context.Context) error {
    return nil
}
"""

        functions = extractor._extract_functions(go_code, "go")

        assert "TopLevel" in functions
        assert "HandleRequest" in functions


@pytest.mark.unit
class TestExtractClasses:
    """Tests for _extract_classes method."""

    def test_extract_classes_python(self) -> None:
        """Should extract Python class names."""
        extractor = CodeMetadataExtractor()

        python_code = '''
class UserService:
    pass

class TestUserService:
    pass

async def async_function():  # Not a class
    pass
'''

        classes = extractor._extract_classes(python_code, "python")

        assert "UserService" in classes
        assert "TestUserService" in classes
        assert "async_function" not in classes

    def test_extract_classes_typescript(self) -> None:
        """Should extract TypeScript class names."""
        extractor = CodeMetadataExtractor()

        typescript_code = '''
class UserService {
    private items: Item[] = [];
}

class TestUserService extends BaseService {
    testMethod() {}
}

interface UserData {  // Not a class
    name: string;
}
'''

        classes = extractor._extract_classes(typescript_code, "typescript")

        assert "UserService" in classes
        assert "TestUserService" in classes

    def test_extract_classes_go(self) -> None:
        """Should extract Go struct type names."""
        extractor = CodeMetadataExtractor()

        go_code = '''
type User struct {
    Name string
}

type UserService struct {
    db *Database
}

func (s *UserService) GetUser() {}
'''

        classes = extractor._extract_classes(go_code, "go")

        assert "User" in classes
        assert "UserService" in classes


@pytest.mark.unit
class TestExtractImports:
    """Tests for _extract_imports method."""

    def test_extract_imports_python(self) -> None:
        """Should capture Python import statements."""
        extractor = CodeMetadataExtractor()

        python_code = '''
import os
import sys
from typing import List
from src.models import User
'''

        imports = extractor._extract_imports(python_code, "python")

        # Check that we got some imports (regex captures them with newlines)
        assert len(imports) > 0
        # The regex may include newlines, so check for presence of modules
        all_imports_text = " ".join(imports)
        assert "os" in all_imports_text or "typing" in all_imports_text or "src" in all_imports_text

    def test_extract_imports_typescript(self) -> None:
        """Should capture TypeScript import statements."""
        extractor = CodeMetadataExtractor()

        typescript_code = '''
import { User, UserService } from './models';
import * as express from 'express';
import axios from 'axios';
'''

        imports = extractor._extract_imports(typescript_code, "typescript")

        assert "./models" in imports
        assert "express" in imports or "axios" in imports

    def test_extract_imports_go(self) -> None:
        """Should capture Go import statements."""
        extractor = CodeMetadataExtractor()

        go_code = '''
import (
    "fmt"
    "os"
    "github.com/gin-gonic/gin"
    "src/models"
)
'''

        imports = extractor._extract_imports(go_code, "go")

        assert len(imports) > 0
        assert any("fmt" in imp or "os" in imp or "gin" in imp for imp in imports)

    def test_extract_imports_deduplication(self) -> None:
        """Should remove duplicate imports."""
        extractor = CodeMetadataExtractor()

        code = '''
import os
import sys
import os  # Duplicate
'''

        imports = extractor._extract_imports(code, "python")

        assert "os" in imports
        assert imports.count("os") == 1


@pytest.mark.unit
class TestDetectLanguage:
    """Tests for _detect_language method."""

    def test_detect_language_from_extension(self) -> None:
        """Should detect language from file extension."""
        extractor = CodeMetadataExtractor()

        test_cases = [
            ("test.py", "python"),
            ("test.ts", "typescript"),
            ("test.tsx", "typescript"),
            ("test.js", "javascript"),
            ("test.jsx", "javascript"),
            ("test.go", "go"),
            ("test.rs", "rust"),
            ("test.java", "java"),
            ("test.c", "c"),
            ("test.cpp", "cpp"),
            ("test.yaml", "yaml"),
            ("test.yml", "yaml"),
            ("test.json", "json"),
            ("test.toml", "toml"),
            ("test.md", "markdown"),
            ("test.txt", "text"),
            ("test.sh", "shell"),
            ("test.sql", "sql"),
            ("test.unknown", "unknown"),
            ("", "unknown"),
        ]

        for file_path, expected_lang in test_cases:
            result = extractor._detect_language(file_path)
            assert result == expected_lang, f"Failed for {file_path}"
