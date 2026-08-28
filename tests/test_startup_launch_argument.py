from platforms.windows.startup import STARTUP_LAUNCH_ARGUMENT


def test_startup_launch_argument_is_stable():
    assert STARTUP_LAUNCH_ARGUMENT == "--startup"
