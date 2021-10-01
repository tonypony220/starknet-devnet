import requests
from os import environ

artifact_path = environ["ARTIFACT_PATH"]

deployed = requests.post("http://localhost:5000/deploy", {"path": artifact_path})
address = deployed.json()["address"]
print("address:", hex(address))

invoked = requests.post("http://localhost:5000/invoke", json={
    "address": address,
    "method_name": "increase_balance",
    "kwargs": { "amount1": 10, "amount2": 20 } 
})
print("invoked")

called = requests.post("http://localhost:5000/call", json={
    "address": address,
    "method_name": "get_balance" 
})
print("called")

print(called.json())
