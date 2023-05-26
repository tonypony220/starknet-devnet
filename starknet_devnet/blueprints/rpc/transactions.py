"""
RPC transaction endpoints
"""

from typing import List

from starkware.starknet.services.api.feeder_gateway.response_objects import (
    TransactionStatus,
)
from starkware.starknet.services.api.gateway.transaction import AccountTransaction
from starkware.starkware_utils.error_handling import StarkException

from starknet_devnet.blueprints.rpc.schema import validate_schema
from starknet_devnet.blueprints.rpc.structures.payloads import (
    RpcBroadcastedDeclareTxn,
    RpcBroadcastedDeployAccountTxn,
    RpcBroadcastedInvokeTxn,
    RpcBroadcastedTxn,
    RpcTransaction,
    make_declare,
    make_deploy_account,
    make_invoke_function,
    rpc_transaction,
)
from starknet_devnet.blueprints.rpc.structures.responses import (
    RpcDeclareTransactionResult,
    RpcDeployAccountTransactionResult,
    RpcInvokeTransactionResult,
    rpc_transaction_receipt,
)
from starknet_devnet.blueprints.rpc.structures.types import BlockId, RpcError, TxnHash
from starknet_devnet.blueprints.rpc.utils import (
    assert_block_id_is_valid,
    get_block_by_block_id,
    rpc_felt,
)
from starknet_devnet.constants import LEGACY_TX_VERSION
from starknet_devnet.state import state
from starknet_devnet.util import (
    LogContext,
    StarknetDevnetException,
    extract_transaction_info_to_log,
)


@validate_schema("getTransactionByHash")
async def get_transaction_by_hash(transaction_hash: TxnHash) -> dict:
    """
    Get the details and status of a submitted transaction
    """
    try:
        result = await state.starknet_wrapper.transactions.get_transaction(
            transaction_hash
        )
    except StarknetDevnetException as ex:
        raise RpcError.from_spec_name("TXN_HASH_NOT_FOUND") from ex

    if result.status == TransactionStatus.NOT_RECEIVED:
        raise RpcError.from_spec_name("TXN_HASH_NOT_FOUND")

    return rpc_transaction(result.transaction)


@validate_schema("getTransactionByBlockIdAndIndex")
async def get_transaction_by_block_id_and_index(block_id: BlockId, index: int) -> dict:
    """
    Get the details of a transaction by a given block id and index
    """
    block = await get_block_by_block_id(block_id)

    try:
        transaction_hash: int = block.transactions[index].transaction_hash
    except IndexError as ex:
        raise RpcError.from_spec_name("INVALID_TXN_INDEX") from ex

    return await get_transaction_by_hash(transaction_hash=rpc_felt(transaction_hash))


@validate_schema("getTransactionReceipt")
async def get_transaction_receipt(transaction_hash: TxnHash) -> dict:
    """
    Get the transaction receipt by the transaction hash
    """
    try:
        result = await state.starknet_wrapper.transactions.get_transaction_receipt(
            tx_hash=transaction_hash
        )
    except StarknetDevnetException as ex:
        raise RpcError.from_spec_name("TXN_HASH_NOT_FOUND") from ex

    if result.status == TransactionStatus.NOT_RECEIVED:
        raise RpcError.from_spec_name("TXN_HASH_NOT_FOUND")

    return await rpc_transaction_receipt(result)


@validate_schema("pendingTransactions")
async def pending_transactions() -> List[RpcTransaction]:
    """
    Returns the transactions in the transaction pool, recognized by this sequencer
    """
    raise NotImplementedError()


@validate_schema("addInvokeTransaction")
async def add_invoke_transaction(invoke_transaction: RpcBroadcastedInvokeTxn) -> dict:
    """
    Submit a new transaction to be added to the chain
    """
    with LogContext().set_context_name("Invoke rpc transaction") as context:
        context.update(extract_transaction_info_to_log(invoke_transaction))

        _, transaction_hash = await state.starknet_wrapper.invoke(
            external_tx=make_invoke_function(invoke_transaction), context=context
        )
    return RpcInvokeTransactionResult(
        transaction_hash=rpc_felt(transaction_hash),
    )


@validate_schema("addDeclareTransaction")
async def add_declare_transaction(
    declare_transaction: RpcBroadcastedDeclareTxn,
) -> dict:
    """
    Submit a new class declaration transaction
    """
    with LogContext().set_context_name("Declare rpc transaction") as context:
        context.update(extract_transaction_info_to_log(declare_transaction))
        if int(declare_transaction["version"], 0) == LEGACY_TX_VERSION:
            raise RpcError.from_spec_name("INVALID_CONTRACT_CLASS")
        class_hash, transaction_hash = await state.starknet_wrapper.declare(
            external_tx=make_declare(declare_transaction)
        )
    return RpcDeclareTransactionResult(
        transaction_hash=rpc_felt(transaction_hash),
        class_hash=rpc_felt(class_hash),
    )


@validate_schema("addDeployAccountTransaction")
async def add_deploy_account_transaction(
    deploy_account_transaction: RpcBroadcastedDeployAccountTxn,
) -> dict:
    """
    Submit a new deploy account transaction
    """
    with LogContext().set_context_name("Deploy account rpc transaction") as context:
        context.update(extract_transaction_info_to_log(deploy_account_transaction))
        (
            contract_address,
            transaction_hash,
        ) = await state.starknet_wrapper.deploy_account(
            external_tx=make_deploy_account(deploy_account_transaction), context=context
        )

        status_response = (
            await state.starknet_wrapper.transactions.get_transaction_status(
                hex(transaction_hash)
            )
        )
        if (
            status_response["tx_status"] == "REJECTED"
            and "is not declared" in status_response["tx_failure_reason"].error_message
        ):
            raise RpcError.from_spec_name("CLASS_HASH_NOT_FOUND")

    return RpcDeployAccountTransactionResult(
        transaction_hash=rpc_felt(transaction_hash),
        contract_address=rpc_felt(contract_address),
    )


def make_transaction(txn: RpcBroadcastedTxn) -> AccountTransaction:
    """
    Convert RpcBroadcastedTxn to AccountTransaction
    """
    txn_type = txn["type"]
    if txn_type == "INVOKE":
        return make_invoke_function(txn)
    if txn_type == "DECLARE":
        return make_declare(txn)
    if txn_type == "DEPLOY":
        raise RpcError(code=-1, message="DEPLOY transactions are deprecated")
    if txn_type == "DEPLOY_ACCOUNT":
        return make_deploy_account(txn)
    raise NotImplementedError(f"Unexpected type {txn_type}.")


@validate_schema("estimateFee")
async def estimate_fee(request: List[RpcBroadcastedTxn], block_id: BlockId) -> list:
    """
    Estimate the fee for a given Starknet transaction
    """
    await assert_block_id_is_valid(block_id)
    transactions = list(map(make_transaction, request))

    try:
        await state.starknet_wrapper.calculate_traces_and_fees(
            transactions,
            skip_validate=False,
            block_id=block_id,
        )
    except StarkException as ex:
        if "Entry point" in ex.message and "not found" in ex.message:
            raise RpcError.from_spec_name("INVALID_MESSAGE_SELECTOR") from ex
        if "While handling calldata" in ex.message:
            raise RpcError.from_spec_name("INVALID_CALL_DATA") from ex
        if "is not deployed" in ex.message:
            raise RpcError.from_spec_name("CONTRACT_NOT_FOUND") from ex
        raise RpcError(code=-1, message=ex.message) from ex
