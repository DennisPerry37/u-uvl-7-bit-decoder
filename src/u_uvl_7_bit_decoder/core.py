"""Core uuencode/uudecode implementation.

This module implements uuencode/uudecode as described in POSIX.
The "7-bit" aspect refers to the fact that each encoded character is
an ASCII character (code points 32-95), making the format safe for
transmission over 7-bit-clean channels such as legacy email and Usenet.

Design decisions:
  * Single-function API: ``uu_encode(data) -> str`` and ``uu_decode(text) -> bytes``.
    We intentionally accept only complete, self-contained blobs and produce
    complete, self-contained blobs. Streaming is out of scope.
  * We always emit ``begin`` and ``end`` lines with the mode ``644`` and the
    filename ``data.bin``. Real uuencode lets you pick both; this library
    keeps the API minimal and deterministic. If you need a different mode
    or filename, use the standard library's ``binascii`` + your own framing.
  * ``uu_decode`` tolerates the ``begin``/``end`` markers that ``uu_encode``
    emits, and also tolerates a bare sequence of encoded lines with no
    framing at all. It raises ``UUDecodeError`` on genuinely malformed input.
"""

from __future__ import annotations

import binascii


class UUDecodeError(ValueError):
    """Raised when input to ``uu_decode`` is not valid uuencoded text."""


def _encode_line(chunk: bytes) -> str:
    """Encode a chunk of up to 45 bytes into a single uuencoded line.

    The line begins with a length byte (number of source bytes encoded in
    this line, mapped into the printable ASCII range starting at space)
    followed by the 6-bit-grouped data, also offset into printable ASCII.
    """
    n = len(chunk)
    # Pad the chunk to a multiple of 3 so that binascii can encode it
    # as a complete set of 4-character groups.
    pad = (-n) % 3
    padded = chunk + b"\x00" * pad
    encoded = binascii.b2a_uu(padded).rstrip(b"\n")
    # binascii.b2a_uu prepends its own length character, which encodes
    # len(padded) (the padded length). We replace it with the real length
    # so that decoders know how many bytes are meaningful.
    return bytes([32 + n]).decode("ascii") + encoded[1:].decode("ascii")


def uu_encode(data: bytes) -> str:
    """Encode ``data`` as uuencoded text with begin/end framing.

    Returns a string with embedded newlines, ready to be transmitted over
    any 7-bit-clean channel and decoded by any standard uudecoder — including
    this module's :func:`uu_decode`.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("uu_encode expects bytes, got %r" % type(data).__name__)
    data = bytes(data)
    lines = ["begin 644 data.bin"]
    for i in range(0, len(data), 45):
        lines.append(_encode_line(data[i:i + 45]))
    lines.append("`")
    lines.append("end")
    return "\n".join(lines)


def uu_decode(text: str) -> bytes:
    """Decode uuencoded text produced by :func:`uu_encode`.

    Accepts input with ``begin``/``end`` framing or a bare sequence of
    encoded lines. ``begin``/``end`` lines and a trailing backtick-only line
    (the conventional empty-payload terminator) are ignored. Blank lines
    are skipped. Any other non-ASCII or out-of-range byte triggers a
    :class:`UUDecodeError`.
    """
    if not isinstance(text, str):
        raise TypeError("uu_decode expects str, got %r" % type(text).__name__)

    encoded_lines = []
    in_payload = False
    saw_begin = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped == "":
            continue
        if stripped.startswith("begin "):
            saw_begin = True
            in_payload = True
            continue
        if stripped == "end":
            if not saw_begin:
                raise UUDecodeError("'end' without matching 'begin'")
            in_payload = False
            break
        if stripped == "`":
            if not in_payload and not saw_begin:
                raise UUDecodeError("'`' terminator outside of uuencoded block")
            continue
        if saw_begin and in_payload:
            encoded_lines.append(raw_line.rstrip("\r\n"))
            continue
        # No begin marker seen yet — treat as bare payload.
        encoded_lines.append(raw_line.rstrip("\r\n"))

    out = bytearray()
    for idx, line in enumerate(encoded_lines, 1):
        try:
            line_bytes = line.encode("ascii")
        except UnicodeEncodeError:
            raise UUDecodeError(
                "line %d contains non-ASCII characters" % idx
            ) from None
        if not line_bytes:
            continue
        length_byte = line_bytes[0]
        if length_byte < 32 or length_byte > 32 + 45:
            raise UUDecodeError(
                "line %d: invalid length byte %d" % (idx, length_byte)
            )
        declared_len = length_byte - 32
        # Reconstruct a line that binascii can decode: it must start with
        # the length byte that binascii expects, which is the declared
        # length rounded UP to a multiple of 3.
        padded_len = declared_len + (-declared_len) % 3
        if padded_len == 0:
            continue
        expected_groups = (padded_len + 2) // 3
        expected_chars = expected_groups * 4
        body = line_bytes[1:]
        if len(body) < expected_chars:
            # Pad with spaces so binascii sees a complete group set.
            body = body + b" " * (expected_chars - len(body))
        reconstructed = bytes([padded_len + 32]) + body[:expected_chars]
        try:
            decoded = binascii.a2b_uu(reconstructed)
        except (binascii.Error, ValueError) as exc:
            raise UUDecodeError("line %d: %s" % (idx, exc)) from None
        out.extend(decoded[:declared_len])
    return bytes(out)
