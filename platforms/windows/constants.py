# =============================
# Global hotkey
# =============================

GLOBAL_HOTKEY_ID = 1

# Win32 fsModifiers flags used by RegisterHotKey().
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

# Virtual-key codes used both by RegisterHotKey() and GetAsyncKeyState().
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_F1 = 0x70


# =============================
# Win32 messages
# =============================

WM_HOTKEY = 0x0312


# =============================
# Temporary caret diagnostics
# =============================

# Keep the diagnostic code available, but disable console noise
# during normal use.
CARET_DIAGNOSTICS_ENABLED = False

# Maximum coordinate difference that still counts as the same
# one-frame-stale caret position.
CARET_STALE_POSITION_TOLERANCE = 2


# =============================
# Automatic insertion
# =============================

# After Windows accepts the injected Unicode input,
# give the target application a short moment to
# consume it before returning focus to the popup.
INSERTION_POPUP_REFOCUS_DELAY_MS = 80


# =============================
# Hotkey release before insertion
# =============================

# SendInput does not reset the physical keyboard state. Wait until the
# current global-hotkey keys are released before injecting Unicode.
INSERTION_KEY_RELEASE_POLL_INTERVAL_MS = 10
INSERTION_KEY_RELEASE_MAX_ATTEMPTS = 50
