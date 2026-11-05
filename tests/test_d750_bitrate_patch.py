import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import d750_bitrate_patch as patch  # noqa: E402


class D750BitratePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = ROOT / "D750_0115.dec.modules" / "b1010_115a.bin"
        if not fixture.is_file():
            raise unittest.SkipTest(
                "stock module fixture not present: provide "
                "D750_0115.dec.modules/b1010_115a.bin (see README §5.2 / §5.9)"
            )
        cls.module = fixture.read_bytes()

    def test_stock_table_matches_expected(self):
        patch.check_stock(self.module)
        self.assertEqual(patch.read_hq(self.module), list(patch.STOCK_HQ))

    def test_patch_changes_only_hq_fields(self):
        out, changes = patch.patch_module(self.module)
        self.assertEqual(len(out), len(self.module))
        self.assertEqual(len(changes), 5)
        patch.verify_patch(self.module, out, changes)
        self.assertEqual(patch.read_hq(out), [patch.TARGET] * 5)

    def test_nq_and_720p_rows_are_untouched(self):
        out, _ = patch.patch_module(self.module)
        for idx in (1, 3, 5, 7):
            off = patch.TABLE_ENTRY1 + idx * patch.ENTRY_STRIDE
            self.assertEqual(out[off:off + 8], self.module[off:off + 8])
        # Entry 10 starts the 720p group; the whole rest of the table must match.
        tail = patch.TABLE_ENTRY1 + 9 * patch.ENTRY_STRIDE
        self.assertEqual(out[tail:tail + 13 * patch.ENTRY_STRIDE],
                         self.module[tail:tail + 13 * patch.ENTRY_STRIDE])

    def test_wrong_stock_is_rejected(self):
        bad = bytearray(self.module)
        bad[patch.TABLE_ENTRY1:patch.TABLE_ENTRY1 + 4] = struct.pack("<I", 1)
        with self.assertRaises(ValueError):
            patch.check_stock(bytes(bad))


if __name__ == "__main__":
    unittest.main()
