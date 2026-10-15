# u-uvl-7-bit-decoder

Converts binary data to and from uuencoded text, the 7-bit-safe format once standard for Usenet posts and email attachments.

```python
from u_uvl_7_bit_decoder import uu_encode, uu_decode

encoded = uu_encode(b"hello, world")
print(encoded)
# begin 644 data.bin
# ...\n`\nend

decoded = uu_decode(encoded)
assert decoded == b"hello, world"
```

## Why this exists

The standard library's `binascii` module handles the low-level byte-to-character mapping for uuencoding, but it does not produce or parse the `begin`/`end` framing that makes a blob self-describing on the wire. This library wraps that primitive with a minimal, deterministic framing layer: every `uu_encode` call emits `begin 644 data.bin`, one or more payload lines, a backtick terminator, and `end`. Every `uu_decode` call accepts that framed form, and also accepts a bare sequence of payload lines for when the framing has already been stripped.

The trade-off is that the mode (`644`) and filename (`data.bin`) are fixed. If you need to control either, reach for `binascii` directly and build your own framing. This library is deliberately small so that its behaviour is easy to audit.

## The awkward edge

`uu_decode` is lenient about a bare trailing backtick line (it ignores it) but strict about `end` appearing without a matching `begin` — that raises `UUDecodeError`. If your input is a bare payload that happens to contain a line beginning with `end`, the decoder will misinterpret it as framing; prefix such input with a `begin` line or strip the offending line before decoding.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

