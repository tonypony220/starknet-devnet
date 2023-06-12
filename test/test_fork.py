"""
Test the forking feature.
Relying on the fact that devnet doesn't support specifying which block to query
"""
import os

import pytest
import requests

from starknet_devnet.constants import DEFAULT_INITIAL_BALANCE
from starknet_devnet.origin import CachedForkedOrigin

from .account import declare_and_deploy_with_chargeable, get_nonce, invoke
from .settings import APP_URL, HOST, bind_free_port
from .shared import (
    ABI_PATH,
    ALPHA_GOERLI2_URL,
    ALPHA_GOERLI_URL,
    CONTRACT_PATH,
    PREDEPLOY_ACCOUNT_CLI_ARGS,
    PREDEPLOYED_ACCOUNT_ADDRESS,
    PREDEPLOYED_ACCOUNT_PRIVATE_KEY,
)
from .test_account import get_account_balance
from .test_deploy import assert_deployed_through_syscall, deploy_account_test_body
from .testnet_deployment import (
    TESTNET_CONTRACT_ADDRESS,
    TESTNET_DEPLOYMENT_BLOCK,
    TESTNET_FORK_PARAMS,
    TESTNET_URL,
)
from .util import (
    DevnetBackgroundProc,
    assert_address_has_no_class_hash,
    assert_tx_status,
    call,
    devnet_in_background,
    mint,
    get_full_contract)

ORIGIN_PORT, ORIGIN_URL = bind_free_port(HOST)
FORK_PORT, FORK_URL = bind_free_port(HOST)

FORKING_DEVNET = DevnetBackgroundProc()


@pytest.fixture(autouse=True)
def run_before_and_after_test():
    """Cleanup after tests finish."""
    # before test
    FORKING_DEVNET.stop()
    yield
    # after test
    FORKING_DEVNET.stop()


def _invoke_on_fork_and_assert_only_fork_changed(
    contract_address: str,
    initial_balance: str,
    fork_url: str,
    origin_url: str,
):
    # account nonce - before
    origin_nonce_before = get_nonce(
        account_address=PREDEPLOYED_ACCOUNT_ADDRESS, feeder_gateway_url=origin_url
    )
    fork_nonce_before = get_nonce(
        account_address=PREDEPLOYED_ACCOUNT_ADDRESS, feeder_gateway_url=fork_url
    )

    # do the invoke and implicitly estimate fee before that
    increase_args = [1, 2]
    invoke_tx_hash = invoke(
        calls=[(contract_address, "increase_balance", increase_args)],
        account_address=PREDEPLOYED_ACCOUNT_ADDRESS,
        private_key=PREDEPLOYED_ACCOUNT_PRIVATE_KEY,
        gateway_url=fork_url,
    )
    # assert only received on fork
    assert_tx_status(invoke_tx_hash, "NOT_RECEIVED", feeder_gateway_url=origin_url)
    assert_tx_status(invoke_tx_hash, "ACCEPTED_ON_L2", feeder_gateway_url=fork_url)
    # assert only callable
    origin_balance_after = call(
        function="get_balance",
        abi_path=ABI_PATH,
        address=contract_address,
        feeder_gateway_url=origin_url,
    )
    assert origin_balance_after == initial_balance

    fork_balance_after = call(
        function="get_balance",
        abi_path=ABI_PATH,
        address=contract_address,
        feeder_gateway_url=fork_url,
    )
    expected_balancer_after = str(int(initial_balance) + sum(increase_args))
    assert fork_balance_after == expected_balancer_after

    # account nonce - after
    origin_nonce_after = get_nonce(
        account_address=PREDEPLOYED_ACCOUNT_ADDRESS, feeder_gateway_url=origin_url
    )
    assert origin_nonce_after == origin_nonce_before
    fork_nonce_after = get_nonce(
        account_address=PREDEPLOYED_ACCOUNT_ADDRESS, feeder_gateway_url=fork_url
    )
    assert fork_nonce_after == fork_nonce_before + 1


@devnet_in_background("--port", ORIGIN_PORT, *PREDEPLOY_ACCOUNT_CLI_ARGS)
def test_forking_devnet_with_account_on_origin():
    """
    Deploy contract on origin, invoke on fork, rely on account on origin.
    Assert only fork changed
    """

    # deploy on origin
    initial_balance = "10"
    deploy_info = declare_and_deploy_with_chargeable(
        contract=CONTRACT_PATH,
        inputs=[initial_balance],
        gateway_url=ORIGIN_URL,
    )

    # fork
    FORKING_DEVNET.start(
        "--port", FORK_PORT, "--fork-network", ORIGIN_URL, "--accounts", "0"
    )

    # account balance - before
    origin_balance_before = get_account_balance(
        address=PREDEPLOYED_ACCOUNT_ADDRESS, server_url=ORIGIN_URL
    )
    assert origin_balance_before == DEFAULT_INITIAL_BALANCE

    fork_balance_before = get_account_balance(
        # fork has access to balances on origin
        address=PREDEPLOYED_ACCOUNT_ADDRESS,
        server_url=FORK_URL,
    )
    assert fork_balance_before == DEFAULT_INITIAL_BALANCE

    _invoke_on_fork_and_assert_only_fork_changed(
        contract_address=deploy_info["address"],
        initial_balance=initial_balance,
        fork_url=FORK_URL,
        origin_url=ORIGIN_URL,
    )

    # account balance - after
    origin_balance_after = get_account_balance(
        address=PREDEPLOYED_ACCOUNT_ADDRESS, server_url=ORIGIN_URL
    )
    assert origin_balance_after == DEFAULT_INITIAL_BALANCE

    fork_balance_after = get_account_balance(
        address=PREDEPLOYED_ACCOUNT_ADDRESS, server_url=FORK_URL
    )
    assert fork_balance_after < DEFAULT_INITIAL_BALANCE


@devnet_in_background("--port", ORIGIN_PORT, "--accounts", "0")
def test_forking_devnet_with_account_on_fork():
    """
    Deploy contract on origin, invoke on fork, rely on account on fork.
    Assert only fork changed
    """

    # declare_and_deploy_with_chargeable on origin
    initial_balance = "10"
    deploy_info = declare_and_deploy_with_chargeable(
        contract=CONTRACT_PATH,
        inputs=[initial_balance],
        gateway_url=ORIGIN_URL,
    )

    # fork
    FORKING_DEVNET.start(
        "--port", FORK_PORT, "--fork-network", ORIGIN_URL, *PREDEPLOY_ACCOUNT_CLI_ARGS
    )

    # account balance - before
    origin_balance_before = get_account_balance(
        address=PREDEPLOYED_ACCOUNT_ADDRESS, server_url=ORIGIN_URL
    )
    assert origin_balance_before == 0

    fork_balance_before = get_account_balance(
        address=PREDEPLOYED_ACCOUNT_ADDRESS, server_url=FORK_URL
    )
    assert fork_balance_before == DEFAULT_INITIAL_BALANCE

    _invoke_on_fork_and_assert_only_fork_changed(
        contract_address=deploy_info["address"],
        initial_balance=initial_balance,
        fork_url=FORK_URL,
        origin_url=ORIGIN_URL,
    )

    # account balance - after
    origin_balance_after = get_account_balance(
        address=PREDEPLOYED_ACCOUNT_ADDRESS, server_url=ORIGIN_URL
    )
    assert origin_balance_after == 0

    fork_balance_after = get_account_balance(
        address=PREDEPLOYED_ACCOUNT_ADDRESS, server_url=FORK_URL
    )
    assert fork_balance_after < DEFAULT_INITIAL_BALANCE


@pytest.mark.usefixtures("run_devnet_in_background")
@pytest.mark.parametrize(
    "run_devnet_in_background",
    [
        [*TESTNET_FORK_PARAMS, "--fork-block", str(TESTNET_DEPLOYMENT_BLOCK)],
        [*TESTNET_FORK_PARAMS, "--fork-block", str(TESTNET_DEPLOYMENT_BLOCK + 1)],
        [*TESTNET_FORK_PARAMS, "--fork-block", "latest"],
        [*TESTNET_FORK_PARAMS],  # should default to latest
    ],
    indirect=True,
)
def test_forking_testnet_from_valid_block():
    """Test forking from various happy path blocks"""

    _invoke_on_fork_and_assert_only_fork_changed(
        contract_address=TESTNET_CONTRACT_ADDRESS,
        initial_balance="10",
        fork_url=APP_URL,
        origin_url=TESTNET_URL,
    )


@pytest.mark.usefixtures("run_devnet_in_background")
@pytest.mark.parametrize(
    "run_devnet_in_background, origin_url",
    [
        (
            # Used to be a mainnet test, but it's a problem if mainnet hasn't been updated
            [*PREDEPLOY_ACCOUNT_CLI_ARGS, "--fork-network", "alpha-goerli"],
            ALPHA_GOERLI_URL,
        ),
        ([*TESTNET_FORK_PARAMS], TESTNET_URL),
    ],
    indirect=["run_devnet_in_background"],
)
def test_deploy_on_fork(origin_url):
    """
    Deploy on fork, invoke on fork.
    Assert usability on fork. Assert no change on origin.
    """

    deploy_info = declare_and_deploy_with_chargeable(
        contract=CONTRACT_PATH, inputs=["10"]
    )
    contract_address = deploy_info["address"]

    invoke_tx_hash = invoke(
        calls=[(contract_address, "increase_balance", [1, 2])],
        account_address=PREDEPLOYED_ACCOUNT_ADDRESS,
        private_key=PREDEPLOYED_ACCOUNT_PRIVATE_KEY,
    )
    assert_tx_status(invoke_tx_hash, "ACCEPTED_ON_L2")

    balance_after = call(
        function="get_balance",
        address=contract_address,
        abi_path=ABI_PATH,
    )
    assert balance_after == "13"

    assert_address_has_no_class_hash(contract_address, origin_url)


@devnet_in_background(
    *TESTNET_FORK_PARAMS, "--fork-block", str(TESTNET_DEPLOYMENT_BLOCK - 1)
)
def test_forking_testnet_from_too_early_block():
    """Test forking testnet if not yet deployed"""

    invoke_tx_hash = invoke(
        calls=[(TESTNET_CONTRACT_ADDRESS, "increase_balance", [2, 3])],  # random values
        account_address=PREDEPLOYED_ACCOUNT_ADDRESS,
        private_key=PREDEPLOYED_ACCOUNT_PRIVATE_KEY,
        max_fee=int(1e8),  # to prevent implicit fee estimation
    )

    # assertions on fork (devnet)
    assert_tx_status(invoke_tx_hash, "REJECTED")
    assert_address_has_no_class_hash(TESTNET_CONTRACT_ADDRESS)

    # assertions on origin (testnet)
    # this will fail if someone invokes `increase_balance(2, 3)` because it will then be REJECTED instead of NOT_RECEIVED
    assert_tx_status(invoke_tx_hash, "NOT_RECEIVED", feeder_gateway_url=TESTNET_URL)


@devnet_in_background(*TESTNET_FORK_PARAMS)
@pytest.mark.parametrize("lite", [True, False])
def test_minting(lite: bool):
    """Test minting"""
    dummy_address = "0x123"
    dummy_amount = 100

    resp = mint(dummy_address, dummy_amount, lite=lite)
    assert resp["new_balance"] == dummy_amount
    resp = mint(dummy_address, dummy_amount, lite=lite)
    assert resp["new_balance"] == dummy_amount * 2


@devnet_in_background(*TESTNET_FORK_PARAMS)
def test_deploy_account():
    """Test that deploy account functionality works when forking"""
    deploy_account_test_body()


@devnet_in_background(*TESTNET_FORK_PARAMS)
def test_declare_and_deploy_happy_path():
    """Test that deploying with udc works when forking"""
    initial_balance = 10
    deploy_info = declare_and_deploy_with_chargeable(
        contract=CONTRACT_PATH, inputs=[initial_balance], salt=hex(42)
    )

    assert_deployed_through_syscall(
        tx_hash=deploy_info["tx_hash"],
        initial_balance=initial_balance,
    )


@devnet_in_background(*TESTNET_FORK_PARAMS)
def test_fork_status_forked():
    """Test GET on /fork_status when forking"""
    resp = requests.get(f"{APP_URL}/fork_status")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("url") == ALPHA_GOERLI2_URL
    assert data.get("block") is not None


@devnet_in_background(
    *TESTNET_FORK_PARAMS, "--fork-block", str(TESTNET_DEPLOYMENT_BLOCK)
)
def test_fork_status_forked_at_block():
    """Test GET on /fork_status when forking a given block"""
    resp = requests.get(f"{APP_URL}/fork_status")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("url") == ALPHA_GOERLI2_URL
    assert data.get("block") == TESTNET_DEPLOYMENT_BLOCK


@devnet_in_background()
def test_fork_status_not_forked():
    """Test GET on /fork_status when not forking"""
    resp = requests.get(f"{APP_URL}/fork_status")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {}



@devnet_in_background("--port", ORIGIN_PORT, *PREDEPLOY_ACCOUNT_CLI_ARGS)
def test_cache_of_forked_origin():
    """Test cache of forked origin works, dumps on exit, and loads if forked network and block is the same"""
    deploy_info = declare_and_deploy_with_chargeable(
        contract=CONTRACT_PATH,
        inputs=["10"],
        gateway_url=ORIGIN_URL,
    )
    # fork
    os.remove(CachedForkedOrigin.DUMP_FILENAME)
    FORKING_DEVNET.start(
        "--port", FORK_PORT, "--fork-network", ORIGIN_URL, "--accounts", "0"
    )
    for i in range(3):
        full_contract_fork = get_full_contract(
            contract_address=deploy_info["address"],
            feeder_gateway_url=FORK_URL,
        )
    FORKING_DEVNET.stop()
    cache = CachedForkedOrigin.load_cache()
    assert cache, "Not dumped"
    assert cache.hits == 2
    assert cache.misses == 1

    # test cache persist between launches of devnet
    FORKING_DEVNET.start(
        "--port", FORK_PORT, "--fork-network", ORIGIN_URL, "--accounts", "0"
    )
    full_contract_fork = get_full_contract(
        contract_address=deploy_info["address"],
        feeder_gateway_url=FORK_URL,
    )
    FORKING_DEVNET.stop()
    cache = CachedForkedOrigin.load_cache()
    assert cache, "Not dumped"
    assert cache.hits == 3
    assert cache.misses == 1

    # testing that dump overwrites for different fork network
    FORKING_DEVNET.start(
        "--port", *TESTNET_FORK_PARAMS, "--fork-block", str(TESTNET_DEPLOYMENT_BLOCK)
    )
    full_contract_fork = get_full_contract(
        contract_address=deploy_info["address"],
        feeder_gateway_url=FORK_URL,
    )
    FORKING_DEVNET.stop()
    cache = CachedForkedOrigin.load_cache()
    assert cache, "Not dumped"
    assert cache.hits == 0
    assert cache.misses == 1


    # resp = requests.get(f"{APP_URL}/fork_status")
    # assert resp.status_code == 200
    # data = resp.json()
    # assert data.get("url") == ALPHA_GOERLI2_URL
    # assert data.get("block") == TESTNET_DEPLOYMENT_BLOCK


