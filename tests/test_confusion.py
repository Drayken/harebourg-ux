import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confusion import Rotation, aim_cell, landing_cell, parse_line, rotate_offset


class ParseTests(unittest.TestCase):
    def test_chat_forms(self) -> None:
        cases = {
            "90° horaire": Rotation.CLOCKWISE,
            "270° contre horaire": Rotation.CLOCKWISE,
            "horaire 1 Pi/2": Rotation.CLOCKWISE,
            "contre horaire 3 Pi/2": Rotation.CLOCKWISE,
            "horaire 2Pi/4": Rotation.CLOCKWISE,
            "contre horaire 6 Pi/4": Rotation.CLOCKWISE,
            "180° horaire": Rotation.HALF,
            "180° contre horaire": Rotation.HALF,
            "horaire 2 Pi/2": Rotation.HALF,
            "horaire 4 Pi/4": Rotation.HALF,
            "contre horaire 2 Pi/2": Rotation.HALF,
            "contre horaire 4 Pi/4": Rotation.HALF,
            "90° contre horaire": Rotation.COUNTERCLOCKWISE,
            "270° horaire": Rotation.COUNTERCLOCKWISE,
            "contre horaire 1 Pi/2": Rotation.COUNTERCLOCKWISE,
            "horaire 3 Pi/2": Rotation.COUNTERCLOCKWISE,
            "contre horaire 2 Pi/4": Rotation.COUNTERCLOCKWISE,
            "horaire 6 Pi/4": Rotation.COUNTERCLOCKWISE,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_line(text), expected)

    def test_combat_log_prefix_and_pi_glyph(self) -> None:
        line = "[11:22] Korbax lance : Confusion contre horaire : 4 π/4 (1"
        self.assertEqual(parse_line(line), Rotation.HALF)

    def test_debuff_tooltip(self) -> None:
        self.assertEqual(
            parse_line("Confusion contre horaire : 1 Pi/2 - 1"),
            Rotation.COUNTERCLOCKWISE,
        )

    def test_misread_digit_is_rejected(self) -> None:
        # Screenshot at 16% life: "Confusion contre horaire : 3 Pi/2" after Comtoise.
        self.assertEqual(parse_line("[17:28] Zxsn : Confusion contre horaire : 3 Pi/2 (1"), Rotation.CLOCKWISE)
        for text in ("contre horaire : 8 Pi/2", "contre horaire : 5 Pi/2", "horaire : 0 Pi/2", "horaire 360°"):
            with self.subTest(text=text):
                self.assertIsNone(parse_line(text))

    def test_unrelated_line(self) -> None:
        self.assertIsNone(parse_line("Korbax lance Comtoise."))
        self.assertIsNone(parse_line("[14:03] Zxsn perd 90 PV (1 tour)"))

    def test_windows_ocr_misreads(self) -> None:
        # Seen from Windows OCR on rendered chat text.
        cases = {
            "[14:02] Zxsn : Confusion contre horaire : 4 TT/4 (1 tour)": Rotation.HALF,
            "[14:02] Zxsn : Confusion contre horaire : 4 Tt/4 (I tour)": Rotation.HALF,
            "[14:02] Zxsn : Confusion contre horaire : 4 Ti/4 (1 tour)": Rotation.HALF,
            "[14:03] Zxsn : Confusion horaire : I Pi/2 (I tour)": Rotation.CLOCKWISE,
            "[14:03] Zxsn : Confusion horaire : l TT/2": Rotation.CLOCKWISE,
            "[14:04] Zxsn : Confusion 900 contre horaire": Rotation.COUNTERCLOCKWISE,
            "[14:04] Zxsn : Confusion 1800 horaire": Rotation.HALF,
            "Confusion contre-horaire : 1 Pi/2": Rotation.COUNTERCLOCKWISE,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_line(text), expected)


class MeleeTests(unittest.TestCase):
    def test_bump_cycle(self) -> None:
        state = Rotation.CLOCKWISE
        seen = [state]
        for _ in range(4):
            state = state.bumped()
            seen.append(state)
        self.assertEqual(
            seen,
            [
                Rotation.CLOCKWISE,
                Rotation.HALF,
                Rotation.COUNTERCLOCKWISE,
                Rotation.STRAIGHT,
                Rotation.CLOCKWISE,
            ],
        )

    def test_melee_moves_the_aim_counter_clockwise(self) -> None:
        # From a fight: 180° at turn start, one melee hit. The aim went from behind the
        # caster to their right; clicking their left landed behind them.
        origin = (0, 0)
        up, left, down, right = (-1, -1), (-1, 1), (1, 1), (1, -1)
        state = Rotation.HALF
        self.assertEqual(aim_cell(origin, up, state), down)
        state = state.bumped()
        self.assertEqual(aim_cell(origin, up, state), right)
        self.assertEqual(landing_cell(origin, left, state), down)


class GridTests(unittest.TestCase):
    def test_cardinal_rotations(self) -> None:
        east = (4, 0)
        self.assertEqual(rotate_offset(*east, Rotation.STRAIGHT), (4, 0))
        self.assertEqual(rotate_offset(*east, Rotation.CLOCKWISE), (0, 4))
        self.assertEqual(rotate_offset(*east, Rotation.HALF), (-4, 0))
        self.assertEqual(rotate_offset(*east, Rotation.COUNTERCLOCKWISE), (0, -4))

    def test_landing_cell(self) -> None:
        self.assertEqual(landing_cell((10, 10), (13, 8), Rotation.CLOCKWISE), (12, 13))

    def test_horaire_turns_clockwise_on_screen(self) -> None:
        # Cheat sheet, 90° horaire: monster straight above, click the cell to the left.
        # Screen x = cell x - cell y, screen y = cell x + cell y, with y pointing down.
        def screen(cell: tuple[int, int]) -> tuple[int, int]:
            return cell[0] - cell[1], cell[0] + cell[1]

        origin = (0, 0)
        up, left, down, right = (-1, -1), (-1, 1), (1, 1), (1, -1)
        self.assertEqual([screen(cell) for cell in (up, left, down, right)], [(0, -2), (-2, 0), (0, 2), (2, 0)])
        self.assertEqual(landing_cell(origin, left, Rotation.CLOCKWISE), up)
        self.assertEqual(aim_cell(origin, up, Rotation.CLOCKWISE), left)
        self.assertEqual(aim_cell(origin, up, Rotation.COUNTERCLOCKWISE), right)

    def test_low_life_click_on_the_wrong_side_lands_behind(self) -> None:
        # 4% life, chat "Confusion contre horaire : 270 degrés". Same state as 90° horaire.
        # Cible was the up-right neighbor. The mirrored aim is the down-right neighbor,
        # and that click lands on the far side of the caster from the mob.
        self.assertEqual(parse_line("Confusion contre horaire : 270 degres"), Rotation.CLOCKWISE)
        origin = (0, 0)
        cible = (0, -1)
        self.assertEqual(aim_cell(origin, cible, Rotation.CLOCKWISE), (-1, 0))
        self.assertEqual(landing_cell(origin, (1, 0), Rotation.CLOCKWISE), (0, 1))

    def test_aim_lands_on_desired(self) -> None:
        origin = (10, 10)
        for rotation in Rotation:
            for desired in ((13, 8), (10, 4), (6, 6), (11, 10)):
                with self.subTest(rotation=rotation, desired=desired):
                    aim = aim_cell(origin, desired, rotation)
                    self.assertEqual(landing_cell(origin, aim, rotation), desired)
