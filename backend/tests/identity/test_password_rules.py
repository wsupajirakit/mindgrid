from mindgrid.platform.identity import passwords


def test_lower_upper_and_digit_are_required_symbols_are_optional() -> None:
    assert passwords.missing_kinds("Abcdefgh1") == []
    assert passwords.missing_kinds("Ab1!@#$%^ &*") == []
    assert passwords.missing_kinds("abcdefgh1") == ["upper"]
    assert passwords.missing_kinds("ABCDEFGH1") == ["lower"]
    assert passwords.missing_kinds("Abcdefghi") == ["digit"]
    assert passwords.missing_kinds("!@#$%^&*()") == ["lower", "upper", "digit"]


def test_letters_and_digits_outside_ascii_do_not_count() -> None:
    assert passwords.missing_kinds("Abcdéfgh\u0661") == ["digit"]
    assert passwords.missing_kinds("กขคงจฉชซ9") == ["lower", "upper"]
