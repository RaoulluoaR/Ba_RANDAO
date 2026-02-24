import requests
import time
import subprocess
import random

# =========================
# CONFIG
# =========================

BEACON_API = "http://127.0.0.1:34103"
ENCLAVE = "my-testnet"

NumberOfAttacks = 300
PauseBetweenAttacks = 0        # in minutes
NumberOfSlotsToAttack = 192      # how many slots per epoch to attack

SLOTS_PER_EPOCH = 32


# =========================
# Helper Functions
# =========================

def get_head_slot():
    r = requests.get(f"{BEACON_API}/eth/v1/beacon/headers/head", timeout=5)
    r.raise_for_status()
    return int(r.json()["data"]["header"]["message"]["slot"])


def get_proposer_duties(epoch):
    r = requests.get(f"{BEACON_API}/eth/v1/validator/duties/proposer/{epoch}")
    r.raise_for_status()
    return r.json()["data"]


# =========================
# VALIDATOR CLIENT MAPPING
# (adjust ranges to your setup)
# =========================

def get_validator_client(index):

    # Supernode (ignored)
    if 0 <= index < 128:
        return None

    # Example distribution
    if 128 <= index < 144:
        return "cl-2-lighthouse-geth"
    elif 144 <= index < 160:
        return "cl-3-lighthouse-nethermind"
    elif 160 <= index < 176:
        return "cl-4-prysm-geth"
    elif 176 <= index < 192:
        return "cl-5-prysm-nethermind"
    else:
        return None


# =========================
# Client Control
# =========================

def stop_client(cl):
    if cl is None:
        return
    print(f"Stopping {cl}")
    subprocess.run(["kurtosis", "service", "stop", ENCLAVE, cl])


def start_client(cl):
    if cl is None:
        return
    print(f"Starting {cl}")
    subprocess.run(["kurtosis", "service", "start", ENCLAVE, cl])


# =========================
# Build Attack List
# =========================

def build_attack_list(epoch):

    duties = get_proposer_duties(epoch)
    attack_list = []

    for duty in duties:
        validator_index = int(duty["validator_index"])
        slot = int(duty["slot"])

        cl = get_validator_client(validator_index)

        if cl is None:
            continue

        attack_list.append([cl, validator_index, slot])

    print("\nAttack candidates:")
    for entry in attack_list:
        print(entry)

    return attack_list


# =========================
# Attack Logic
# =========================

def attack_selected_slots(attack_list):

    if not attack_list:
        print("No attackable slots found.")
        return

    selected = random.sample(
        attack_list,
        min(NumberOfSlotsToAttack, len(attack_list))
    )

    selected.sort(key=lambda x: x[2])

    print("\nSelected slots for attack:")
    for s in selected:
        print(s)

    for cl, validator_index, slot in selected:

        print(f"\nWaiting to attack validator {validator_index} at slot {slot}")

        # Wait for slot-1
        while True:
            curr_slot = get_head_slot()
            print(f"curr slot is {curr_slot}, waiting for Slot {slot}")

            if curr_slot >= slot - 1:
                print(f"Stopping {cl} at slot {curr_slot}")
                stop_client(cl)
                break

            time.sleep(0.5)

        # Wait two slots (~24s)
        target_restart_slot = slot + 1

        while True:
            curr_slot = get_head_slot()
            if curr_slot >= target_restart_slot:
                break
            time.sleep(0.5)


        print(f"Restarting {cl}")
        start_client(cl)


# =========================
# Epoch Attack
# =========================

def epoch_attack():

    # Wait until new epoch starts
    while True:
        curr_slot = get_head_slot()
        if curr_slot % SLOTS_PER_EPOCH == 0:
            break
        time.sleep(1)

    current_epoch = curr_slot // SLOTS_PER_EPOCH
    target_epoch = current_epoch + 1

    print(f"\nCurrent epoch: {current_epoch}")
    print(f"Target epoch: {target_epoch}")

    attack_list = build_attack_list(target_epoch)
    attack_selected_slots(attack_list)


# =========================
# Main Loop
# =========================

def config_attack():

    print(f"Starting {NumberOfAttacks} attack rounds")

    attack_number = 0

    while attack_number < NumberOfAttacks:
        print(f"\n=== Attack Round {attack_number} ===")
        epoch_attack()
        attack_number += 1
        time.sleep(PauseBetweenAttacks * 60)

    print("\nAttack script finished.")


if __name__ == "__main__":
    config_attack()

