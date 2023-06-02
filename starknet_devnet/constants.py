"""Constants used across the project."""

from importlib.metadata import version

CAIRO_LANG_VERSION = version("cairo-lang")
TIMEOUT_FOR_WEB3_REQUESTS = 120  # seconds
L1_MESSAGE_CANCELLATION_DELAY = (
    0  # Min amount of time in seconds for a message to be able to be cancelled
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5050

DEFAULT_ACCOUNTS = 10
DEFAULT_INITIAL_BALANCE = 10**21
DEFAULT_GAS_PRICE = 10**8

SUPPORTED_TX_VERSION = 1
SUPPORTED_RPC_TX_VERSION = 1

SUPPORTED_RPC_DECLARE_TX_VERSION = 2
DEPRECATED_RPC_DECLARE_TX_VERSION = 1

DUMMY_STATE_ROOT = bytes(32)
DUMMY_PENDING_BLOCK_HASH = 0

DEFAULT_TIMEOUT = 60  # seconds

OLD_SUPPORTED_VERSIONS = [0]

# account used by Starknet CLI; calculated using
# poetry run python scripts/compute_compiled_class_hash.py \
#   ~/.cache/pypoetry/virtualenvs/<YOUR_VENV>/lib/python3.9/site-packages/starkware/starknet/third_party/open_zeppelin/account.json
STARKNET_CLI_ACCOUNT_CLASS_HASH = (
    0x7AB95E820D92B974797C8F139AD72F8550ADAA068FEBE4E38DA9A4A9539A81D
)

# starkware.starknet.public.abi.get_selector_from_name("replace_class")
REPLACE_CLASS_SELECTOR = (
    0x217DF192877EED2921E241046523F8D8DA7981F0A3DDAFE0E7517F6523276D2
)

LEGACY_RPC_TX_VERSION = 0
LEGACY_TX_VERSION = 0
