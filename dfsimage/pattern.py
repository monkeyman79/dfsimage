"""This module contains parsed DFS file name pattern and pattern list."""

from re import Pattern
from typing import Union, Optional, List


class ParsedPattern:
    """Represents parsed DFS name pattern."""

    def __init__(self, filename: Pattern, dirname: Optional[Pattern],
                 head: Optional[int], pattern: str):
        """Construct ParsedPattern object.

        Args:
            filename: Compiled regular expression for filename
            dirname: Compled regular expression for directory name
            head: Head number - 0 or 1
            patter: Original pattern string
        """
        self.filename = filename
        self.dirname = dirname
        self.head = head
        self.pattern = pattern
        self.match_count = 0

    def ensure_matched(self):
        """Raise exception if the pattern didn't match any file."""
        if self.match_count == 0:
            raise FileNotFoundError("file '%s' not found" % self.pattern)


class PatternList:
    """List of ParsedPattern objects."""

    def __init__(self, patterns: List[ParsedPattern]):
        """Construct PatternList by wrapping list of ParsedPattern objects."""
        self.patterns = patterns

    def ensure_matched(self):
        """Raise exception if any of patterns didn't match any file."""
        for pattern in self.patterns:
            pattern.ensure_matched()


PatternUnion = Union[str, List[str], ParsedPattern, PatternList]
