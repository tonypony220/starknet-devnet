## Introduction
A Flask wrapper of Starknet dummy network. Similar in purpose to Ganache.

## Requirements
Requires Python and pip.

Run (preferably in a virtual environment):
```
pip install Flask[async] cairo-lang==0.4.0
```
Currently proven to work with cairo-lang 0.4.0

## Run
```
usage: python server.py [-h] [--host HOST] [--port PORT]

Run a local instance of Starknet devnet

optional arguments:
  -h, --help   show this help message and exit
  --host HOST  address to listen at; defaults to localhost
  --port PORT  the port to listen at; defaults to 5000
```

## Test
```
$ ./test.sh
```

## Interaction
Interact with this devnet as you would with the official Starknet [alpha network](https://www.cairo-lang.org/docs/hello_starknet/amm.html?highlight=alpha#interaction-examples).
