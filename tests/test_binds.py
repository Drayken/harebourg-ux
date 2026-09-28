import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import binds
import profiles
from binds import MOD_ALT, MOD_CONTROL, MOD_SHIFT, Bind

VK_INSERT = 0x2D
VK_A = 0x41
VK_F5 = 0x74


class LabelTests(unittest.TestCase):
    def test_mouse_and_keyboard_labels(self) -> None:
        self.assertEqual(binds.label(Bind.mouse(4)), "Souris 4")
        self.assertEqual(binds.label(Bind.keyboard(VK_INSERT, MOD_SHIFT)), "Maj+Inser")
        self.assertEqual(binds.label(Bind.keyboard(VK_F5, MOD_ALT | MOD_CONTROL | MOD_SHIFT)), "Ctrl+Maj+Alt+F5")

    def test_unnamed_key_uses_layout_character(self) -> None:
        self.assertEqual(binds.label(Bind.keyboard(0xDE, MOD_CONTROL), lambda vk: "²"), "Ctrl+²")
        self.assertEqual(binds.label(Bind.keyboard(0xDE, MOD_CONTROL)), "Ctrl+Touche 222")


class ProblemTests(unittest.TestCase):
    def test_accepted_binds(self) -> None:
        for bind in (
            Bind.mouse(3),
            Bind.mouse(5),
            Bind.keyboard(VK_F5),
            Bind.keyboard(VK_A),
            Bind.keyboard(0x31),
            Bind.keyboard(VK_A, MOD_CONTROL),
        ):
            self.assertIsNone(binds.problem(bind, {}), bind)

    def test_refused_binds(self) -> None:
        self.assertIsNotNone(binds.problem(Bind.mouse(1), {}))
        self.assertIsNotNone(binds.problem(Bind.keyboard(binds.VK_ESCAPE, MOD_SHIFT), {}))
        self.assertIsNotNone(binds.problem(Bind.keyboard(0x10, MOD_SHIFT), {}))

    def test_taken_bind_names_its_owner(self) -> None:
        taken = {Bind.keyboard(0x2E, MOD_SHIFT): "Maj+Suppr"}
        self.assertEqual(binds.problem(Bind.keyboard(0x2E, MOD_SHIFT), taken), "Déjà utilisée : Maj+Suppr.")


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / "nested" / "binds.json"

    def tearDown(self) -> None:
        self._dir.cleanup()

    def test_missing_file_gives_defaults(self) -> None:
        self.assertEqual(profiles.find_binds(self.path), dict(binds.DEFAULTS))

    def test_round_trip(self) -> None:
        saved = {binds.MARK_SELF: Bind.keyboard(VK_INSERT, MOD_SHIFT), binds.PIN: Bind.mouse(3)}
        profiles.save_binds(saved, self.path)
        self.assertEqual(profiles.find_binds(self.path), saved)

    def test_invalid_entry_falls_back_per_action(self) -> None:
        data = {binds.MARK_SELF: {"key": binds.VK_ESCAPE, "mods": 0}, binds.PIN: {"button": 3}}
        self.assertEqual(binds.from_json(data), {binds.MARK_SELF: Bind.mouse(4), binds.PIN: Bind.mouse(3)})

    def test_clashing_binds_fall_back_to_defaults(self) -> None:
        data = {binds.MARK_SELF: {"button": 3}, binds.PIN: {"button": 3}}
        self.assertEqual(binds.from_json(data), dict(binds.DEFAULTS))


if __name__ == "__main__":
    unittest.main()
