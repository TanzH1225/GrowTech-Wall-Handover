from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comm.line_parser import BufferedLineParser


class BufferedLineParserTests(unittest.TestCase):
    def test_fragmented_line(self) -> None:
        parser = BufferedLineParser()
        self.assertEqual(parser.feed(b"STAT,1000,72"), [])
        self.assertEqual(parser.pending_bytes, b"STAT,1000,72")
        self.assertEqual(
            parser.feed(b".5,1450,6.5,0,0,0,0,0\r\n"),
            ["STAT,1000,72.5,1450,6.5,0,0,0,0,0"],
        )

    def test_combined_lines_and_blank_lines(self) -> None:
        parser = BufferedLineParser()
        self.assertEqual(
            parser.feed(b"START 1 1\nPOS 1 1\n\npartial"),
            ["START 1 1", "POS 1 1"],
        )
        self.assertEqual(parser.feed(b" end\n"), ["partial end"])

    def test_bad_utf8_is_ignored_without_losing_framing(self) -> None:
        parser = BufferedLineParser()
        self.assertEqual(parser.feed(b"POS \xff1 2\n"), ["POS 1 2"])

    def test_oversized_unterminated_record_is_rejected_and_reset(self) -> None:
        parser = BufferedLineParser(max_buffer_bytes=4)
        with self.assertRaises(ValueError):
            parser.feed(b"12345")
        self.assertEqual(parser.pending_bytes, b"")


if __name__ == "__main__":
    unittest.main()
