"""
Utility functions used across the project.
"""
import logging
import os
import sys
import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from starkware.starknet.business_logic.state.state import CachedState
from starkware.starknet.definitions.error_codes import StarknetErrorCode
from starkware.starknet.services.api.feeder_gateway.response_objects import (
    ClassHashPair,
    ContractAddressHashPair,
    FeeEstimationInfo,
    StorageEntry,
)
from starkware.starknet.testing.contract import StarknetContract
from starkware.starkware_utils.error_handling import StarkErrorCode, StarkException


def parse_hex_string(arg: str) -> int:
    """
    Converts the argument to an integer only if it starts with `0x`.
    """
    if isinstance(arg, str) and arg.startswith("0x"):
        try:
            return int(arg, 16)
        except ValueError:
            pass

    raise StarknetDevnetException(
        code=StarkErrorCode.MALFORMED_REQUEST,
        message=f"Hash should be a hexadecimal string starting with 0x, or 'null'; got: '{arg}'.",
    )


def fixed_length_hex(arg: int) -> str:
    """
    Converts the int input to a hex output of fixed length
    """
    return f"0x{arg:064x}"


def to_int_array(values: List[str]) -> List[int]:
    """Convert to List of ints"""
    return [int(numeric, 16) for numeric in values]


@dataclass
class Uint256:
    """Abstraction of Uint256 type"""

    low: int
    high: int

    def to_felt(self) -> int:
        """Converts to felt."""
        return (self.high << 128) + self.low

    @staticmethod
    def from_felt(felt: int) -> "Uint256":
        """Converts felt to Uint256"""
        return Uint256(low=felt & ((1 << 128) - 1), high=felt >> 128)


class StarknetDevnetException(StarkException):
    """
    Exception raised across the project.
    Indicates the raised issue is devnet-related.
    """

    def __init__(self, code: StarknetErrorCode, status_code=500, message=None):
        super().__init__(code=code, message=message)
        self.status_code = status_code


class UndeclaredClassDevnetException(StarknetDevnetException):
    """Exception raised when Devnet has to return an undeclared class"""

    def __init__(self, class_hash: int):
        super().__init__(
            code=StarknetErrorCode.UNDECLARED_CLASS,
            message=f"Class with hash {class_hash:#x} is not declared.",
        )


def enable_pickling():
    """
    Extends the `StarknetContract` class to enable pickling.
    """

    def contract_getstate(self):
        return self.__dict__

    def contract_setstate(self, state):
        self.__dict__ = state

    StarknetContract.__getstate__ = contract_getstate
    StarknetContract.__setstate__ = contract_setstate


def check_valid_dump_path(dump_path: str):
    """Checks if dump path is a directory. Raises ValueError if not."""

    dump_path_dir = os.path.dirname(dump_path)

    if not dump_path_dir:
        # dump_path is just a file, with no parent dir
        return

    if not os.path.isdir(dump_path_dir):
        raise ValueError(f"Invalid dump path: directory '{dump_path_dir}' not found.")


def str_to_felt(text: str) -> int:
    """Converts string to felt."""
    return int.from_bytes(bytes(text, "ascii"), "big")


async def group_classes_by_version(
    contracts: List[ContractAddressHashPair], state: CachedState
) -> Tuple[List[int], List[ContractAddressHashPair]]:
    """Group into two lists: cairo0 contracts and  cairo1 contracts"""
    cairo0_classes: List[int] = []
    cairo1_classes: List[ContractAddressHashPair] = []
    for contract in contracts:
        compiled_class_hash = await state.get_compiled_class_hash(contract.class_hash)
        if compiled_class_hash == 0:
            cairo0_classes.append(contract.class_hash)
        else:
            class_hash_pair = ClassHashPair(contract.class_hash, compiled_class_hash)
            cairo1_classes.append(class_hash_pair)
    return cairo0_classes, cairo1_classes


async def get_all_declared_cairo0_classes(
    previous_state: CachedState,
    explicitly_declared_contracts: List[int],
    deployed_cairo0_classes: List[int],
) -> Tuple[int]:
    """Returns a tuple of explicitly and implicitly declared cairo0 classes"""
    declared_contracts_set = set(explicitly_declared_contracts)
    for deployed_contract in deployed_cairo0_classes:
        try:
            await previous_state.get_compiled_class_by_class_hash(deployed_contract)
        except StarkException:
            declared_contracts_set.add(deployed_contract)
    return tuple(declared_contracts_set)


async def get_all_declared_cairo1_classes(
    previous_state: CachedState,
    explicitly_declared_classes: List[ClassHashPair],
    deployed_cairo1_contracts: List[ContractAddressHashPair],
) -> List[ClassHashPair]:
    """Returns a list of explicitly and implicitly declared cairo1 classes"""
    declared_classes_set = set(explicitly_declared_classes)
    for deployed_contract in deployed_cairo1_contracts:
        try:
            await previous_state.get_compiled_class_by_class_hash(
                deployed_contract.class_hash
            )
        except StarkException:
            declared_classes_set.add(deployed_contract.class_hash)
    return list(declared_classes_set)


async def get_replaced_classes(
    previous_state: CachedState,
    current_state: CachedState,
) -> List[ContractAddressHashPair]:
    """Find contracts whose class has been replaced"""
    replaced: List[ContractAddressHashPair] = []
    for address, class_hash in current_state.cache.address_to_class_hash.items():
        previous_class_hash = await previous_state.get_class_hash_at(address)
        if previous_class_hash and previous_class_hash != class_hash:
            replaced.append(
                ContractAddressHashPair(address=address, class_hash=class_hash)
            )
    return replaced


async def get_storage_diffs(
    previous_state: CachedState,
    current_state: CachedState,
    visited_storage_entries: Set[StorageEntry],
):
    """Returns storages modified from change"""
    assert previous_state is not current_state

    storage_diffs: Dict[int, List[StorageEntry]] = {}

    for address, key in visited_storage_entries or {}:
        old_storage_value = await previous_state.get_storage_at(address, key)
        new_storage_value = await current_state.get_storage_at(address, key)
        if old_storage_value != new_storage_value:
            if address not in storage_diffs:
                storage_diffs[address] = []
            storage_diffs[address].append(
                StorageEntry(
                    key=key,
                    value=await current_state.get_storage_at(address, key),
                )
            )

    return storage_diffs


async def assert_not_declared(class_hash: int, compiled_class_hash: int):
    """Assert class is not declared"""
    if compiled_class_hash != 0:
        raise StarknetDevnetException(
            code=StarknetErrorCode.CLASS_ALREADY_DECLARED,
            message=f"Class with hash {hex(class_hash)} is already declared.\n {hex(compiled_class_hash)} != 0",
        )


def assert_recompiled_class_hash(recompiled: int, expected: int):
    """Assert the class hashes match"""
    if recompiled != expected:
        raise StarknetDevnetException(
            code=StarknetErrorCode.INVALID_COMPILED_CLASS_HASH,
            message=f"Compiled class hash not matching; received: {hex(expected)}, computed: {hex(recompiled)}",
        )


def get_fee_estimation_info(tx_fee: int, gas_price: int):
    """Construct fee estimation response"""

    gas_usage = tx_fee // gas_price if gas_price else 0

    return FeeEstimationInfo.load(
        {
            "overall_fee": tx_fee,
            "unit": "wei",
            "gas_price": gas_price,
            "gas_usage": gas_usage,
        }
    )


def warn(msg: str, file=sys.stderr):
    """Log a warning"""
    print(f"\033[93m{msg}\033[0m", file=file)


class LogSuppressor:
    """Context manager to suppress logger"""

    def __init__(self, logger_name):
        # check logger exists
        assert logger_name in logging.Logger.manager.loggerDict
        self.logger = logging.getLogger(logger_name)

    def __enter__(self):
        self.logger.disabled = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.disabled = False


# FeederGatewayClient is implemented in such a way that it logs and raises;
# this suppresses the logging
suppress_feeder_gateway_client_logger = LogSuppressor("services.external_api.client")


class OrderedDictCache(OrderedDict):
    def __init__(self, cache_id=None):
        super().__init__()
        self.hits = 0
        self.misses = 0
        self.cache_id = cache_id


class CachedProxy:
    """
    LRU cache. Cache results of async calls of provided object
    """

    def __init__(self, proxied_object, maxsize=512, cache_id=None):
        self._proxied = proxied_object
        self.maxsize = maxsize  # number of elements in cache
        self.cache = OrderedDictCache(cache_id=cache_id)

    def __getattr__(self, attr):
        # recursion protection when pickling
        proxied_object = object.__getattribute__(self, '_proxied')
        attr = getattr(proxied_object, attr, None)
        # attr = object.__getattribute__(self._proxied, attr)
        # print("getting ", attr, flush=True)
        # attr = getattr(self._proxied, attr, None)
        if attr is None:
            raise AttributeError
        if asyncio.iscoroutinefunction(attr):  # caching only coroutines
            return self.async_cached_method(attr)
        return attr

    def async_cached_method(self, method):
        cache = self.cache

        async def wrapped_method(*args, **kwargs):
            # key = hash_params(*args, **kwargs)
            # key = (method.__name__, args, tuple(sorted(kwargs.items())))
            key = (method.__name__, args)
            if key in cache:
                cache.move_to_end(key)
                result = cache[key]
                self.cache.hits += 1
                print("------------ The method {} is return from cache. key={}".format(method, key))
                return result
            self.cache.misses += 1
            result = await method(*args, **kwargs)
            # print("The result was {}.".format(result))
            while len(cache) >= self.maxsize:
                # if cache.__sizeof__() > self.maxsize_in_bytes:
                # if sys.getsizeof(cache) > self.maxsize_in_bytes:
                # if total_size(cache) > self.maxsize_in_bytes:
                # if len(cache) > self.maxsize_in_bytes:
                # print("max", self.maxsize_in_bytes, flush=True)
                # print("deleting len=", len(cache))
                # print("cur", sys.getsizeof(cache), flush=True)
                # print("cur", cache.__sizeof__(), flush=True)
                cache.popitem(last=False)
            # print("cur items", sys.getsizeof(cache.items()), flush=True)
            # print("cur cache", cache.__sizeof__(), flush=True)
            cache[key] = result
            print( "++++++++++++ The method {} exec. key={}".format( method, key))
            return result
        return wrapped_method
