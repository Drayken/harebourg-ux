import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import profiles
from grid import Projection


class ProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / "nested" / "profiles.json"

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_missing_file_has_no_profile(self) -> None:
        self.assertIsNone(profiles.find("comte", 1920, 1080, self.path))
        self.assertIsNone(profiles.cell_size_hint(1920, 1080, self.path))

    def test_save_is_per_map_and_client_size(self) -> None:
        projection = Projection(812.5, 140.25, 71.5, 35.75)
        profiles.save("comte", 1920, 1080, projection, self.path)
        self.assertEqual(profiles.find("comte", 1920, 1080, self.path), projection)
        self.assertIsNone(profiles.find("comte", 1920, 1050, self.path))
        self.assertIsNone(profiles.find("klime", 1920, 1080, self.path))
        self.assertEqual(profiles.cell_size_hint(1920, 1080, self.path), (71.5, 35.75))
        self.assertIsNone(profiles.cell_size_hint(2560, 1440, self.path))

    def test_second_save_keeps_other_profiles(self) -> None:
        profiles.save("comte", 1920, 1080, Projection(1, 2, 60, 30), self.path)
        profiles.save("comte", 2560, 1440, Projection(3, 4, 80, 40), self.path)
        self.assertEqual(profiles.find("comte", 1920, 1080, self.path), Projection(1, 2, 60, 30))

    def test_corrupt_file_is_ignored(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(profiles.find("comte", 1920, 1080, self.path))
        profiles.save("comte", 1920, 1080, Projection(1, 2, 60, 30), self.path)
        self.assertIsNotNone(profiles.find("comte", 1920, 1080, self.path))


class ChatRegionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / "nested" / "chat.json"

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_region_is_per_client_size(self) -> None:
        self.assertIsNone(profiles.find_chat(1920, 1080, self.path))
        profiles.save_chat(1920, 1080, (10, 700, 500, 300), self.path)
        self.assertEqual(profiles.find_chat(1920, 1080, self.path), (10, 700, 500, 300))
        self.assertIsNone(profiles.find_chat(1280, 720, self.path))

    def test_region_outside_client_is_refused(self) -> None:
        profiles.save_chat(1920, 1080, (10, 900, 500, 300), self.path)
        self.assertIsNone(profiles.find_chat(1920, 1080, self.path))


if __name__ == "__main__":
    unittest.main()
