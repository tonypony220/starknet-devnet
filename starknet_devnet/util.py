from enum import Enum, auto
import argparse

class TxStatus(Enum):
    PENDING = auto()
    NOT_RECEIVED = auto()


DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000
def parse_args():
    parser = argparse.ArgumentParser(description="Run a local instance of Starknet devnet")
    parser.add_argument(
        "--host",
        help=f"the address to listen at; defaults to {DEFAULT_HOST} (use the address the program outputs on start)",
        default=DEFAULT_HOST
    )
    parser.add_argument(
        "--port",
        type=int,
        help=f"the port to listen at; defaults to {DEFAULT_PORT}",
        default=DEFAULT_PORT
    )

    return parser.parse_args()