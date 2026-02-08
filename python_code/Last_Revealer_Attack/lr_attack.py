import requests
import time
import subprocess
import json

# =========================
# CONFIG
# =========================

BEACON_API = "http://127.0.0.1:32788"
ENCLAVE = "my-testnet"
NumberOfAttacks = 1
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
    r = requests.get(
        f"{BEACON_API}/eth/v1/validator/duties/proposer/{epoch}",
        params={"epoch": epoch},
        timeout=5)
    r.raise_for_status()              #check if api reachable
    j = json.loads(r)
    print("\n Plan on Attacking Validator ", j["data"][-1]["validator_index"], " at Slot ", j["data"][-1]["slot"])
    return [int(j["data"][-1]["validator_index"]), int(j["data"][-1]["Slot"])]   #return validator ID and last slot of epoch
   
def get_validator_client(index):      #check one time for testnet, always stable distribution
    if 0 <= index <= 127:
        return "vc-1-geth-lighthouse"
    elif 128 <= index <= 255:
        return "vc-2-nethermind-prysm"
    elif 256 <= index <= 383:
        return "vc-3-besu-teku"
    elif 384 <= index <= 511:
        return "vc-4-erigon-lodestar"
    else:
        raise ValueError(f"Unknown validator index {index}")
    
def stop_client(cl):
    print(f"Stopping {cl}")
    subprocess.run(["kurtosis", "service", "stop", ENCLAVE, cl])

def start_client(cl):
    print(f"Starting {cl}")
    subprocess.run(["kurtosis", "service", "start", ENCLAVE, cl])
    
# =========================
# last revealer attack
# =========================

def last_revealer_attack():           #start the attack
    while True:
        print("waiting for new epoch to start...")
        currSlot = get_head_slot()

        if currSlot // 32 == 0:
            print("\nnew epoch startet")
            break
        time.sleep(2)

    currEpoch = currSlot / 32
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
    currEpoch = currSlot / 32
    print(f"\nstarting client {cl} at slot {currSlot} of {currEpoch}")

# =========================
# main
# =========================

def config_attack():      #while loop for repeating attacks, and prob. for chanche of attacks
    print(f"starting {NumberOfAttacks} Attacks with {PauseBetweenAttacks} epochs inbetween")

    AttackNumber = 0
    while AttackNumber <= NumberOfAttacks:
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
