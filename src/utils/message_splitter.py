"""
Message splitting utility for Discord's character limits.

Discord has a 2000 character limit per message. This utility
handles splitting long responses into multiple messages.
"""

from collections.abc import Iterator


class MessageSplitter:
    """
    Splits messages to fit within Discord's character limits.

    Handles edge cases like splitting mid-word and ensures
    messages don't exceed the maximum length.
    """

    def __init__(self, max_length: int = 2000) -> None:
        """
        Initialize the splitter.

        Args:
            max_length: Maximum characters per message (default: Discord's 2000)
        """
        if max_length <= 0:
            raise ValueError("max_length must be positive")
        self.max_length = max_length

    def split(self, message: str) -> list[str]:
        """
        Split a message into chunks that fit within the limit.

        Args:
            message: The message to split

        Returns:
            List of message chunks, each <= max_length
        """
        if not message:
            return []

        if len(message) <= self.max_length:
            return [message]

        return list(self._chunk_message(message))

    def _chunk_message(self, message: str) -> Iterator[str]:
        """
        Generator that yields message chunks.

        Tries to split on paragraph boundaries first, then
        falls back to hard splitting.

        Args:
            message: The message to chunk

        Yields:
            Message chunks
        """
        # Try paragraph-aware splitting first
        paragraphs = message.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            # Add paragraph separator if not first
            test_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para

            if len(test_chunk) <= self.max_length:
                current_chunk = test_chunk
            else:
                # Current chunk is full, yield it
                if current_chunk:
                    yield current_chunk

                # Check if single paragraph exceeds limit
                if len(para) > self.max_length:
                    # Hard split the paragraph
                    yield from self._hard_split(para)
                    current_chunk = ""
                else:
                    current_chunk = para

        # Yield remaining chunk
        if current_chunk:
            yield current_chunk

    def _hard_split(self, text: str) -> Iterator[str]:
        """
        Hard split text when no natural boundaries exist.

        Args:
            text: Text to split

        Yields:
            Text chunks of exactly max_length or less
        """
        for i in range(0, len(text), self.max_length):
            yield text[i : i + self.max_length]

    def estimate_chunks(self, message: str) -> int:
        """
        Estimate the number of chunks a message will produce.

        Args:
            message: The message to analyze

        Returns:
            Estimated number of chunks
        """
        if not message:
            return 0
        return len(self.split(message))


# Default instance for common use
default_splitter = MessageSplitter()


__all__ = ["MessageSplitter", "default_splitter"]
