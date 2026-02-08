import requests
import time
import subprocess
import random
import re
from datetime import datetime, timezone

# =========================
# CONFIG
# =========================

BEACON_API = "http://127.0.0.1:32788"
ENCLAVE = "my-testnet"

SLOTS_PER_EPOCH = 32
SECONDS_PER_SLOT = 12

ATTACK_EPOCHS = 5
ATTACK_PROBABILITY = 0.10
STOP_OFFSET = 3
OFFLINE_SLOTS = 3

# =========================
# HARDCODED SERVICE LIST BASED ON YOUR ENCLAVE
# =========================

# Basierend auf Ihrer Ausgabe:
AVAILABLE_VC_SERVICES = [
    "vc-1-geth-lighthouse",    # Validatoren 0-127
    "vc-2-nethermind-prysm",   # Validatoren 128-255  
    "vc-4-erigon-lodestar",    # Validatoren 384-511
    # vc-3-besu-teku fehlt! (Validatoren 256-383)
]

def validator_to_vc(index):
    """Hardcoded mapping basierend auf verfügbaren Services"""
    if index is None:
        return None
    
    if 0 <= index <= 127:
        return "vc-1-geth-lighthouse"
    elif 128 <= index <= 255:
        return "vc-2-nethermind-prysm"
    elif 384 <= index <= 511:  # vc-3-besu-teku fehlt, daher überspringen wir 256-383
        return "vc-4-erigon-lodestar"
    else:
        return None

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
    """Get the proposer validator index for a specific slot"""
    try:
        epoch = slot // SLOTS_PER_EPOCH
        r = requests.get(
            f"{BEACON_API}/eth/v1/validator/duties/proposer/{epoch}",
            timeout=5
        )
        r.raise_for_status()
        
        data = r.json()["data"]
        
        for duty in data:
            if int(duty["slot"]) == slot:
                return int(duty["validator_index"])
        
        print(f"WARNING: No proposer found for slot {slot} in epoch {epoch}")
        return None
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            # Epoche könnte noch nicht verfügbar sein
            print(f"Slot {slot}: Epoch {epoch} not available yet, skipping...")
            return None
        else:
            print(f"HTTP Error getting proposer for slot {slot}: {e}")
            return None
    except Exception as e:
        print(f"Error getting proposer for slot {slot}: {e}")
        return None

# =========================
# KURTOSIS FUNKTIONEN
# =========================

def service_exists(vc):
    """Check if a service exists in the enclave"""
    return vc in AVAILABLE_VC_SERVICES

def stop_vc(vc):
    if vc is None:
        print("  ERROR: VC name is None")
        return False
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Stopping {vc}")
    
    try:
        result = subprocess.run(
            ["kurtosis", "service", "stop", ENCLAVE, vc],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"  ✅ Successfully stopped {vc}")
            return True
        else:
            print(f"  ERROR stopping {vc}: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT stopping {vc}")
        return False
    except Exception as e:
        print(f"  EXCEPTION stopping {vc}: {e}")
        return False

def start_vc(vc):
    if vc is None:
        print("  ERROR: VC name is None")
        return False
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting {vc}")
    
    try:
        result = subprocess.run(
            ["kurtosis", "service", "start", ENCLAVE, vc],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"  ✅ Successfully started {vc}")
            return True
        else:
            print(f"  ERROR starting {vc}: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT starting {vc}")
        return False
    except Exception as e:
        print(f"  EXCEPTION starting {vc}: {e}")
        return False

def check_service_status(vc):
    """Check status of a service"""
    try:
        result = subprocess.run(
            ["kurtosis", "service", "status", ENCLAVE, vc],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"ERROR: {result.stderr[:100]}"
            
    except Exception as e:
        return f"EXCEPTION: {e}"

# =========================
# ATTACK FUNKTION
# =========================

def run_last_revealer_attack():
    """Last-Revealer Attack basierend auf verfügbaren Services"""
    print("Starting last-revealer attack")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    
    print(f"\n=== AVAILABLE VC SERVICES ===")
    for vc in AVAILABLE_VC_SERVICES:
        status = check_service_status(vc)
        print(f"  {vc}: {status}")
    
    # Initiale Daten abrufen
    genesis_time = get_genesis_time()
    if genesis_time is None:
        print("Failed to get genesis time. Exiting.")
        return
        
    start_slot = get_head_slot()
    if start_slot is None:
        print("Failed to get head slot. Exiting.")
        return
    
    end_slot = start_slot + ATTACK_EPOCHS * SLOTS_PER_EPOCH
    
    print(f"\n=== ATTACK PARAMETERS ===")
    print(f"Genesis time: {genesis_time}")
    print(f"Current slot: {start_slot}")
    print(f"Attack until slot: {end_slot}")
    print(f"Attack probability: {ATTACK_PROBABILITY*100}%")
    print(f"Offline slots: {OFFLINE_SLOTS}")
    
    attack_count = 0
    skipped_count = 0
    successful_attacks = 0
    
    for slot in range(start_slot + 1, end_slot + 1):
        # Probabilistische Auswahl
        if random.random() > ATTACK_PROBABILITY:
            continue
            
        # Proposer für diesen Slot ermitteln
        proposer = get_proposer_for_slot(slot)
        if proposer is None:
            skipped_count += 1
            continue
        
        # VC Mapping
        vc = validator_to_vc(proposer)
        if vc is None:
            # Validator gehört zu vc-3-besu-teku das fehlt
            skipped_count += 1
            continue
        
        slot_ts = genesis_time + slot * SECONDS_PER_SLOT
        current_time = time.time()
        
        # Prüfen ob Slot in der Zukunft liegt
        if slot_ts < current_time:
            skipped_count += 1
            continue
        
        attack_count += 1
        
        print(f"\n{'='*60}")
        print(f"[ATTACK #{attack_count}] Slot {slot} | Proposer {proposer} | {vc}")
        print(f"  Slot time: {datetime.fromtimestamp(slot_ts, tz=timezone.utc).strftime('%H:%M:%S')}")
        print(f"  Current: {datetime.fromtimestamp(current_time, tz=timezone.utc).strftime('%H:%M:%S')}")
        print(f"  Time until slot: {slot_ts - current_time:.1f}s")
        
        try:
            # Warten bis STOP_OFFSET Sekunden vor Slot
            stop_time = slot_ts - STOP_OFFSET
            if stop_time > current_time:
                wait_time = stop_time - current_time
                print(f"  Waiting {wait_time:.1f}s until stop...")
                if wait_time > 0:
                    time.sleep(wait_time)
            
            # VC stoppen
            print(f"  Stopping {vc}...")
            if not stop_vc(vc):
                print(f"  ❌ Failed to stop {vc}")
                continue
            
            # Warten während der Validator offline ist
            resume_time = slot_ts + OFFLINE_SLOTS * SECONDS_PER_SLOT
            offline_duration = OFFLINE_SLOTS * SECONDS_PER_SLOT
            print(f"  Keeping {vc} offline for {offline_duration}s...")
            time.sleep(offline_duration)
            
            # VC wieder starten
            print(f"  Starting {vc}...")
            if start_vc(vc):
                successful_attacks += 1
                print(f"  ✅ Attack successful")
            else:
                print(f"  ⚠️  Attack completed but restart had issues")
            
        except Exception as e:
            print(f"  ❌ Error during attack: {e}")
        
        print(f"{'='*60}")
        
        # Kurze Pause zwischen Angriffen
        time.sleep(1)
    
    print(f"\n{'='*60}")
    print("Attack simulation finished")
    print(f"Total attacks attempted: {attack_count}")
    print(f"Successful attacks: {successful_attacks}")
    print(f"Total slots skipped: {skipped_count}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

# =========================
# DIAGNOSE FUNKTIONEN
# =========================

def check_chain_status():
    """Check current chain status"""
    print(f"\n=== CHECKING CHAIN STATUS ===")
    
    try:
        # Beacon Chain
        r = requests.get(f"{BEACON_API}/eth/v1/beacon/headers/head", timeout=5)
        beacon_head = int(r.json()["data"]["header"]["message"]["slot"])
        
        print(f"Beacon Chain Head Slot: {beacon_head}")
        
        # Versuche Execution Block
        try:
            r = requests.get(f"{BEACON_API}/eth/v1/beacon/blocks/head", timeout=5)
            execution_block = r.json()["data"]["message"]["body"]["execution_payload"]["block_number"]
            print(f"Execution Block: {execution_block}")
            print(f"Difference: {beacon_head - int(execution_block)} slots")
        except:
            print("Execution block info not available")
        
    except Exception as e:
        print(f"Error checking chain status: {e}")

def check_validator_status(validator_index):
    """Check status of a specific validator"""
    print(f"\n=== CHECKING VALIDATOR {validator_index} ===")
    
    try:
        r = requests.get(
            f"{BEACON_API}/eth/v1/beacon/states/head/validators/{validator_index}",
            timeout=5
        )
        
        if r.status_code == 200:
            data = r.json()["data"]
            print(f"Status: {data['status']}")
            print(f"Balance: {int(data['balance']) / 1e9:.4f} ETH")
            
            # Welcher VC?
            vc = validator_to_vc(validator_index)
            if vc:
                print(f"VC Service: {vc}")
            else:
                print(f"VC Service: Not available (missing vc-3-besu-teku?)")
                
        elif r.status_code == 404:
            print(f"Validator {validator_index} not found")
        else:
            print(f"API Error: {r.status_code}")
            
    except Exception as e:
        print(f"Error checking validator: {e}")

def test_specific_attack():
    """Test attack on a specific validator"""
    print("\n=== TEST SPECIFIC ATTACK ===")
    
    try:
        validator_index = int(input("Enter validator index to attack: "))
        
        vc = validator_to_vc(validator_index)
        if vc is None:
            print(f"Validator {validator_index} cannot be attacked (vc-3-besu-teku missing)")
            return
        
        print(f"\nTarget: Validator {validator_index} -> {vc}")
        
        # Check current status
        print("\nCurrent status:")
        status = check_service_status(vc)
        print(f"{vc}: {status}")
        
        # Get next proposer slot
        current_slot = get_head_slot()
        if current_slot is None:
            return
        
        # Find next slot where this validator is proposer
        print(f"\nLooking for next slot where validator {validator_index} is proposer...")
        
        for lookahead in range(1, 33):  # Check next 32 slots
            test_slot = current_slot + lookahead
            proposer = get_proposer_for_slot(test_slot)
            
            if proposer == validator_index:
                print(f"✅ Found! Slot {test_slot}")
                
                genesis_time = get_genesis_time()
                if genesis_time is None:
                    return
                
                slot_ts = genesis_time + test_slot * SECONDS_PER_SLOT
                current_time = time.time()
                
                print(f"\nAttack plan:")
                print(f"  Slot: {test_slot}")
                print(f"  Time: {datetime.fromtimestamp(slot_ts, tz=timezone.utc).strftime('%H:%M:%S')}")
                print(f"  VC to stop: {vc}")
                print(f"  Wait time: {slot_ts - current_time:.1f}s")
                
                confirm = input("\nExecute attack? (y/n): ")
                if confirm.lower() == 'y':
                    execute_single_attack(test_slot, validator_index, vc, genesis_time)
                return
        
        print(f"No proposer slot found for validator {validator_index} in next 32 slots")
        
    except ValueError:
        print("Invalid validator index")
    except Exception as e:
        print(f"Error: {e}")

def execute_single_attack(slot, validator_index, vc, genesis_time):
    """Execute a single attack"""
    slot_ts = genesis_time + slot * SECONDS_PER_SLOT
    current_time = time.time()
    
    print(f"\nExecuting attack on slot {slot}...")
    
    # Warten bis STOP_OFFSET Sekunden vor Slot
    stop_time = slot_ts - STOP_OFFSET
    if stop_time > current_time:
        wait_time = stop_time - current_time
        print(f"Waiting {wait_time:.1f}s until stop...")
        time.sleep(wait_time)
    
    # VC stoppen
    print(f"Stopping {vc}...")
    if not stop_vc(vc):
        print(f"Failed to stop {vc}")
        return
    
    # Warten während der Validator offline ist
    print(f"Keeping {vc} offline for {OFFLINE_SLOTS} slots...")
    time.sleep(OFFLINE_SLOTS * SECONDS_PER_SLOT)
    
    # VC wieder starten
    print(f"Starting {vc}...")
    start_vc(vc)
    
    print(f"\n✅ Attack on validator {validator_index} completed")

# =========================
# ENTRYPOINT
# =========================

if __name__ == "__main__":
    print(f"{'='*60}")
    print("LAST-REVEALER ATTACK SCRIPT")
    print(f"Available VC Services: {', '.join(AVAILABLE_VC_SERVICES)}")
    print(f"{'='*60}")
    
    # Menü
    print("\nSelect mode:")
    print("1. Run full attack simulation")
    print("2. Test attack on specific validator")
    print("3. Check chain status")
    print("4. Check validator status")
    print("5. List all services")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    if choice == "1":
        run_last_revealer_attack()
    elif choice == "2":
        test_specific_attack()
    elif choice == "3":
        check_chain_status()
    elif choice == "4":
        try:
            idx = int(input("Enter validator index: "))
            check_validator_status(idx)
        except:
            print("Invalid input")
    elif choice == "5":
        print(f"\nAvailable VC Services:")
        for vc in AVAILABLE_VC_SERVICES:
            print(f"  - {vc}")
        print("\nMissing: vc-3-besu-teku (validators 256-383 will be skipped)")
    else:
        print("Invalid choice. Running full attack simulation...")
        run_last_revealer_attack()