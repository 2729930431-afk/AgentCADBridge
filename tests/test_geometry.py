import math

import pytest

from cadbridge.backends.geometry import orbit, path_placements


def test_nonrotating_orbit_still_changes_position():
    assert orbit((12, 10, 0), (10, 10, 0), math.pi / 2) == pytest.approx((10, 12, 0))


def test_path_uses_nonzero_base_and_turn_relative_to_original_heading():
    result = path_placements([(10, 20), (10, 30), (20, 30)], 3)
    assert result[0][0] == pytest.approx((10, 30, 0))
    assert result[0][1] == pytest.approx(0)
    assert result[1][0] == pytest.approx((20, 30, 0))
    assert result[1][1] == pytest.approx(-math.pi / 2)


@pytest.mark.parametrize("points", [[], [(0, 0)], [(0, 0), (0, 0)]])
def test_invalid_paths_rejected_before_copying(points):
    with pytest.raises(ValueError):
        path_placements(points, 3)
