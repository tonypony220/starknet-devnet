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
$ python server.py
```

## Test
```
$ ./test.sh
```

## Use
Use this devnet like you would use the official Starknet [alpha network](https://www.cairo-lang.org/docs/hello_starknet/amm.html?highlight=alpha#interaction-examples).
