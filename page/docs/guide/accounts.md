---
sidebar_position: 13
---

# Accounts

## Predeployed accounts

Devnet predeploys `--accounts` with some `--initial-balance`. To hide the details of these accounts use `--hide-predeployed-contracts`. The accounts get charged for transactions according to the `--gas-price`. A `--seed` can be used to regenerate the same set of accounts. Read more about it in the [Run section](run.md).

To get the code of the account (currently OpenZeppelin [v0.5.1](https://github.com/OpenZeppelin/cairo-contracts/releases/tag/v0.5.1)), use one of the following:

- `GET /get_code?contractAddress=<ACCOUNT_ADDRESS>`
- [Starknet CLI](https://www.cairo-lang.org/docs/hello_starknet/cli.html#get-code): `starknet get_code --contract_address <ACCOUNT_ADDRESS> --feeder_gateway_url <DEVNET_URL>`
- [GitHub repository](https://github.com/0xSpaceShard/cairo-contracts/tree/fix-account-query-version)

You can use the accounts in e.g. [**starknet-hardhat-plugin**](https://github.com/0xSpaceShard/starknet-hardhat-plugin) via:

```typescript
const account = await starknet.OpenZeppelin.getAccountFromAddress(
  ADDRESS,
  PRIVATE_KEY
);
```

## Custom implementation

To make the predeployed accounts use an account implementation of your choice, you can provide the path to a contract compilation artifact:

```bash
starknet-devnet --account-class path/to/my/account.json
```

## Fetch predeployed accounts

```
GET /predeployed_accounts
```

Response:

```
[
  {
    "initial_balance": 1e+21,
    "address": "0x7c3e2...",
    "private_key": "0x6160...",
    "public_key": "0x6a5540..."
  },
  ...
]
```

## Fetch account balance

```
GET /account_balance?address=<HEX_ADDRESS>
```

Response:

```
{
  "amount": 123...456,
  "unit": "wei"
}
```

## Argent

If you attempt to deploy an Argent account to Devnet (e.g. via the Argent X browser extension), you may get an error like:

```
Class with hash 0x25ec026985a3bf9d0cc1fe17326b245dfdc3ff89b8fde106542a3ea56c5a918 is not declared
```

That means the ArgentProxy class is not declared. You can either declare it manually or run Devnet in [forked mode](fork.md), forking it from a network where this class is declared, e.g. alpha-goerli:

```
$ starknet-devnet --fork-network alpha-goerli
```
