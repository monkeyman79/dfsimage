"""Text and numeric conversion functions."""

from .misc import bchr

BBC_POUND = "`"
UNICODE_POUND = bchr(0xa3).decode("iso8859-1")


def bbc_to_unicode(string: str) -> str:
    """Replace BBC pound code ("`") with unicode pound."""
    return string.replace(BBC_POUND, UNICODE_POUND)


def unicode_to_bbc(string: str) -> str:
    """Replace unicode pound with BBC pound code ("`")."""
    return string.replace(UNICODE_POUND, BBC_POUND)


def from_bcd(val: int) -> int:
    """Convert BCD encoded number to decimal.

    Args:
        val: BCD encoded number.
    Returns:
        Decimal value.
    """
    return val % 16 + (val >> 4) * 10


def to_bcd(val: int) -> int:
    """Convert decimal value to BCD encoded.

    Args:
        val: Decimal value.
    Returns:
        BCD encoded number.
    """
    return val % 10 + ((val // 10) << 4)


UNDERSCORE = ord('_')


def name_translate_safe(code):
    """Safe filename translation generator

    Translate everything that is not digit or letter to UNDERSCORE.
    """
    if (ord('0') <= code <= ord('9')
            or ord('@') <= code <= ord('Z')
            or ord('a') <= code <= ord('z')):
        return code
    return UNDERSCORE


def name_translate_standard(code):
    """Standard filename translation generator

    Translate characters that are illegal on Windows to UNDERSCORE.
    To is more than enough for Linux with standard filesystem,
    because any filename that is legal on Windows is also legal on
    Linux.
    """
    if code < 32 or code >= 127:
        return UNDERSCORE
    if code in b'"*/\\:<>?|':
        return UNDERSCORE
    return code


NAME_SAFE_TRANS = bytes(name_translate_safe(x) for x in range(0, 256))

NAME_STD_TRANS = bytes(name_translate_standard(x) for x in range(0, 256))
