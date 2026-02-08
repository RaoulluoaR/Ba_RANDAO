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
    r = requests.get(f"{BEACON_API}/eth/v1/validator/duties/proposer/{epoch}")
    r.raise_for_status()              #check if api reachable
    j = r.json()
    print("\n Plan on Attacking Validator ", j["data"][-1]["validator_index"], " at Slot ", j["data"][-1]["slot"])
    return [int(j["data"][-1]["validator_index"]), int(j["data"][-1]["slot"])]   #return validator ID and last slot of epoch
   
def get_validator_client(index):
    # ==================================================
    # Geth + Lighthouse (glh-01 .. glh-08) → 0–127
    # ==================================================
    if 0 <= index <= 15:
        return "vc-glh-01"
    elif 16 <= index <= 31:
        return "vc-glh-02"
    elif 32 <= index <= 47:
        return "vc-glh-03"
    elif 48 <= index <= 63:
        return "vc-glh-04"
    elif 64 <= index <= 79:
        return "vc-glh-05"
    elif 80 <= index <= 95:
        return "vc-glh-06"
    elif 96 <= index <= 111:
        return "vc-glh-07"
    elif 112 <= index <= 127:
        return "vc-glh-08"

    # ==================================================
    # Nethermind + Lighthouse (nmlh-01 .. nmlh-08) → 128–255
    # ==================================================
    elif 128 <= index <= 143:
        return "vc-nmlh-01"
    elif 144 <= index <= 159:
        return "vc-nmlh-02"
    elif 160 <= index <= 175:
        return "vc-nmlh-03"
    elif 176 <= index <= 191:
        return "vc-nmlh-04"
    elif 192 <= index <= 207:
        return "vc-nmlh-05"
    elif 208 <= index <= 223:
        return "vc-nmlh-06"
    elif 224 <= index <= 239:
        return "vc-nmlh-07"
    elif 240 <= index <= 255:
        return "vc-nmlh-08"

    # ==================================================
    # Geth + Prysm (gp-01 .. gp-08) → 256–383
    # ==================================================
    elif 256 <= index <= 271:
        return "vc-gp-01"
    elif 272 <= index <= 287:
        return "vc-gp-02"
    elif 288 <= index <= 303:
        return "vc-gp-03"
    elif 304 <= index <= 319:
        return "vc-gp-04"
    elif 320 <= index <= 335:
        return "vc-gp-05"
    elif 336 <= index <= 351:
        return "vc-gp-06"
    elif 352 <= index <= 367:
        return "vc-gp-07"
    elif 368 <= index <= 383:
        return "vc-gp-08"

    # ==================================================
    # Nethermind + Prysm (nmp-01 .. nmp-08) → 384–511
    # ==================================================
    elif 384 <= index <= 399:
        return "vc-nmp-01"
    elif 400 <= index <= 415:
        return "vc-nmp-02"
    elif 416 <= index <= 431:
        return "vc-nmp-03"
    elif 432 <= index <= 447:
        return "vc-nmp-04"
    elif 448 <= index <= 463:
        return "vc-nmp-05"
    elif 464 <= index <= 479:
        return "vc-nmp-06"
    elif 480 <= index <= 495:
        return "vc-nmp-07"
    elif 496 <= index <= 511:
        return "vc-nmp-08"

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
