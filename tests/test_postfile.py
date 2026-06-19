from xtools.postfile import weighted_length, MAX_WEIGHTED_LEN


def test_weighted_length_ascii_is_one_each():
    assert weighted_length("a" * 280) == 280


def test_weighted_length_japanese_is_two_each():
    assert weighted_length("あ" * 140) == 280


def test_max_constant():
    assert MAX_WEIGHTED_LEN == 280
