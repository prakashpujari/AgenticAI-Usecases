from datetime import date
import pytest

from age_utils import calculate_age, bmi, recommend_measurements


def test_calculate_age_simple():
    # fixed today to 2020-05-15
    y, m, d = calculate_age(1990, 5, 15, today=date(2020, 5, 15))
    assert (y, m, d) == (30, 0, 0)


def test_calculate_age_borrow_days():
    y, m, d = calculate_age(2000, 1, 31, today=date(2020, 3, 1))
    assert y == 20


def test_bmi_and_recommend():
    val = bmi(70, 170)
    assert isinstance(val, float)
    rec = recommend_measurements(30, "female")
    assert "life_stage" in rec and "tips" in rec


def test_invalid_dob():
    with pytest.raises(ValueError):
        calculate_age(3000, 1, 1)
