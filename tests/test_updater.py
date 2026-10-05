import pytest

from utils.updater import parse_version


@pytest.mark.parametrize(
    "text, expected",
    [
        ("v1.2.3", (1, 2, 3, 4, 0)),
        ("1.2.3", (1, 2, 3, 4, 0)),
        ("v1.2.3-alpha.1", (1, 2, 3, 1, 1)),
        ("v1.2.3-beta.2", (1, 2, 3, 2, 2)),
        ("v1.2.3-rc1", (1, 2, 3, 3, 1)),
        ("v1.2.3-beta", (1, 2, 3, 2, 0)),
    ],
)
def test_parse_version(text, expected):
    assert parse_version(text) == expected


def test_prerelease_order_is_alpha_beta_rc_final():
    ordered = ["v1.0.0-alpha.1", "v1.0.0-beta.1", "v1.0.0-rc1", "v1.0.0"]
    assert [parse_version(v) for v in ordered] == sorted(parse_version(v) for v in ordered)


def test_versions_compare_numerically_not_as_text():
    assert parse_version("v0.10.0") > parse_version("v0.2.0")


def test_a_release_is_newer_than_its_own_prerelease():
    assert parse_version("v0.3.0") > parse_version("v0.3.0-rc2")


def test_two_part_version_equals_the_same_with_a_zero_patch():
    assert parse_version("v1.2") == parse_version("v1.2.0")
