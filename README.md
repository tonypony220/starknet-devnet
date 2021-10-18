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

## Test
A basic test to see if everything's working properly:
```text
$ ./test.sh
```

## Interaction
Interact with this devnet as you would with the official Starknet [alpha network](https://www.cairo-lang.org/docs/hello_starknet/amm.html?highlight=alpha#interaction-examples).

## Hardhat integration
- Be sure to read [Important notes](#important-notes).
- If you're using [the Hardhat plugin](https://github.com/Shard-Labs/starknet-hardhat-plugin), see [here](https://github.com/Shard-Labs/starknet-hardhat-plugin#testing-network) on how to edit its config file to integrate this devnet.
