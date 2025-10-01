import pytest
from filters import FilterParser

@pytest.mark.parametrize(
    'inp,expected_keys', [
        ("100k mc, 10k volume, 100+ users", ['mc_min','volume_min','holders_min']),
        ("mc > 1m, vol > 50k", ['mc_min','volume_min']),
        ("1m mc, 100k vol, 500 liq", ['mc_min','volume_min','liquidity_min']),
    ]
)
def test_parse_filter(inp, expected_keys):
    parser = FilterParser()
    f = parser.parse_filter(inp)
    for k in expected_keys:
        assert k in f
