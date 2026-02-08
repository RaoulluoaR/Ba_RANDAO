import requests
import time
import subprocess
import random
from datetime import datetime, timezone

# =========================
# CONFIG
# =========================

BEACON_API = "http://127.0.0.1:32788"
ENCLAVE = "my-testnet"

SLOTS_PER_EPOCH = 32
SECONDS_PER_SLOT = 12

ATTACK_EPOCHS = 5          # wie viele Epochen angreifen
ATTACK_PROBABILITY = 0.10  # ~10% der Slots angreifen
STOP_OFFSET = 3            # Sekunden vor Slot-Beginn VC stoppen

# =========================
# BEACON API HELPERS
# =========================

def get_head_slot():
    try:
        r = requests.get(f"{BEACON_API}/eth/v1/beacon/headers/head", timeout=5)
        r.raise_for_status()
        return int(r.json()["data"]["header"]["message"]["slot"])
    except Exception as e:
        print(f"Error getting head slot: {e}")
        return None

def get_genesis_time():
    try:
        r = requests.get(f"{BEACON_API}/eth/v1/beacon/genesis", timeout=5)
        r.raise_for_status()
        return int(r.json()["data"]["genesis_time"])
    except Exception as e:
        print(f"Error getting genesis time: {e}")
        return None

def get_proposer_for_slot(slot):
    try:
        epoch = slot // SLOTS_PER_EPOCH
        r = requests.get(
            f"{BEACON_API}/eth/v1/validator/duties/proposer/{epoch}",
            timeout=5,
        )
        r.raise_for_status()
        
        data = r.json()["data"]
        # Finde den Proposer für den spezifischen Slot
        # ACHTUNG: Die API-Struktur kann je nach Client variieren
        for duty in data:
            if "slot" in duty and duty["slot"] == str(slot):
                return int(duty["validator_index"])
        
        # Fallback: ersten Validator nehmen (vereinfacht)
        if data:
            return int(data[0]["validator_index"])
            
        return None
    except Exception as e:
        print(f"Error getting proposer for slot {slot}: {e}")
        return None

# =========================
# VALIDATOR → VC MAPPING
# =========================

def validator_to_vc(index):
    if index is None:
        return None
        
    if 0 <= index <= 127:
        return "vc-1-geth-lighthouse"
    elif 128 <= index <= 255:
        return "vc-2-nethermind-prysm"
    elif 256 <= index <= 383:
        return "vc-3-besu-teku"
    elif 384 <= index <= 511:
        return "vc-4-erigon-lodestar"
    else:
        print(f"Warning: Unknown validator index {index}")
        return None

# =========================
# KURTOSIS CONTROL
# =========================

def stop_vc(vc):
    if vc is None:
        return False
        
    print(f"Stopping {vc}")
    try:
        result = subprocess.run(
            ["kurtosis", "service", "stop", ENCLAVE, vc],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            print(f"Error stopping {vc}: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Exception stopping {vc}: {e}")
        return False

def start_vc(vc):
    if vc is None:
        return False
        
    print(f"Starting {vc}")
    try:
        result = subprocess.run(
            ["kurtosis", "service", "start", ENCLAVE, vc],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            print(f"Error starting {vc}: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Exception starting {vc}: {e}")
        return False

# =========================
# TIMING
# =========================

def slot_start_time(slot, genesis_time):
    return genesis_time + slot * SECONDS_PER_SLOT

def sleep_until(ts):
    now = time.time()
    if ts > now:
        time.sleep(max(0.1, ts - now))

# =========================
# MAIN ATTACK LOOP
# =========================

def run_last_revealer_attack():
    print("Starting last-revealer attack simulation")
    
    # Initiale Daten abrufen
    genesis_time = get_genesis_time()
    if genesis_time is None:
        print("Failed to get genesis time. Exiting.")
        return
        
    start_slot = get_head_slot()
    if start_slot is None:
        print("Failed to get head slot. Exiting.")
        return
        
    print(f"Genesis time: {genesis_time}")
    print(f"Current slot: {start_slot}")
    
    end_slot = start_slot + ATTACK_EPOCHS * SLOTS_PER_EPOCH
    print(f"Attack will run from slot {start_slot} to {end_slot}")
    
    for slot in range(start_slot + 1, end_slot + 1):
        # Probabilistische Auswahl (korrigiert)
        if random.random() > ATTACK_PROBABILITY:
            # print(f"Slot {slot}: Skipped (probability)")
            continue
            
        # Proposer für diesen Slot ermitteln
        proposer = get_proposer_for_slot(slot)
        if proposer is None:
            print(f"Slot {slot}: No proposer found. Skipping.")
            continue
            
        vc = validator_to_vc(proposer)
        if vc is None:
            print(f"Slot {slot}: No VC mapping for validator {proposer}. Skipping.")
            continue
            
        slot_ts = slot_start_time(slot, genesis_time)
        current_time = time.time()
        
        # Prüfen ob Slot in der Zukunft liegt
        if slot_ts < current_time:
            print(f"Slot {slot}: Already passed. Skipping.")
            continue
            
        print(
            f"\n[ATTACK] Slot {slot} | Proposer {proposer} | {vc} | "
            f"Time: {datetime.fromtimestamp(slot_ts, tz=timezone.utc).strftime('%H:%M:%S')}"
        )
        
        # 1. Warten bis kurz vor Slot (mit STOP_OFFSET Sekunden Puffer)
        wait_until = slot_ts - STOP_OFFSET
        if wait_until > current_time:
            print(f"  Waiting until {STOP_OFFSET}s before slot...")
            sleep_until(wait_until)
        
        # 2. VC stoppen
        if not stop_vc(vc):
            print(f"  Failed to stop {vc}. Continuing anyway...")
        
        # 3. Slot abwarten (Block wird nicht produziert)
        print(f"  Letting slot {slot} pass without block...")
        sleep_until(slot_ts + SECONDS_PER_SLOT)
        
        # 4. VC wieder starten
        if not start_vc(vc):
            print(f"  Warning: Failed to restart {vc}")
        
        print(f"  Attack on slot {slot} completed")
        
        # Kurze Pause zwischen Angriffen
        time.sleep(1)
    
    print("\nAttack simulation finished")

# =========================
# ENTRYPOINT
# =========================

if __name__ == "__main__":
    run_last_revealer_attack()
