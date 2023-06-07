"""
Contains classes that provide the abstraction of L2 blockchain.
"""
import asyncio
from collections import OrderedDict
import cloudpickle as pickle

from services.external_api.client import BadRequest
from starknet_devnet.devnet_config import get_network_name_from_url
from starkware.starknet.definitions.error_codes import StarknetErrorCode
from starkware.starknet.services.api.feeder_gateway.feeder_gateway_client import (
    FeederGatewayClient,
)
from starkware.starknet.services.api.feeder_gateway.response_objects import (
    StarknetBlock,
    TransactionInfo,
    TransactionReceipt,
    TransactionStatus,
    TransactionTrace,
)

from starknet_devnet.forked_state import is_originally_starknet_exception
from starknet_devnet.util import (
    StarknetDevnetException,
    UndeclaredClassDevnetException,
    suppress_feeder_gateway_client_logger,
)


class Origin:
    """
    Abstraction of an L2 blockchain.
    """

    async def get_transaction_status(self, transaction_hash: str):
        """Returns the status of the transaction."""
        raise NotImplementedError

    async def get_transaction(self, transaction_hash: str) -> TransactionInfo:
        """Returns the transaction object."""
        raise NotImplementedError

    async def get_transaction_receipt(
        self, transaction_hash: str
    ) -> TransactionReceipt:
        """Returns the transaction receipt object."""
        raise NotImplementedError

    async def get_transaction_trace(self, transaction_hash: str) -> TransactionTrace:
        """Returns the transaction trace object."""
        raise NotImplementedError

    async def get_block_by_hash(self, block_hash: str) -> StarknetBlock:
        """Returns the block identified with either its hash."""
        raise NotImplementedError

    async def get_block_by_number(self, block_number: int) -> StarknetBlock:
        """Returns the block identified with either its number or the latest block if no number provided."""
        raise NotImplementedError

    def get_number_of_blocks(self):
        """Returns the number of blocks stored so far"""
        raise NotImplementedError

    async def get_state_update(
        self, block_hash: str = None, block_number: int = None
    ) -> dict:
        """
        Returns the state update for provided block hash or block number.
        If none are provided return the last state update
        """
        raise NotImplementedError

    async def get_class_by_hash(
        self, class_hash: int, block_number: int = None
    ) -> dict:
        """Return DeprecatedCompiledClass for cairo0 contracts and ContractClass for cairo1 contracts"""
        raise NotImplementedError


class NullOrigin(Origin):
    """
    A default class to comply with the Origin interface.
    """

    async def get_transaction_status(self, transaction_hash: str):
        return {"tx_status": TransactionStatus.NOT_RECEIVED.name}

    async def get_transaction(self, transaction_hash: str) -> TransactionInfo:
        return TransactionInfo.create(
            status=TransactionStatus.NOT_RECEIVED,
        )

    async def get_transaction_receipt(
        self, transaction_hash: str
    ) -> TransactionReceipt:
        return TransactionReceipt(
            status=TransactionStatus.NOT_RECEIVED,
            transaction_hash=0,  # testnet returns 0 instead of received hash
            events=[],
            l2_to_l1_messages=[],
            block_hash=None,
            block_number=None,
            transaction_index=None,
            execution_resources=None,
            actual_fee=None,
            transaction_failure_reason=None,
            l1_to_l2_consumed_message=None,
        )

    async def get_transaction_trace(self, transaction_hash: str):
        tx_hash_int = int(transaction_hash, 16)
        message = f"Transaction corresponding to hash {tx_hash_int} is not found."
        raise StarknetDevnetException(
            code=StarknetErrorCode.INVALID_TRANSACTION_HASH, message=message
        )

    async def get_block_by_hash(self, block_hash: str):
        message = f"Block hash not found; got: {block_hash}."
        raise StarknetDevnetException(
            code=StarknetErrorCode.BLOCK_NOT_FOUND, message=message
        )

    async def get_block_by_number(self, block_number: int):
        message = "Requested the latest block, but there are no blocks so far."
        raise StarknetDevnetException(
            code=StarknetErrorCode.BLOCK_NOT_FOUND, message=message
        )

    def get_number_of_blocks(self):
        return 0

    async def get_state_update(
        self, block_hash: str = None, block_number: int = None
    ) -> dict:
        if block_hash:
            error_message = (
                f"No state updates saved for the provided block hash {block_hash}"
            )
            raise StarknetDevnetException(
                code=StarknetErrorCode.BLOCK_NOT_FOUND, message=error_message
            )

        if block_number is not None:
            error_message = (
                f"No state updates saved for the provided block number {block_number}"
            )
            raise StarknetDevnetException(
                code=StarknetErrorCode.BLOCK_NOT_FOUND, message=error_message
            )

    async def get_class_by_hash(
        self, class_hash: int, block_number: int = None
    ) -> dict:
        raise UndeclaredClassDevnetException(class_hash)


class ForkedOrigin(Origin):
    """
    Abstracts an origin that the devnet was forked from.
    """

    def __init__(
        self, feeder_gateway_client: FeederGatewayClient, last_block_number: int
    ):
        self.__feeder_gateway_client = feeder_gateway_client
        self.__number_of_blocks = last_block_number + 1

    async def get_transaction_status(self, transaction_hash: str):
        return await self.__feeder_gateway_client.get_transaction_status(
            transaction_hash
        )

    async def get_transaction(self, transaction_hash: str):
        return await self.__feeder_gateway_client.get_transaction(transaction_hash)

    async def get_transaction_receipt(
        self, transaction_hash: str
    ) -> TransactionReceipt:
        return await self.__feeder_gateway_client.get_transaction_receipt(
            transaction_hash
        )

    async def get_transaction_trace(self, transaction_hash: str):
        try:
            with suppress_feeder_gateway_client_logger:
                return await self.__feeder_gateway_client.get_transaction_trace(
                    transaction_hash
                )
        except BadRequest as bad_request:
            if is_originally_starknet_exception(bad_request):
                raise StarknetDevnetException(
                    code=StarknetErrorCode.INVALID_TRANSACTION_HASH,
                    message=f"Transaction corresponding to hash {transaction_hash} is not found.",
                ) from bad_request
            raise

    async def get_block_by_hash(self, block_hash: str) -> StarknetBlock:
        custom_exception = StarknetDevnetException(
            code=StarknetErrorCode.BLOCK_NOT_FOUND,
            message=f"Block hash {block_hash} does not exist.",
        )
        try:
            with suppress_feeder_gateway_client_logger:
                block = await self.__feeder_gateway_client.get_block(
                    block_hash=block_hash
                )
            if block.block_number > self.get_number_of_blocks():
                raise custom_exception
            return block
        except BadRequest as bad_request:
            if is_originally_starknet_exception(bad_request):
                raise custom_exception from bad_request
            raise

    async def get_block_by_number(self, block_number: int):
        return await self.__feeder_gateway_client.get_block(block_number=block_number)

    def get_number_of_blocks(self):
        return self.__number_of_blocks

    async def get_state_update(
        self, block_hash: str = None, block_number: int = None
    ) -> dict:
        try:
            with suppress_feeder_gateway_client_logger:
                return await self.__feeder_gateway_client.get_state_update(
                    block_hash=block_hash,
                    block_number=block_number,
                )
        except BadRequest as bad_request:
            if is_originally_starknet_exception(bad_request):
                raise StarknetDevnetException(
                    code=StarknetErrorCode.BLOCK_NOT_FOUND,
                    message=f"Block hash {block_hash} does not exist.",
                ) from bad_request
            raise

    async def get_class_by_hash(
        self, class_hash: int, block_number: int = None
    ) -> dict:
        try:
            with suppress_feeder_gateway_client_logger:
                return await self.__feeder_gateway_client.get_class_by_hash(
                    hex(class_hash), block_number=block_number
                )
        except BadRequest as bad_request:
            if is_originally_starknet_exception(bad_request):
                raise UndeclaredClassDevnetException(class_hash) from bad_request
            raise


class CachedProxy:
    """
    LRU cache results of calls provided object
    """

    def __init__(self, proxied_object, maxsize=512):
        self._proxied = proxied_object
        self.maxsize = maxsize  # number of elements in cache
        self.cache = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.dump_filename = "cache_dump.pkl"

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
                self.hits += 1
                print("------------ The method {} is return from cache. key={}".format(method, key))
                return result
            self.misses += 1
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


    def _load(self):
        try:
            with open(self.dump_filename, "rb") as file:
                return pickle.load(file)
        except FileNotFoundError:
            return None

    def try_load_from_dump(self):
        loaded_cache = self._load()
        if loaded_cache:
            self.cache = loaded_cache

    def dump(self):
        with open(self.dump_filename, "w+b") as file:
            pickle.dump(self.cache, file)
        print("Cache dumped to ", self.dump_filename)
        print(f"Current len: {len(self.cache)}")
        print(f"Hits: {self.hits}")
        print(f"Misses: {self.misses}")
        # print(f"cache: ", self.cache)


class CachedForkedOrigin(CachedProxy):
    """
    Caching wrapped over ForkedOrigin. Dumps cache
    """

    def __init__(
            self,
            feeder_gateway_client: FeederGatewayClient,
            last_block_number: int
    ):
        origin = ForkedOrigin(feeder_gateway_client, last_block_number)

        super().__init__(origin)
        network_name = get_network_name_from_url(feeder_gateway_client.url)
        self.dump_filename = f"cache_dump_{network_name}:{last_block_number}.pkl"
        self.try_load_from_dump()

