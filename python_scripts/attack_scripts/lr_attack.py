import requests
import time
import subprocess
import json

# =========================
# CONFIG
# =========================

BEACON_API = "http://127.0.0.1:32794"
ENCLAVE = "my-testnet"
NumberOfAttacks = 400
PauseBetweenAttacks = 0
ChanceOfAttack = 1

# =========================
# get functions and helper functions
# =========================

def get_head_slot():                  #get current slot number
    r = requests.get(f"{BEACON_API}/eth/v1/beacon/headers/head", timeout=5)
    r.raise_for_status()
    return int(r.json()["data"]["header"]["message"]["slot"])

def get_last_proposer_of_epoch(epoch):
    r = requests.get(f"{BEACON_API}/eth/v1/validator/duties/proposer/{epoch}")
    r.raise_for_status()              #check if api reachable
    j = r.json()
    print("\n Plan on Attacking Validator ", j["data"][-1]["validator_index"], " at Slot ", j["data"][-1]["slot"])
    return [int(j["data"][-1]["validator_index"]), int(j["data"][-1]["slot"])]   #return validator ID and last slot of epoch
   
def get_validator_client(index):
    if not (0 <= index <= 191):
        raise ValueError(f"Unknown validator index {index}")

    if index < 128:
        return None
    elif index < 144:
        return "cl-2-lighthouse-geth"
    elif index < 160:
        return "cl-3-lighthouse-nethermind"
    elif index < 176:
        return "cl-4-prysm-geth"
    else:
        return "cl-5-prysm-nethermind"
    
def stop_client(cl):
    print(f"Stopping {cl}")

    if cl is None:
        print("targeted super node")
        return

    subprocess.run(["kurtosis", "service", "stop", ENCLAVE, cl])

def start_client(cl):
    print(f"Starting {cl}")

    if cl is None:
        print("targeted super node, didnt get stopped")
        return

    subprocess.run(["kurtosis", "service", "start", ENCLAVE, cl])
    
# =========================
# last revealer attack
# =========================

def last_revealer_attack():           #start the attack
    while True:
        currSlot = get_head_slot()
        print(f"waiting for new epoch to start... Slot is currently Slot {currSlot}")

        if currSlot % 32 == 0:
            print("\nnew epoch startet")
            break
        time.sleep(1)

    currEpoch = currSlot // 32
    print(f"\nAttacking last slot of epoch {currEpoch}")

    valIndLastSlot = get_last_proposer_of_epoch(currEpoch)
    valInd = valIndLastSlot[0]
    lastSlot = valIndLastSlot[1]
    
    if lastSlot != currSlot + 31:
        raise Exception("currSlot was not the first slot!")
    
    cl = get_validator_client(valInd)
    while True:
        print(f"\nwaiting to stop client {cl}...")
        currSlot = get_head_slot()

        if currSlot == lastSlot - 1:
            print(f"\ninitiate stopping at slot {currSlot}")
            break
        time.sleep(2)
    
    time.sleep(6)   #give time for the pre to last slot to get proposed

    if lastSlot != currSlot + 1:
        raise Exception("currSlot is not pre to last slot in epoch!")

    print(f"\nstopping client {cl} for 24 seconds at slot {currSlot} of {currEpoch}")
    stop_client(cl)
    time.sleep(24)

    currSlot = get_head_slot()
    currEpoch = currSlot // 32
    print(f"\nstarting client {cl} at slot {currSlot} of {currEpoch}")
    start_client(cl)

# =========================
# main
# =========================

def config_attack():      #while loop for repeating attacks, and prob. for chanche of attacks
    print(f"starting {NumberOfAttacks} Attacks with {PauseBetweenAttacks} epochs inbetween")

    AttackNumber = 0
    while AttackNumber < NumberOfAttacks:
        print(f"\nstarting attack number {AttackNumber}")
        last_revealer_attack()
        AttackNumber += 1
        time.sleep(PauseBetweenAttacks * 60)

    print("\nAttackscript finished")

if __name__ == "__main__":
     config_attack()     




#zu beginn von epoche ablesen welche clients validatoren sein werden
#validtoren sind cliets zugewiesen, immer fest verteilt
#clients mit kurtosis befehl stoppen und starten
#(Nie im selben Slot stoppen UND starten)

'''''
fragt nach aktueller epoche x

frage validator IDs für epoche x+1 im ersten Slot der Epoche +1 ab.

finde den client y der den validator beinhaltet der slot 32 den block proposen soll 
(feste verteilung zum beispiel geth light house validatoren 130-250)

stoppe zu beginn von slot 31 client y

starte client y 24 sekunden (zwei slot dauern) später erneut

'''''
