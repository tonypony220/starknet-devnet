"""
Gateway routes
"""

import json

from flask import Blueprint, jsonify, request
from starkware.starknet.definitions.error_codes import StarknetErrorCode
from starkware.starknet.definitions.transaction_type import TransactionType
from starkware.starkware_utils.error_handling import StarkErrorCode

from starknet_devnet.devnet_config import DumpOn
from starknet_devnet.state import state
from starknet_devnet.util import (
    LogContext,
    StarknetDevnetException,
    extract_transaction_info_to_log,
    fixed_length_hex,
)

from .shared import validate_transaction

gateway = Blueprint("gateway", __name__, url_prefix="/gateway")


@gateway.route("/add_transaction", methods=["POST"])
async def add_transaction():
    """Endpoint for accepting (state-changing) transactions."""
    with LogContext() as context:
        context.update(extract_transaction_info_to_log(json.loads(request.get_data())))
        transaction = validate_transaction(request.get_data())
        tx_type = transaction.tx_type

        response_dict = {
            "code": StarkErrorCode.TRANSACTION_RECEIVED.name,
        }

        if tx_type == TransactionType.DECLARE:
            (
                contract_class_hash,
                transaction_hash,
            ) = await state.starknet_wrapper.declare(transaction, context)
            response_dict["class_hash"] = hex(contract_class_hash)

        elif tx_type == TransactionType.DEPLOY_ACCOUNT:
            (
                contract_address,
                transaction_hash,
            ) = await state.starknet_wrapper.deploy_account(transaction, context)
            response_dict["address"] = fixed_length_hex(contract_address)

        elif tx_type == TransactionType.DEPLOY:
            raise StarknetDevnetException(
                code=StarknetErrorCode.DEPRECATED_TRANSACTION,
                message="Deploy transaction is no longer supported.",
            )

        elif tx_type == TransactionType.INVOKE_FUNCTION:
            (contract_address, transaction_hash) = await state.starknet_wrapper.invoke(
                transaction, context
            )
            response_dict["address"] = fixed_length_hex(contract_address)

        else:
            raise StarknetDevnetException(
                code=StarkErrorCode.MALFORMED_REQUEST,
                message=f"Invalid tx_type: {tx_type.name}.",
                status_code=400,
            )

        response_dict["transaction_hash"] = hex(transaction_hash)

        # after tx
        if state.dumper.dump_on == DumpOn.TRANSACTION:
            state.dumper.dump()
    return jsonify(response_dict)
