from constants import (
    APPLICATION_NAME,
    SINGLE_INSTANCE_SERVER_NAME,
)


def test_single_instance_name_is_stable():
    assert APPLICATION_NAME == "Kaokey"
    assert SINGLE_INSTANCE_SERVER_NAME == (
        "Kaokey.SingleInstance"
    )
