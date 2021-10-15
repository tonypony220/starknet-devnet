## Introduction
A Flask wrapper of Starknet dummy network. Similar in purpose to Ganache.

## Install

pip install starknet-devnet

## Run
```
usage: starknet-devnet [-h] [--host HOST] [--port PORT]

Run a local instance of Starknet devnet

optional arguments:
  -h, --help   show this help message and exit
  --host HOST  the address to listen at; defaults to 0.0.0.0 (use the address the program outputs on start)
  --port PORT  the port to listen at; defaults to 5000
```

## Important notes
- `host`:
  - Currently, specifying `--host=localhost` or `--host=127.0.0.1` will not work with [the Hardhat plugin](#hardhat-integration) because of Docker networking issues which are being fixed.
  - Rely on the default behavior of `--host=0.0.0.0`, but keep in mind that this will use your local IP address (printed on program startup), making it accessible by others on the network.
- Types in call/invoke:
  - You will NOT be able to pass or receive values of type other than `felt` and `felt*`.

## Test
A basic test to see if everything's working properly:
```
$ ./test.sh
```

## Interaction
Interact with this devnet as you would with the official Starknet [alpha network](https://www.cairo-lang.org/docs/hello_starknet/amm.html?highlight=alpha#interaction-examples).

## Hardhat integration
- Be sure to read [Important notes](#important-notes).
- If you're using [the Hardhat plugin](https://github.com/Shard-Labs/starknet-hardhat-plugin), see [here](https://github.com/Shard-Labs/starknet-hardhat-plugin#testing-network) on how to edit its config file to integrate this devnet.
