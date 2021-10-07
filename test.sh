#!/bin/bash

trap 'kill $(jobs -p)' EXIT
python server.py &

source .env

output=$(starknet deploy --contract $CONTRACT_PATH --gateway_url=$GATEWAY_URL)
echo $output
deploy_tx_id=$(echo $output | sed -r "s/.*Transaction ID: (\w*).*/\1/")
address=$(echo $output | sed -r "s/.*Contract address: (\w*).*/\1/")
echo "Address: $address"
echo "tx_id: $deploy_tx_id"
starknet invoke --function increase_balance --inputs 10 20 --address $address --abi $ABI_PATH --gateway_url=$GATEWAY_URL
#starknet tx_status --id $deploy_tx_id
RESULT=$(starknet call --function get_balance --address $address --abi $ABI_PATH --feeder_gateway_url=$FEEDER_GATEWAY_URL)

echo
if [ $RESULT == 30 ]; then
    echo "Success!"
else
    echo "Test failed!"
    exit 1
fi
