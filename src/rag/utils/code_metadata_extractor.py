"""Metadata extraction utilities for code files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)


# Function patterns by language
PYTHON_FUNCTION_PATTERN = r"(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
TYPESCRIPT_FUNCTION_PATTERN = r"(?:async\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
TYPESCRIPT_ARROW_FUNCTION = r"(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:\([^)]*\)\s*?=>|[a-zA-Z_][a-zA-Z0-9_]*\s*?=>)"
GO_FUNCTION_PATTERN = r"func\s+(?:\([^)]*\)\s*)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\("

# Class patterns by language
PYTHON_CLASS_PATTERN = r"class\s+([A-Z][a-zA-Z0-9_]*)\s*(?:\(|:)"
TYPESCRIPT_CLASS_PATTERN = r"class\s+([A-Z][a-zA-Z0-9_]*)\s*(?:\{|extends)"
GO_CLASS_PATTERN = r"type\s+([A-Z][a-zA-Z0-9_]*)\s+struct"

# Import patterns by language
PYTHON_IMPORT_PATTERN = (
    r"^(?:from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import|import\s+([a-zA-Z_][a-zA-Z0-9_., \t]*))"
)
TYPESCRIPT_IMPORT_PATTERN = r"^import\s+(?:\{[^}]*\}|\*\s+as\s+[a-zA-Z_][a-zA-Z0-9_]*|[a-zA-Z_][a-zA-Z0-9_]*)\s+from\s+['\"]([^'\"]+)['\"]"
GO_IMPORT_PATTERN = r"^(?:import|\s+)\s*[\"']([a-zA-Z_][a-zA-Z0-9_/]*)[\"']"


class CodeMetadataExtractor:
    """
    Extract metadata from code files.

    Identifies functions, classes, imports, layer classification,
    module name, language, and test detection.
    """

    def __init__(self) -> None:
        """Initialize the code metadata extractor."""
        # Pre-compile regex patterns for Python
        self._python_function_re = re.compile(PYTHON_FUNCTION_PATTERN)
        self._python_class_re = re.compile(PYTHON_CLASS_PATTERN)
        self._python_import_re = re.compile(PYTHON_IMPORT_PATTERN, re.MULTILINE)

        # Pre-compile regex patterns for TypeScript
        self._ts_function_re = re.compile(TYPESCRIPT_FUNCTION_PATTERN)
        self._ts_arrow_function_re = re.compile(TYPESCRIPT_ARROW_FUNCTION)
        self._ts_class_re = re.compile(TYPESCRIPT_CLASS_PATTERN)
        self._ts_import_re = re.compile(TYPESCRIPT_IMPORT_PATTERN, re.MULTILINE)

        # Pre-compile regex patterns for Go
        self._go_function_re = re.compile(GO_FUNCTION_PATTERN)
        self._go_class_re = re.compile(GO_CLASS_PATTERN)
        self._go_import_re = re.compile(GO_IMPORT_PATTERN, re.MULTILINE)

        # Layer classification patterns
        self._layer_patterns = {
            "core": r"src[/\\]core[/\\]",
            "storage": r"src[/\\]storage[/\\]",
            "rag": r"src[/\\]rag[/\\]",
            "middleware": r"src[/\\]middleware[/\\]",
            "utils": r"src[/\\]utils[/\\]",
            "models": r"src[/\\]models[/\\]",
            "config": r"src[/\\]config[/\\]",
            "services": r"src[/\\]services[/\\]",
            "tools": r"src[/\\]tools[/\\]",
            "tests": r"tests?[/\\]",
            "scripts": r"scripts?[/\\]",
            "docs": r"docs?[/\\]",
            "migrations": r"migrations?[/\\]",
        }

        log.debug("rag_code_metadata_extractor_initialized")

    def extract_code_metadata(self, text: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        Extract metadata from code text.

        Args:
            text: The code text to extract metadata from
            context: Additional context containing at least:
                - file_path: str (path to the file)

        Returns:
            Dictionary with extracted code metadata
        """
        file_path = context.get("file_path", "")

        # Detect language from file extension
        language = self._detect_language(file_path)

        # Extract code structure
        functions = self._extract_functions(text, language)
        classes = self._extract_classes(text, language)
        imports = self._extract_imports(text, language)

        # Classify layer and module
        layer = self._classify_layer(file_path)
        module = self._extract_module_name(file_path)

        # Detect if it's a test file
        is_test = self._detect_is_test(file_path)

        metadata = {
            "file_path": file_path,
            "language": language,
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "layer": layer,
            "module": module,
            "is_test": is_test,
        }

        log.info(
            "rag_code_metadata_extracted",
            file_path=file_path,
            language=language,
            layer=layer,
            module=module,
            is_test=is_test,
            num_functions=len(functions),
            num_classes=len(classes),
            num_imports=len(imports),
            event_name="rag_code_metadata_extracted",
        )

        return metadata

    def _extract_functions(self, text: str, language: str) -> list[str]:
        """
        Extract function names from code text.

        Args:
            text: Code text to search
            language: Programming language identifier

        Returns:
            List of function names found
        """
        functions = []

        if language == "python":
            matches = self._python_function_re.findall(text)
            functions.extend(matches)

        elif language == "typescript":
            # Regular functions
            matches = self._ts_function_re.findall(text)
            functions.extend(matches)
            # Arrow functions
            arrow_matches = self._ts_arrow_function_re.findall(text)
            functions.extend(arrow_matches)

        elif language == "go":
            matches = self._go_function_re.findall(text)
            functions.extend(matches)

        # Remove duplicates while preserving order
        seen = set()
        unique_functions = []
        for func in functions:
            if func not in seen:
                seen.add(func)
                unique_functions.append(func)

        return unique_functions

    def _extract_classes(self, text: str, language: str) -> list[str]:
        """
        Extract class names from code text.

        Args:
            text: Code text to search
            language: Programming language identifier

        Returns:
            List of class names found
        """
        classes = []

        if language == "python":
            matches = self._python_class_re.findall(text)
            classes.extend(matches)

        elif language == "typescript":
            matches = self._ts_class_re.findall(text)
            classes.extend(matches)

        elif language == "go":
            matches = self._go_class_re.findall(text)
            classes.extend(matches)

        return classes

    def _extract_imports(self, text: str, language: str) -> list[str]:
        """
        Extract imported modules from code text.

        Args:
            text: Code text to search
            language: Programming language identifier

        Returns:
            List of imported modules
        """
        imports = []

        if language == "python":
            matches = self._python_import_re.findall(text)
            for match in matches:
                # match is tuple (from_module, import_statement) or (import_statement,)
                if isinstance(match, tuple):
                    if match[0]:  # "from X import Y"
                        imports.append(match[0])
                    elif match[1]:  # "import X"
                        # Handle multiple imports: "import os, sys"
                        modules = []
                        for raw_module in match[1].split(","):
                            cleaned = raw_module.split("#", 1)[0].strip()
                            cleaned = cleaned.split(" as ", 1)[0].strip()
                            if cleaned:
                                modules.append(cleaned)
                        imports.extend(modules)
                else:
                    imports.append(match)

        elif language == "typescript":
            matches = self._ts_import_re.findall(text)
            imports.extend(matches)

        elif language == "go":
            matches = self._go_import_re.findall(text)
            imports.extend(matches)

        # Remove duplicates while preserving order
        seen = set()
        unique_imports = []
        for imp in imports:
            if imp and imp not in seen:
                seen.add(imp)
                unique_imports.append(imp)

        return unique_imports

    def _classify_layer(self, file_path: str) -> str:
        """
        Classify the architectural layer based on file path.

        Args:
            file_path: Path to the file

        Returns:
            Layer identifier (core, storage, rag, etc.)
        """
        if not file_path:
            return "unknown"

        for layer, pattern in self._layer_patterns.items():
            if re.search(pattern, file_path):
                return layer

        return "unknown"

    def _extract_module_name(self, file_path: str) -> str:
        """
        Extract module name from file path.

        Args:
            file_path: Path to the file

        Returns:
            Module name (e.g., "agent", "discord", "repository")
        """
        if not file_path:
            return "unknown"

        path = Path(file_path)

        # Get the filename without extension
        module = path.stem

        # If it's __init__, use the parent directory name
        if module == "__init__" and path.parent.name:
            module = path.parent.name

        return module

    def _detect_language(self, file_path: str) -> str:
        """
        Detect programming language from file extension.

        Args:
            file_path: Path to the file

        Returns:
            Language identifier (python, typescript, go, yaml, etc.)
        """
        if not file_path:
            return "unknown"

        path = Path(file_path)
        suffix = path.suffix.lower()

        language_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".toml": "toml",
            ".md": "markdown",
            ".txt": "text",
            ".sh": "shell",
            ".sql": "sql",
        }

        return language_map.get(suffix, "unknown")

    def _detect_is_test(self, file_path: str) -> bool:
        """
        Detect if the file is a test file.

        Args:
            file_path: Path to the file

        Returns:
            True if the file appears to be a test file
        """
        if not file_path:
            return False

        path_lower = file_path.lower()

        # Check if file is in tests/ directory
        if re.search(r"tests?[/\\]", path_lower):
            return True

        # Check if filename contains "test"
        path = Path(file_path)
        return "test" in path.stem.lower()


__all__ = ["CodeMetadataExtractor"]
