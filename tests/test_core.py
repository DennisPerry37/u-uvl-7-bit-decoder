import unittest

from u_uvl_7_bit_decoder import uu_encode, uu_decode, UUDecodeError


class TestEncodeDecodeRoundTrip(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(uu_decode(uu_encode(b"")), b"")

    def test_one_byte(self):
        self.assertEqual(uu_decode(uu_encode(b"A")), b"A")

    def test_two_bytes(self):
        self.assertEqual(uu_decode(uu_encode(b"AB")), b"AB")

    def test_three_bytes(self):
        self.assertEqual(uu_decode(uu_encode(b"ABC")), b"ABC")

    def test_45_bytes_one_line(self):
        data = bytes(range(45))
        self.assertEqual(uu_decode(uu_encode(data)), data)

    def test_46_bytes_two_lines(self):
        data = bytes(range(46))
        self.assertEqual(uu_decode(uu_encode(data)), data)

    def test_90_bytes_two_lines(self):
        data = bytes(range(90))
        self.assertEqual(uu_decode(uu_encode(data)), data)

    def test_all_256_byte_values(self):
        data = bytes(range(256))
        self.assertEqual(uu_decode(uu_encode(data)), data)

    def test_large_input(self):
        data = bytes(i % 251 for i in range(10000))
        self.assertEqual(uu_decode(uu_encode(data)), data)


class TestEncodedShape(unittest.TestCase):
    def test_begin_end_present(self):
        text = uu_encode(b"hello")
        self.assertTrue(text.startswith("begin 644 data.bin\n"))
        self.assertTrue(text.endswith("\nend"))

    def test_backtick_terminator_present(self):
        text = uu_encode(b"")
        self.assertEqual(text.split("\n"), ["begin 644 data.bin", "`", "end"])


class TestDecodeWithoutFraming(unittest.TestCase):
    def test_bare_payload_decodes(self):
        encoded = uu_encode(b"cat")
        # Extract just the payload line(s), between begin/end.
        payload = encoded.split("\n")[1:-2]  # drop begin, backtick, end
        self.assertEqual(uu_decode("\n".join(payload)), b"cat")


class TestErrorHandling(unittest.TestCase):
    def test_decode_non_ascii_raises(self):
        with self.assertRaises(UUDecodeError):
            uu_decode("begin 644 data.bin\n\u00ff line\nend\n")

    def test_decode_end_without_begin_raises(self):
        with self.assertRaises(UUDecodeError):
            uu_decode("end")

    def test_decode_bad_length_byte_raises(self):
        with self.assertRaises(UUDecodeError):
            uu_decode("begin 644 data.bin\n@payload\nend")

    def test_encode_rejects_str(self):
        with self.assertRaises(TypeError):
            uu_encode("not bytes")  # type: ignore[arg-type]

    def test_decode_rejects_bytes(self):
        with self.assertRaises(TypeError):
            uu_decode(b"not str")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
