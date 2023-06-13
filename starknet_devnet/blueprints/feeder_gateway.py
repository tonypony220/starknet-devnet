"""
Feeder gateway routes.
"""

from typing import Type

from flask import Blueprint, Response, jsonify, request
from marshmallow import ValidationError
from starkware.starknet.services.api.feeder_gateway.request_objects import (
    CallFunction,
    CallL1Handler,
)
from starkware.starknet.services.api.feeder_gateway.response_objects import (
    LATEST_BLOCK_ID,
    PENDING_BLOCK_ID,
    BlockTransactionTraces,
    StarknetBlock,
    TransactionSimulationInfo,
)
from starkware.starknet.services.api.gateway.transaction import (
    AccountTransaction,
    InvokeFunction,
    Transaction,
)
from starkware.starkware_utils.error_handling import StarkErrorCode
from starkware.starkware_utils.validated_dataclass import ValidatedMarshmallowDataclass
from werkzeug.datastructures import MultiDict

from starknet_devnet.blueprints.rpc.structures.types import BlockId
from starknet_devnet.state import state
from starknet_devnet.util import (
    StarknetDevnetException,
    fixed_length_hex,
    parse_hex_string,
)

feeder_gateway = Blueprint("feeder_gateway", __name__, url_prefix="/feeder_gateway")


def validate_request(data: bytes, cls: Type[ValidatedMarshmallowDataclass], many=False):
    """Ensure `data` is valid Starknet function call. Returns an object of type specified with `cls`."""
    try:
        return cls.Schema().loads(data, many=many)
    except (AttributeError, KeyError, TypeError, ValidationError) as err:
        raise StarknetDevnetException(
            code=StarkErrorCode.MALFORMED_REQUEST,
            message=f"Invalid {cls.__name__}: {err}",
            status_code=400,
        ) from err


def validate_int(request_args: MultiDict, attribute: str):
    """Validate if attribute is int."""
    try:
        return int(request_args.get(attribute))
    except (ValueError) as err:
        raise StarknetDevnetException(
            code=StarkErrorCode.MALFORMED_REQUEST,
            message=str(err),
            status_code=400,
        ) from err


def _extract_raw_block_arguments(args: MultiDict):
    block_hash = args.get("blockHash")
    block_number = args.get("blockNumber")

    if block_hash is not None and block_number is not None:
        message = "Ambiguous criteria: only one of (block number, block hash) can be provided."
        raise StarknetDevnetException(
            code=StarkErrorCode.MALFORMED_REQUEST, message=message
        )

    return block_hash, block_number


async def _get_block_object(args: MultiDict) -> StarknetBlock:
    """Returns the block object"""
    block_hash, block_number = _extract_raw_block_arguments(args)

    if block_hash is not None:
        return await state.starknet_wrapper.blocks.get_by_hash(block_hash)

    return await state.starknet_wrapper.blocks.get_by_number(block_number)


async def _get_block_transaction_traces(block: StarknetBlock):
    traces = []
    if block.transaction_receipts:
        for transaction in block.transaction_receipts:
            tx_hash = hex(transaction.transaction_hash)
            trace = await state.starknet_wrapper.transactions.get_transaction_trace(
                tx_hash
            )

            # expected trace is equal to response of get_transaction, but with the hash property
            trace_dict = trace.dump()
            trace_dict["transaction_hash"] = tx_hash
            traces.append(trace_dict)

    # assert correct structure
    return BlockTransactionTraces.load({"traces": traces})


def _get_block_id(args: MultiDict) -> BlockId:
    block_number = args.get("blockNumber")
    block_hash = args.get("blockHash")

    if block_number is None and block_hash is None:
        return "latest"

    if block_number is None:
        # there is some hash
        return {"block_hash": block_hash}

    if block_number in [PENDING_BLOCK_ID, LATEST_BLOCK_ID]:
        return block_number

    # there is some number and it should be an integer
    return {"block_number": block_number}


def _get_skip_validate(args: MultiDict) -> bool:
    skip_validate = args.get("skipValidate")

    if skip_validate == "true":
        return True

    if skip_validate == "false":
        return False

    # default case (user did not specify)
    if skip_validate is None:
        return False

    raise StarknetDevnetException(
        code=StarkErrorCode.MALFORMED_REQUEST,
        message=f"Invalid value for skipValidate: {skip_validate}. Should be true or false.",
    )


@feeder_gateway.route("/get_contract_addresses", methods=["GET"])
def get_contract_addresses():
    """Endpoint that returns an object containing the addresses of key system components."""
    return "Not implemented", 501


@feeder_gateway.route("/call_contract", methods=["POST"])
async def call_contract():
    """
    Endpoint for receiving calls (not invokes) of contract functions.
    """

    block_id = _get_block_id(request.args)
    data = request.get_data()  # better than request.data in some edge cases

    try:
        # version 1
        call_specifications = validate_request(data, CallFunction)
    except StarknetDevnetException:
        # version 0
        call_specifications = validate_request(data, InvokeFunction)

    result_dict = await state.starknet_wrapper.call(call_specifications, block_id)
    return jsonify(result_dict)


@feeder_gateway.route("/get_block", methods=["GET"])
async def get_block():
    """Endpoint for retrieving a block identified by its hash or number."""

    block = await _get_block_object(request.args)
    block_dump = block.dump()

    # This is a hack to fix StarknetBlock.loads(data=raw_response)
    if "transaction_receipts" not in block_dump:
        block_dump["transaction_receipts"] = None

    return jsonify(block_dump)


@feeder_gateway.route("/get_block_traces", methods=["GET"])
async def get_block_traces():
    """Returns the traces of the transactions in the specified block."""

    block = await _get_block_object(request.args)
    block_transaction_traces = await _get_block_transaction_traces(block)
    return jsonify(block_transaction_traces.dump())


@feeder_gateway.route("/get_code", methods=["GET"])
async def get_code():
    """
    Returns the ABI and bytecode of the contract whose contractAddress is provided.
    """

    block_id = _get_block_id(request.args)

    contract_address = request.args.get("contractAddress", type=parse_hex_string)
    code_dict = await state.starknet_wrapper.get_code(contract_address, block_id)
    return jsonify(code_dict)


@feeder_gateway.route("/get_full_contract", methods=["GET"])
async def get_full_contract():
    """
    Returns the contract class of the contract whose contractAddress is provided.
    """
    block_id = _get_block_id(request.args)
    contract_address = request.args.get("contractAddress", type=parse_hex_string)
    contract_class = await state.starknet_wrapper.get_class_by_address(
        contract_address, block_id
    )

    # strip debug_info if cairo 0 class
    class_program = contract_class.get("program")
    if class_program and class_program.get("debug_info"):
        class_program["debug_info"] = None

    return jsonify(contract_class)


@feeder_gateway.route("/get_class_hash_at", methods=["GET"])
async def get_class_hash_at():
    """Get contract class hash by contract address"""

    contract_address = request.args.get("contractAddress", type=parse_hex_string)
    class_hash = await state.starknet_wrapper.get_class_hash_at(contract_address)
    return jsonify(fixed_length_hex(class_hash))


@feeder_gateway.route("/get_class_by_hash", methods=["GET"])
async def get_class_by_hash():
    """Get contract class by class hash"""

    class_hash = request.args.get("classHash", type=parse_hex_string)
    class_dict = await state.starknet_wrapper.get_class_by_hash(class_hash)
    # if isinstance(contract_class, DeprecatedCompiledClass):
    #     contract_class = contract_class.remove_debug_info()

    return jsonify(class_dict)


@feeder_gateway.route("/get_compiled_class_by_class_hash", methods=["GET"])
async def get_compiled_class_by_hash():
    """Get compiled class by class hash (sierra hash)"""
    class_hash = request.args.get("classHash", type=parse_hex_string)
    compiled_class = await state.starknet_wrapper.get_compiled_class_by_class_hash(
        class_hash
    )
    return jsonify(compiled_class.dump())


@feeder_gateway.route("/get_storage_at", methods=["GET"])
async def get_storage_at():
    """Endpoint for returning the storage identified by `key` from the contract at"""
    block_id = _get_block_id(request.args)

    contract_address = request.args.get("contractAddress", type=parse_hex_string)
    key = validate_int(request.args, "key")

    storage = await state.starknet_wrapper.get_storage_at(
        contract_address, key, block_id
    )
    return jsonify(storage)


@feeder_gateway.route("/get_transaction_status", methods=["GET"])
async def get_transaction_status():
    """
    Returns the status of the transaction identified by the transactionHash argument in the GET request.
    """

    transaction_hash = request.args.get("transactionHash")
    tx_status = await state.starknet_wrapper.transactions.get_transaction_status(
        transaction_hash
    )
    return jsonify(tx_status)


@feeder_gateway.route("/get_transaction", methods=["GET"])
async def get_transaction():
    """
    Returns the transaction identified by the transactionHash argument in the GET request.
    """

    transaction_hash = request.args.get("transactionHash")
    transaction_info = await state.starknet_wrapper.transactions.get_transaction(
        transaction_hash
    )
    return Response(
        response=transaction_info.dumps(), status=200, mimetype="application/json"
    )


@feeder_gateway.route("/get_transaction_receipt", methods=["GET"])
async def get_transaction_receipt():
    """
    Returns the transaction receipt identified by the transactionHash argument in the GET request.
    """

    transaction_hash = request.args.get("transactionHash")
    tx_receipt = await state.starknet_wrapper.transactions.get_transaction_receipt(
        transaction_hash
    )
    return Response(
        response=tx_receipt.dumps(), status=200, mimetype="application/json"
    )


@feeder_gateway.route("/get_transaction_trace", methods=["GET"])
async def get_transaction_trace():
    """
    Returns the trace of the transaction identified by the transactionHash argument in the GET request.
    """

    transaction_hash = request.args.get("transactionHash")
    transaction_trace = await state.starknet_wrapper.transactions.get_transaction_trace(
        transaction_hash
    )

    return Response(
        response=transaction_trace.dumps(), status=200, mimetype="application/json"
    )


@feeder_gateway.route("/get_state_update", methods=["GET"])
async def get_state_update():
    """
    Returns the status update from the block identified by the blockHash argument in the GET request.
    If no block hash was provided it will default to the last block.
    """

    block_hash, block_number = _extract_raw_block_arguments(request.args)

    state_update = await state.starknet_wrapper.blocks.get_state_update(
        block_hash=block_hash, block_number=block_number
    )

    assert state_update is not None
    return jsonify(state_update.dump())


@feeder_gateway.route("/estimate_fee", methods=["POST"])
async def estimate_fee():
    """Returns the estimated fee for a transaction."""
    data = request.get_data()

    try:
        transaction = validate_request(data, Transaction)  # version 1
    except StarknetDevnetException:
        transaction = validate_request(data, InvokeFunction)  # version 0

    block_id = _get_block_id(request.args)
    skip_validate = _get_skip_validate(request.args)

    _, fee_response = await state.starknet_wrapper.calculate_trace_and_fee(
        transaction, skip_validate=skip_validate, block_id=block_id
    )
    return jsonify(fee_response)


@feeder_gateway.route("/estimate_fee_bulk", methods=["POST"])
async def estimate_fee_bulk():
    """Returns the estimated fee for a bulk of transactions."""

    try:
        # version 1
        transactions = validate_request(request.get_data(), Transaction, many=True)
    except StarknetDevnetException:
        # version 0
        transactions = validate_request(request.get_data(), InvokeFunction, many=True)

    block_id = _get_block_id(request.args)
    skip_validate = _get_skip_validate(request.args)

    _, fee_responses, _ = await state.starknet_wrapper.calculate_traces_and_fees(
        transactions,
        block_id=block_id,
        skip_validate=skip_validate,
    )
    return jsonify(fee_responses)


@feeder_gateway.route("/simulate_transaction", methods=["POST"])
async def simulate_transaction():
    """Returns the estimated fee for a transaction."""
    transaction = validate_request(request.get_data(), AccountTransaction)
    block_id = _get_block_id(request.args)
    skip_validate = _get_skip_validate(request.args)

    trace, fee_response = await state.starknet_wrapper.calculate_trace_and_fee(
        transaction,
        block_id=block_id,
        skip_validate=skip_validate,
    )

    simulation_info = TransactionSimulationInfo(
        trace=trace, fee_estimation=fee_response
    )

    return jsonify(simulation_info.dump())


@feeder_gateway.route("/get_nonce", methods=["GET"])
async def get_nonce():
    """Returns the nonce of the contract whose contractAddress is provided"""

    block_id = _get_block_id(request.args)
    contract_address = request.args.get("contractAddress", type=parse_hex_string)
    nonce = await state.starknet_wrapper.get_nonce(contract_address, block_id)

    return jsonify(hex(nonce))


@feeder_gateway.route("/estimate_message_fee", methods=["POST"])
async def estimate_message_fee():
    """Message fee estimation endpoint"""

    block_id = _get_block_id(request.args)

    call = validate_request(request.get_data(), CallL1Handler)
    fee_estimation = await state.starknet_wrapper.estimate_message_fee(call, block_id)
    return jsonify(fee_estimation)
