import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chat import Found, Watch, entries, latest, pick, speaker
from confusion import Rotation

# From a fight: the turn-start line sits above the Comtoise cast, then one melee hit.
TURN_ONE = [
    "[16:17] Comte Harebourg lance Bon vieux temps.",
    "[16:17] Zxsn : Confusion horaire : 4 Pi/4 (1 tour)",
    "[16:17] Zxsn lance Comtoise.",
    "[16:17] Zxsn lance Mutilation.",
    "[16:17] Zxsn : -301 PV (infini)",
    "[16:17] Zxsn lance Condensation. Coup critique !",
    "[16:17] Cycloïde : -294 PV",
    "[16:17] Zxsn lance Aversion.",
    "[16:17] Cycloïde : -74 PV",
    "[16:17] Cycloïde lance Pendultimatum.",
    "[16:17] Zxsn : Confusion horaire : 1 Pi/2 (1 tour)",
    "[16:17] Zxsn lance Stase.",
]

# From the same fight: here the turn-start line sits below the Comtoise cast.
TURN_TWO = [
    "[16:50] Comte Harebourg lance Contretemps.",
    "[16:50] Zxsn : -579 PV",
    "[16:50] Zxsn lance Comtoise.",
    "[16:50] Zxsn : Confusion contre horaire : 90 degrés",
    "(1 tour)",
    "[16:50] Zxsn : -343 PV (infini)",
]


class EntryTests(unittest.TestCase):
    def test_wrapped_lines_join_on_timestamps(self) -> None:
        lines = [
            "[14:02] Zxsn : Confusion contre horaire :",
            "4 TT/4 (1 tour)",
            "[14:03] Korbax lance Comtoise.",
        ]
        self.assertEqual(
            entries(lines),
            ["[14:02] Zxsn : Confusion contre horaire : 4 TT/4 (1 tour)", "[14:03] Korbax lance Comtoise."],
        )

    def test_without_timestamps_each_line_stands_alone(self) -> None:
        self.assertEqual(entries(["a", "", "b"]), ["a", "b"])

    def test_misread_timestamps_still_start_an_entry(self) -> None:
        # Seen from Windows OCR on indented chat lines.
        lines = [
            "[17:03] Zxsn lance Comtoise.",
            "117:03] Zxsn : -521PVS.",
            "(17:03] Zxsn : Confusion horaire : 1 Pi/2",
            "+ Cl 7:03] Zxsn : -100 Dommages (1",
            "-331 PV",
        ]
        self.assertEqual(len(entries(lines)), 4)
        self.assertEqual([speaker(entry) for entry in entries(lines)], ["Zxsn"] * 4)


class LatestTests(unittest.TestCase):
    def test_turn_start_above_comtoise(self) -> None:
        self.assertEqual(latest(TURN_ONE[:3]), Found(Rotation.HALF, 1, "Zxsn"))

    def test_turn_start_below_comtoise(self) -> None:
        self.assertEqual(latest(TURN_TWO), Found(Rotation.COUNTERCLOCKWISE, 1, "Zxsn"))

    def test_melee_line_adds_to_the_turn_start(self) -> None:
        # 180° plus one melee hit is 270° horaire, even though the line prints 1 Pi/2.
        self.assertEqual(latest(TURN_ONE), Found(Rotation.COUNTERCLOCKWISE, 1, "Zxsn"))

    def test_each_melee_line_adds_again(self) -> None:
        log = [*TURN_ONE, "[16:17] Cycloïde : -80 PV", "[16:17] Zxsn : Confusion horaire : 1 Pi/2 (1 tour)"]
        self.assertEqual(latest(log).rotation, Rotation.STRAIGHT)

    def test_name_case_from_ocr_is_the_same_character(self) -> None:
        # Seen from Windows OCR: "Zxsn" and "zxsn" in the same frame.
        log = [
            "[17:02] Zxsn lance Comtoise.",
            "[17:02] zxsn : Confusion contre horaire : 6 Pi/4 (1",
            "[17:02] Zxsn lance Dissolution. Coup critique !",
            "[17:02] Cycloide : -461PV",
            "[17:02] zxsn : Confusion horaire : 1 Pi/2 (1",
            "[17:02] Zxsn : 1% Dommages finaux (3",
        ]
        self.assertEqual(latest(log[:2]).rotation, Rotation.CLOCKWISE)
        self.assertEqual(latest(log), Found(Rotation.HALF, 1, "zxsn"))

    def test_misread_turn_start_digit_waits(self) -> None:
        # From a fight at 16% life: "3 Pi/2" after Comtoise. A 3 read as 8 or 5 is no angle.
        log = [
            "[17:28] Zxsn lance Comtoise. [A]",
            "[17:28] Zxsn : Confusion contre horaire : 3 Pi/2 (1",
            "[17:28] Zxsn : -81 PV (infini)",
            "[17:28] Zxsn lance Nervosité. Coup critique ! [A]",
        ]
        self.assertEqual(latest(log), Found(Rotation.CLOCKWISE, 2, "Zxsn"))
        for misread in ("8 Pi/2", "5 Pi/2"):
            with self.subTest(misread=misread):
                self.assertIsNone(latest([log[0], log[1].replace("3 Pi/2", misread), *log[2:]]))

    def test_another_characters_comtoise_is_not_your_turn_start(self) -> None:
        log = ["[14:02] Korbax lance Comtoise.", "[14:02] Zxsn : Confusion horaire : 1 Pi/2 (1 tour)"]
        self.assertIsNone(latest(log))

    def test_melee_line_before_the_next_comtoise_is_not_the_turn_start(self) -> None:
        log = [
            "[14:02] Zxsn : Confusion horaire : 1 Pi/2 (1 tour)",
            "[14:03] Zxsn lance Comtoise.",
            "[14:03] Zxsn : Confusion horaire : 4 Pi/4 (1 tour)",
        ]
        self.assertEqual(latest(log), Found(Rotation.HALF, 0, "Zxsn"))

    def test_nothing_without_a_turn_start(self) -> None:
        self.assertIsNone(latest(["[14:03] Korbax lance Comtoise."]))
        self.assertIsNone(latest(["[14:03] Zxsn : Confusion horaire : 1 Pi/2 (1 tour)"]))

    def test_misread_turn_start_does_not_fall_back(self) -> None:
        # Seen from Windows OCR: the "90°" vanished from the line.
        log = [
            "[14:02) Zxsn : Confiasion contre horaire : 4 n/4 (I tour)",
            "[14:02) Zxsn lance Comtoise.",
            "[14:03) Korbax lance Comtoise.",
            "[14:031 Zxsn : Confision horaire (I tour)",
            "[14:031 Zxsn lance Comtoise.",
        ]
        self.assertIsNone(latest(log))

    def test_pick_prefers_the_readable_reading(self) -> None:
        blurred = ["[14:03] Zxsn lance Comtoise.", "[14:03] Zxsn : Confision horaire (I tour)"]
        sharp = ["[14:03] Zxsn lance Comtoise.", "[14:03] Zxsn : Confusion 900 horaire (1 tour)"]
        self.assertEqual(pick([blurred, sharp]), sharp)
        self.assertEqual(pick([blurred]), blurred)


class SpeakerTests(unittest.TestCase):
    def test_name_after_the_timestamp(self) -> None:
        cases = {
            "[14:02] Zxsn : Confusion horaire : 1 Pi/2": "Zxsn",
            "[11:22] Korbax lance : Confusion contre horaire : 4 π/4": "Korbax",
            "[14:031 Zxsn : Confision horaire (I tour)": "Zxsn",
            "[14:02) Mi-Lou : Confusion horaire": "Mi-Lou",
            "Zxsn : Confusion horaire : 1 Pi/2": "Zxsn",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(speaker(text), expected)

    def test_tooltip_names_nobody(self) -> None:
        self.assertIsNone(speaker("Confusion contre horaire : 1 Pi/2 - 1"))
        self.assertIsNone(speaker("[14:02] Confflsion horaire : 1 Pi/2"))


class WatchTests(unittest.TestCase):
    def test_turn_then_melee(self) -> None:
        watch = Watch()
        self.assertEqual(watch.feed(TURN_ONE[:3]), Found(Rotation.HALF, 1, "Zxsn"))
        self.assertIsNone(watch.feed(TURN_ONE[:10]))
        self.assertEqual(watch.feed(TURN_ONE[:11]).rotation, Rotation.COUNTERCLOCKWISE)
        self.assertIsNone(watch.feed(TURN_ONE))

    def test_redraw_does_not_repeat_a_melee_line(self) -> None:
        watch = Watch()
        watch.feed(TURN_ONE[:11])
        self.assertIsNone(watch.feed(TURN_ONE[:11]))

    def test_melee_after_the_turn_start_scrolled_off(self) -> None:
        watch = Watch()
        watch.feed(TURN_ONE[:3])
        watch.feed(TURN_ONE[3:10])
        self.assertEqual(watch.feed(TURN_ONE[5:11]).rotation, Rotation.COUNTERCLOCKWISE)
        repeat = "[16:17] Zxsn : Confusion horaire : 1 Pi/2 (1 tour)"
        self.assertEqual(watch.feed([*TURN_ONE[6:11], repeat]).rotation, Rotation.STRAIGHT)
        self.assertIsNone(watch.feed([*TURN_ONE[7:11], repeat, "[16:17] Zxsn lance Stase."]))

    def test_two_lines_in_one_frame_both_count(self) -> None:
        watch = Watch()
        watch.feed(TURN_ONE[:3])
        watch.feed(TURN_ONE[3:9])
        repeat = "[16:17] Zxsn : Confusion horaire : 1 Pi/2 (1 tour)"
        self.assertEqual(watch.feed([*TURN_ONE[4:9], repeat, repeat]).rotation, Rotation.STRAIGHT)

    def test_unmatched_frame_does_not_replay_melee_lines(self) -> None:
        watch = Watch()
        watch.feed(TURN_ONE[:3])
        watch.feed(TURN_ONE[2:])
        found = watch.feed(["[16:18] Nocturlabe lance Rush.", "[16:18] Zxsn : Confusion horaire : 1 Pi/2 (1 tour)"])
        self.assertEqual(found.rotation, Rotation.COUNTERCLOCKWISE)

    def test_next_turn_start_resets(self) -> None:
        watch = Watch()
        watch.feed(TURN_ONE)
        self.assertEqual(watch.feed([*TURN_ONE, *TURN_TWO]).rotation, Rotation.COUNTERCLOCKWISE)
        self.assertIsNone(watch.feed(TURN_TWO))
        melee = ["[16:50] Zxsn lance Aversion.", "[16:50] Cycloïde : -74 PV", TURN_ONE[10]]
        self.assertEqual(watch.feed([*TURN_TWO, *melee]).rotation, Rotation.STRAIGHT)

    def test_hotkey_correction_is_the_base_for_melee(self) -> None:
        watch = Watch()
        watch.feed(TURN_ONE[:3])
        watch.feed(TURN_ONE[3:10])
        watch.correct(Rotation.CLOCKWISE)
        self.assertEqual(watch.feed(TURN_ONE[4:11]).rotation, Rotation.HALF)

    def test_misread_turn_start_gives_nothing(self) -> None:
        watch = Watch()
        watch.feed(TURN_ONE)
        log = ["[16:50] Zxsn lance Comtoise.", "[16:50] Zxsn : Confision horaire (I tour)"]
        self.assertIsNone(watch.feed([*TURN_ONE, *log]))
        self.assertIsNone(watch.feed([*TURN_ONE, *log, "[16:50] Cycloïde : -80 PV", TURN_ONE[10]]))

    def test_companion_keeps_its_own_angle(self) -> None:
        watch = Watch()
        watch.feed(TURN_ONE[:3])
        log = [*TURN_ONE[:3], "[16:18] Korbax lance Comtoise.", "[16:18] Korbax : Confusion horaire : 1 Pi/2"]
        self.assertEqual(watch.feed(log), Found(Rotation.CLOCKWISE, 0, "Korbax"))


if __name__ == "__main__":
    unittest.main()
