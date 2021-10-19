## Introduction
A Flask wrapper of Starknet dummy network. Similar in purpose to Ganache.

## Install
```text
pip install starknet-devnet
```

## Run
```text
usage: starknet-devnet [-h] [--host HOST] [--port PORT]

Run a local instance of Starknet devnet

optional arguments:
  -h, --help   show this help message and exit
  --host HOST  the address to listen at; defaults to localhost (use the address the program outputs on start)
  --port PORT  the port to listen at; defaults to 5000
```

## Important notes
- Types in call/invoke:
  - You will NOT be able to pass or receive values of type other than `felt` and `felt*`.

## Interaction
Interact with this devnet as you would with the official Starknet [alpha network](https://www.cairo-lang.org/docs/hello_starknet/amm.html?highlight=alpha#interaction-examples).

## Hardhat integration
- Be sure to read [Important notes](#important-notes).
- If you're using [the Hardhat plugin](https://github.com/Shard-Labs/starknet-hardhat-plugin), see [here](https://github.com/Shard-Labs/starknet-hardhat-plugin#testing-network) on how to edit its config file to integrate this devnet.

## Development - Prerequisite
If you're a developer willing to contribute, be sure to have installed [Poetry](https://pypi.org/project/poetry/). Check the link for more information.

## Development - Run
```text
poetry run starknet-devnet
```

## Development - Test
`test.sh` contains a basic test to check if everything's working properly.

Create `.env` which will hold variables required by the test. See `.env.example` for help.
```text
$ ./test.sh
```

## Development - Build
```text
poetry build
```
