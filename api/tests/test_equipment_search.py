import unittest

from partgraph.equipment.service import _search_without_whitespace


class EquipmentSearchTests(unittest.TestCase):
    def test_spacing_does_not_change_equipment_search_form(self) -> None:
        self.assertEqual(_search_without_whitespace("10 mm"), "10mm")
        self.assertEqual(_search_without_whitespace("10mm"), "10mm")
        self.assertEqual(_search_without_whitespace("  3/8   in  drive "), "3/8indrive")


if __name__ == "__main__":
    unittest.main()
