"""Unit tests for MessageSplitter utility."""

import pytest

from src.utils.message_splitter import MessageSplitter, default_splitter


class TestMessageSplitter:
    """Tests for MessageSplitter class."""

    def test_init_default_max_length(self) -> None:
        """Should use Discord's 2000 character limit by default."""
        splitter = MessageSplitter()
        assert splitter.max_length == 2000

    def test_init_custom_max_length(self) -> None:
        """Should accept custom max_length."""
        splitter = MessageSplitter(max_length=100)
        assert splitter.max_length == 100

    def test_init_invalid_max_length(self) -> None:
        """Should raise ValueError for non-positive max_length."""
        with pytest.raises(ValueError, match="must be positive"):
            MessageSplitter(max_length=0)

        with pytest.raises(ValueError, match="must be positive"):
            MessageSplitter(max_length=-10)

    def test_split_empty_message(self) -> None:
        """Should return empty list for empty message."""
        splitter = MessageSplitter(max_length=100)
        assert splitter.split("") == []

    def test_split_short_message(self) -> None:
        """Should return single chunk for message under limit."""
        splitter = MessageSplitter(max_length=100)
        message = "Hello, world!"
        result = splitter.split(message)
        assert result == [message]

    def test_split_exact_limit(self) -> None:
        """Should return single chunk when message is exactly max_length."""
        splitter = MessageSplitter(max_length=10)
        message = "0123456789"  # Exactly 10 chars
        result = splitter.split(message)
        assert result == [message]
        assert len(result) == 1

    def test_split_long_message_hard_split(self) -> None:
        """Should hard split message without paragraph boundaries."""
        splitter = MessageSplitter(max_length=10)
        message = "0123456789ABCDEFGHIJ"  # 20 chars
        result = splitter.split(message)
        assert len(result) == 2
        assert result[0] == "0123456789"
        assert result[1] == "ABCDEFGHIJ"

    def test_split_with_paragraphs(self) -> None:
        """Should prefer splitting on paragraph boundaries."""
        splitter = MessageSplitter(max_length=20)
        message = "First paragraph\n\nSecond paragraph\n\nThird"
        result = splitter.split(message)
        # Should split into paragraphs, not mid-word
        for chunk in result:
            assert len(chunk) <= 20

    def test_split_preserves_content(self) -> None:
        """Splitting and joining should preserve original content."""
        splitter = MessageSplitter(max_length=50)
        message = "A" * 100
        result = splitter.split(message)
        reconstructed = "".join(result)
        assert reconstructed == message

    def test_estimate_chunks_empty(self) -> None:
        """Should estimate 0 chunks for empty message."""
        splitter = MessageSplitter()
        assert splitter.estimate_chunks("") == 0

    def test_estimate_chunks_short(self) -> None:
        """Should estimate 1 chunk for short message."""
        splitter = MessageSplitter(max_length=100)
        assert splitter.estimate_chunks("Hello") == 1

    def test_estimate_chunks_long(self) -> None:
        """Should estimate correct number of chunks."""
        splitter = MessageSplitter(max_length=10)
        message = "0123456789" * 5  # 50 chars
        estimate = splitter.estimate_chunks(message)
        assert estimate == 5

    def test_default_splitter_instance(self) -> None:
        """Should provide a default splitter with Discord's limit."""
        assert default_splitter.max_length == 2000


class TestMessageSplitterEdgeCases:
    """Edge case tests for MessageSplitter."""

    def test_single_char_over_limit(self) -> None:
        """Should handle message that's 1 char over limit."""
        splitter = MessageSplitter(max_length=10)
        message = "0123456789A"  # 11 chars
        result = splitter.split(message)
        assert len(result) == 2
        assert len(result[0]) == 10
        assert len(result[1]) == 1

    def test_very_long_paragraph(self) -> None:
        """Should hard split a very long paragraph."""
        splitter = MessageSplitter(max_length=10)
        message = "A" * 100  # Single long paragraph
        result = splitter.split(message)
        assert len(result) == 10

    def test_multiple_short_paragraphs(self) -> None:
        """Should combine short paragraphs into single chunk."""
        splitter = MessageSplitter(max_length=50)
        message = "Para 1\n\nPara 2\n\nPara 3"  # All fit in 50 chars
        result = splitter.split(message)
        assert len(result) == 1

    def test_whitespace_only_message(self) -> None:
        """Should handle whitespace-only messages."""
        splitter = MessageSplitter(max_length=10)
        message = "   \n\n   "
        result = splitter.split(message)
        assert len(result) == 1
        assert result[0] == message
