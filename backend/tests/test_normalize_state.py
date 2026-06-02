from analysis.geo import normalize_state


def test_spelling_and_alias_variants_collapse():
    assert normalize_state("Orissa") == normalize_state("Odisha")
    assert normalize_state("Tamilnadu") == normalize_state("Tamil Nadu")
    assert normalize_state("Chattisgarh") == normalize_state("Chhattisgarh")
    assert normalize_state("Gao") == normalize_state("Goa")
    assert normalize_state("Nct Of Delhi") == normalize_state("Delhi")
    assert normalize_state("Uttrakhand") == normalize_state("Uttarakhand")
    assert normalize_state("Jammu & Kashmir") == normalize_state("Jammu and Kashmir")


def test_plain_state_normalizes_stably():
    assert normalize_state("Punjab") == normalize_state(" punjab ")
    assert normalize_state("Maharashtra") != normalize_state("Punjab")
