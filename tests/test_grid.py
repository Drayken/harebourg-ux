import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grid import Kind, Projection, available_maps, load_map, parse_site_layout, parse_text

COMTE_SITE = (
    '{"size":[22,22],"details":[[1,9,12,1],[2,7,14,1],[3,5,16,1],[4,4,11,1],[4,13,17,1],'
    "[5,3,11,1],[5,12,13,2],[5,14,18,1],[6,3,11,1],[6,12,13,2],[6,14,18,1],[7,2,11,1],"
    "[7,14,18,1],[7,19,19,2],[8,2,19,1],[9,1,2,2],[9,4,20,1],[10,1,2,2],[10,3,9,1],"
    "[10,10,11,2],[10,12,20,1],[11,1,9,1],[11,10,11,2],[11,12,20,1],[12,1,20,1],[13,2,19,1],"
    "[14,2,19,1],[15,3,5,1],[15,6,8,2],[15,10,18,1],[16,3,5,1],[16,6,8,2],[16,10,14,1],"
    '[16,16,18,1],[17,4,14,1],[17,15,15,2],[17,16,17,1],[18,5,16,1],[19,7,14,1],[20,9,12,1]]}'
)


class LayoutTests(unittest.TestCase):
    def test_comte_file_matches_simulator_string(self) -> None:
        self.assertIn("comte", available_maps())
        from_file = load_map("comte")
        from_site = parse_site_layout("comte", COMTE_SITE)
        self.assertEqual(from_file.rows, from_site.rows)
        self.assertEqual((from_file.width, from_file.height), (22, 22))

    def test_kinds_and_holes(self) -> None:
        layout = load_map("comte")
        self.assertEqual(layout.kind((9, 1)), Kind.WALKABLE)
        self.assertEqual(layout.kind((12, 5)), Kind.WALL)
        self.assertEqual(layout.kind((0, 0)), Kind.EMPTY)
        self.assertEqual(layout.kind((-1, 30)), Kind.EMPTY)
        self.assertTrue(layout.is_hole((12, 4)))
        self.assertTrue(layout.is_hole((3, 9)))
        self.assertFalse(layout.is_hole((0, 9)))
        self.assertFalse(layout.is_hole((9, 1)))

    def test_text_round_trip_and_bad_char(self) -> None:
        layout = load_map("comte")
        self.assertEqual(parse_text("again", layout.to_text()).rows, layout.rows)
        with self.assertRaises(ValueError):
            parse_text("bad", "..x..\n")


class ProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.projection = Projection(400, 100, 86, 43)

    def test_center_formula(self) -> None:
        self.assertEqual(self.projection.center((0, 0)), (400, 100))
        self.assertEqual(self.projection.center((1, 0)), (443, 121.5))
        self.assertEqual(self.projection.center((0, 1)), (357, 121.5))

    def test_hit_test_round_trip(self) -> None:
        for cell in ((0, 0), (5, 3), (21, 21), (3, 17), (-2, 4)):
            cx, cy = self.projection.center(cell)
            with self.subTest(cell=cell):
                self.assertEqual(self.projection.cell_at(cx, cy), cell)
                self.assertEqual(self.projection.cell_at(cx + 20, cy + 5), cell)
                self.assertEqual(self.projection.cell_at(cx - 5, cy - 10), cell)

    def test_neighbours_share_vertices(self) -> None:
        projection = Projection(400.3, 100.7, 61.4, 30.7)
        top, right, bottom, left = projection.diamond((4, 4))
        east = projection.diamond((5, 4))
        south = projection.diamond((4, 5))
        self.assertEqual((east[0], east[3]), (right, bottom))
        self.assertEqual((south[0], south[1]), (left, bottom))

    def test_bounds_move_and_scale(self) -> None:
        layout = load_map("comte")
        left, top, right, bottom = self.projection.bounds(layout)
        moved = self.projection.moved(5, -3)
        self.assertEqual(moved.bounds(layout), (left + 5, top - 3, right + 5, bottom - 3))
        scaled = self.projection.scaled(2, 0.5, left, top)
        s_left, s_top, s_right, s_bottom = scaled.bounds(layout)
        self.assertEqual((s_left, s_top), (left, top))
        self.assertAlmostEqual(s_right - s_left, (right - left) * 2, delta=1)
        self.assertAlmostEqual(s_bottom - s_top, (bottom - top) * 0.5, delta=1)

    def test_fit_centers_used_cells(self) -> None:
        layout = load_map("comte")
        fitted = self.projection.fit(layout, 1000, 600, margin=20)
        used = [cell for cell, kind in layout.cells() if kind is not Kind.EMPTY]
        xs = [x for cell in used for x, _ in fitted.diamond(cell)]
        ys = [y for cell in used for _, y in fitted.diamond(cell)]
        self.assertGreaterEqual(min(xs), 19)
        self.assertLessEqual(max(xs), 981)
        self.assertGreaterEqual(min(ys), 19)
        self.assertLessEqual(max(ys), 581)
        self.assertAlmostEqual(fitted.cell_width / fitted.cell_height, 2)

    def test_uniform_scale_locks_the_diamond_ratio(self) -> None:
        stretched = Projection(100, 80, 40, 30)
        anchor_x, anchor_y = 10.0, 20.0
        u = (anchor_x - stretched.origin_x) / (stretched.cell_width / 2)
        v = (anchor_y - stretched.origin_y) / (stretched.cell_height / 2)
        scaled = stretched.scaled_uniform(1.5, anchor_x, anchor_y)
        self.assertAlmostEqual(scaled.cell_width, 60)
        self.assertAlmostEqual(scaled.cell_height, 30)
        self.assertAlmostEqual(scaled.origin_x + u * (scaled.cell_width / 2), anchor_x)
        self.assertAlmostEqual(scaled.origin_y + v * (scaled.cell_height / 2), anchor_y)


if __name__ == "__main__":
    unittest.main()
