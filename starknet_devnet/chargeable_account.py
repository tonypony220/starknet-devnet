"""
Account that is charged with a fee when nobody else can be charged.
"""
import sys
from starknet_devnet.account import Account
from .util import warn


class ChargeableAccount(Account):
    """
    A well-funded account that can be charged with a fee when no other account can.
    E.g. for signing mint txs. Can also be useful in tests.
    """

    PRIVATE_KEY = 0x5FB2959E3011A873A7160F5BB32B0ECE
    PUBLIC_KEY = 0x4C37AB4F0994879337BFD4EAD0800776DB57DA382B8ED8EFAA478C5D3B942A4
    ADDRESS = 0x1CAF2DF5ED5DDE1AE3FAEF4ACD72522AC3CB16E23F6DC4C7F9FAED67124C511

    def __init__(self, starknet_wrapper):
        super().__init__(
            starknet_wrapper,
            private_key=ChargeableAccount.PRIVATE_KEY,
            public_key=ChargeableAccount.PUBLIC_KEY,
            initial_balance=2**251,  # loads of cash
            account_class_wrapper=starknet_wrapper.config.account_class,
        )

    def __print(self):
        """stdout chargeable account"""
        print(f"\nPredeployed chargeable account")
        print(f"Address: {hex(self.address)}")
        print(f"Public key: {hex(self.public_key)}")
        print(f"Private key: {hex(self.private_key)}")
        print(f"Initial balance of chargeable account: {self.initial_balance} WEI")
        warn(
            "WARNING: Use these accounts and their keys ONLY for local testing. "
            "DO NOT use them on mainnet or other live networks because you will LOSE FUNDS.\n",
            file=sys.stderr,
        )
        sys.stdout.flush()
