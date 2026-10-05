import pytest

from bluetooth import safer_plus

# Captured from a real Redmi Buds 5 Pro (2026-10-05): the earbuds answered each random challenge
# the app sent. The cipher must reproduce what the hardware computes.
EARBUD_ANSWERS = [
    ("9762e8a1836d32cc4b7b8605c553545f", "f7fe2d0211bab715efe4c33ac740574d"),
    ("9ddc4d55a9f74b1c2df9d11a2762b281", "ac0512878403a24c87d1b6cb974061c9"),
    ("a979ae189a0c36bf973de72297ed1595", "7b09a3799fa3005472c2673c9c45e82b"),
    ("57990d37d3dad961ee7e6a092ba4f2ef", "6b21b2bdd693d3147ee9e6f41e46eb87"),
]

# The earbuds sent this challenge and accepted this answer (authentication result 01 00).
ACCEPTED_BY_EARBUDS = ("60c881a805416aeeaa3a1e079d879568", "787748b987ecf34ab33464eaa78f44ba")


@pytest.mark.parametrize("challenge, answer", EARBUD_ANSWERS)
def test_matches_what_real_earbuds_compute(challenge, answer):
    assert safer_plus.challenge_response(bytes.fromhex(challenge)).hex() == answer


def test_answer_the_earbuds_accepted():
    challenge, answer = ACCEPTED_BY_EARBUDS
    assert safer_plus.challenge_response(bytes.fromhex(challenge)).hex() == answer


def test_exp_and_log_tables_are_inverses():
    # log(1) must be 0: a Java byte[] defaults to 0 and the reference port left 128 (it broke auth).
    assert safer_plus._LOG[1] == 0
    assert all(safer_plus._LOG[safer_plus._EXP[x]] == x for x in range(256))


def test_tables_match_the_public_safer_plus_spec():
    assert list(safer_plus._EXP[:8]) == [1, 45, 226, 147, 190, 69, 21, 174]
    assert list(safer_plus._BIAS[0]) == [70, 151, 177, 186, 163, 183, 16, 10, 197, 55, 179, 201, 90, 40, 172, 100]


def test_linear_layer_is_the_armenian_shuffle_pht_network():
    shuffle = [8, 11, 12, 15, 2, 1, 6, 5, 10, 9, 14, 13, 0, 7, 4, 3]

    def pht(x):
        out = list(x)
        for i in range(0, 16, 2):
            out[i], out[i + 1] = 2 * x[i] + x[i + 1], x[i] + x[i + 1]
        return out

    def layer(x):
        for step in range(4):
            x = pht(x)
            if step != 3:
                x = [x[shuffle[k]] for k in range(16)]
        return x

    for j in range(16):
        unit = [0] * 16
        unit[j] = 1
        column = layer(unit)
        assert column == [safer_plus._COEFFICIENTS[i][j] for i in range(16)]


def test_wrong_sizes_are_rejected():
    with pytest.raises(ValueError):
        safer_plus.encrypt(b"short", bytes(16))
    with pytest.raises(ValueError):
        safer_plus.encrypt(bytes(16), b"short")
