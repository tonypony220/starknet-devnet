from flask import Flask, request, jsonify
from starkware.starknet.testing.starknet import Starknet
from starkware.starknet.testing.contract import StarknetContract
from starkware.starknet.compiler.compile import compile_starknet_files

app = Flask(__name__)
address2contract = {}

class StarknetWrapper:
    def __init__(self):
        self.starknet = None
    
    async def get_starknet(self):
        if not self.starknet:
            self.starknet = await Starknet.empty()
        return self.starknet

starknet_wrapper = StarknetWrapper()

@app.route("/deploy", methods=["POST"])
async def deploy():
    starknet = await starknet_wrapper.get_starknet()

    source_path = request.form["path"]
    contract_definition = compile_starknet_files([source_path], debug_info=True)

    address = await starknet.deploy(contract_definition=contract_definition)
    address2contract[address] = StarknetContract(
        starknet=starknet,
        abi=contract_definition.abi,
        contract_address=address
    )

    # TODO hex address
    return jsonify({ "address": address, "abi": contract_definition.abi })

@app.route("/invoke", methods=["POST"])
async def invoke():
    return await invoke_or_call("invoke", request)

@app.route("/call", methods=["POST"])
async def call():
    return await invoke_or_call("call", request)

async def invoke_or_call(choice, request):
    content = request.get_json()
    address = content["address"]
    contract = address2contract[address]

    method_name = content["method_name"]
    method = getattr(contract, method_name)

    kwargs = content.get("kwargs")
    prepared = method(**kwargs) if kwargs else method()
    finish_me = getattr(prepared, choice)
    ret = await finish_me()
    return jsonify(ret)

if __name__ == "__main__":
    app.run()
