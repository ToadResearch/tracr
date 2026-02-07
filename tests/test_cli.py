from tracr.cli import _local_tui_base_url


def test_local_tui_base_url_maps_wildcard_host_to_loopback() -> None:
    assert _local_tui_base_url("0.0.0.0", 8787) == "http://127.0.0.1:8787"


def test_local_tui_base_url_keeps_specific_host() -> None:
    assert _local_tui_base_url("127.0.0.1", 9001) == "http://127.0.0.1:9001"
