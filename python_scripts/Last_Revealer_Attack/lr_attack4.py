import requests
import time
import subprocess
import random
import json
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

AVAILABLE_VC_SERVICES = [
    "vc-1-geth-lighthouse",
    "vc-2-nethermind-prysm", 
    "vc-4-erigon-lodestar",
]

def validator_to_vc(index):
    """Hardcoded mapping basierend auf verfügbaren Services"""
    if index is None:
        return None
    
    if 0 <= index <= 127:
        return "vc-1-geth-lighthouse"
    elif 128 <= index <= 255:
        return "vc-2-nethermind-prysm"
    elif 384 <= index <= 511:
        return "vc-4-erigon-lodestar"
    else:
        return None

# =========================
# VERBESSERTE SERVICE STATUS FUNKTION
# =========================

def get_service_status(vc):
    """Get detailed service status from kurtosis"""
    try:
        # 1. Versuche mit 'kurtosis service inspect' für detaillierte Info
        result = subprocess.run(
            ["kurtosis", "service", "inspect", ENCLAVE, vc],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            output = result.stdout
            
            # Extrahiere Status aus der Ausgabe
            for line in output.split('\n'):
                if "Status:" in line:
                    status = line.split("Status:")[1].strip()
                    return f"{status}"
            
            # Falls Status nicht gefunden, prüfe auf RUNNING/STOPPED
            if "RUNNING" in output:
                return "RUNNING"
            elif "STOPPED" in output:
                return "STOPPED"
            else:
                return "INSPECTED (no clear status)"
        
        # 2. Fallback: Verwende 'kurtosis service ls' mit besserem Parsing
        result = subprocess.run(
            ["kurtosis", "service", "ls", ENCLAVE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            service_found = False
            
            for line in lines:
                if vc in line:
                    service_found = True
                    
                    # Extrahiere Status
                    line_lower = line.lower()
                    if "running" in line_lower:
                        # Versuche Port-Info zu extrahieren
                        if "ports:" in line_lower:
                            return "RUNNING (with ports)"
                        return "RUNNING"
                    elif "stopped" in line_lower:
                        return "STOPPED"
                    elif "starting" in line_lower:
                        return "STARTING"
                    elif "stopping" in line_lower:
                        return "STOPPING"
                    elif "error" in line_lower:
                        return "ERROR"
                    elif "not_found" in line_lower:
                        return "NOT_FOUND"
                    else:
                        return f"FOUND: {line[:50]}..."
            
            if not service_found:
                return "NOT_IN_LIST"
            else:
                return "FOUND (status unknown)"
        else:
            return f"LS_ERROR: {result.stderr[:50]}"
            
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"EXCEPTION: {str(e)[:50]}"

def get_detailed_service_info():
    """Get detailed information about all services"""
    print(f"\n{'='*60}")
    print("DETAILED SERVICE INFORMATION")
    print(f"{'='*60}")
    
    for vc in AVAILABLE_VC_SERVICES:
        print(f"\n{vc}:")
        
        # 1. Basic status
        status = get_service_status(vc)
        print(f"  Status: {status}")
        
        # 2. Try to get logs (last 1 line)
        try:
            result = subprocess.run(
                ["kurtosis", "service", "logs", ENCLAVE, vc, "--tail", "1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3
            )
            
            if result.returncode == 0 and result.stdout.strip():
                log_line = result.stdout.strip().split('\n')[-1]
                print(f"  Last log: {log_line[:80]}...")
            elif result.stderr:
                if "No logs" in result.stderr or "does not contains any logs" in result.stderr:
                    print(f"  Logs: No logs available (service may be stopped)")
                else:
                    print(f"  Log error: {result.stderr[:50]}...")
        except:
            print(f"  Logs: Unable to retrieve")
        
        # 3. Try to check if service responds
        if "RUNNING" in status:
            print(f"  Health: Presumably healthy")
        else:
            print(f"  Health: May need attention")

# =========================
# ERWEITERTE VERIFIKATIONS FUNKTIONEN
# =========================

def verify_no_block_produced(slot):
    """Überprüfe ob wirklich KEIN Block für diesen Slot produziert wurde"""
    print(f"\n[BLOCK VERIFICATION] Checking if any block was produced at slot {slot}...")
    
    try:
        # 1. Prüfe ob ein Block für diesen Slot existiert
        r = requests.get(
            f"{BEACON_API}/eth/v2/beacon/blocks/{slot}",
            timeout=5
        )
        
        if r.status_code == 200:
            # Block existiert - Angriff fehlgeschlagen
            block_data = r.json()
            proposer = int(block_data["data"]["message"]["proposer_index"])
            block_hash = block_data["data"]["message"]["body"]["execution_payload"]["block_hash"][:20]
            
            print(f"  ❌ BLOCK EXISTS: Slot {slot} has block")
            print(f"     Proposer: {proposer}")
            print(f"     Block hash: 0x{block_hash}...")
            print(f"     Execution block: {block_data['data']['message']['body']['execution_payload']['block_number']}")
            return False, proposer, f"0x{block_hash}..."
            
        elif r.status_code == 404:
            # KEIN Block existiert - das ist gut!
            print(f"  ✅ NO BLOCK: Slot {slot} has no block (404)")
            
            # 2. Prüfe den nächsten Slot um sicherzustellen dass die Chain weiterläuft
            next_slot = slot + 1
            r_next = requests.get(
                f"{BEACON_API}/eth/v2/beacon/blocks/{next_slot}",
                timeout=5
            )
            
            if r_next.status_code == 200:
                # Nächster Slot hat einen Block - Chain läuft weiter
                next_block_data = r_next.json()
                print(f"  ✅ CHAIN CONTINUES: Slot {next_slot} has block")
                print(f"     Next proposer: {int(next_block_data['data']['message']['proposer_index'])}")
                return True, None, None
            elif r_next.status_code == 404:
                print(f"  ⚠️  CHAIN MAY BE STUCK: Slot {next_slot} also has no block")
                return True, None, None  # Trotzdem als Erfolg werten
            else:
                print(f"  ⚠️  Cannot verify chain continuation")
                return True, None, None
                
        else:
            print(f"  ⚠️  API Error {r.status_code} for slot {slot}")
            return None, None, None
            
    except Exception as e:
        print(f"  ⚠️  Verification error: {e}")
        return None, None, None

def verify_validator_penalty(validator_index, slot):
    """Überprüfe ob der Validator eine Penalty für das Verpassen des Slots erhielt"""
    print(f"\n[PENALTY VERIFICATION] Checking penalties for validator {validator_index}...")
    
    try:
        # 1. Hole Validator-Balance vor und nach dem Slot
        # Balance vor dem Slot (State bei slot-1)
        balance_before = None
        balance_after = None
        
        # Versuche Balance vor dem Slot zu bekommen
        try:
            r_before = requests.get(
                f"{BEACON_API}/eth/v1/beacon/states/{slot-1}/validators/{validator_index}",
                timeout=5
            )
            if r_before.status_code == 200:
                balance_before = int(r_before.json()["data"]["balance"])
        except:
            pass
        
        # Versuche Balance nach dem Slot zu bekommen (slot+1)
        try:
            r_after = requests.get(
                f"{BEACON_API}/eth/v1/beacon/states/{slot+5}/validators/{validator_index}",  # +5 um sicherzustellen dass State verfügbar
                timeout=5
            )
            if r_after.status_code == 200:
                balance_after = int(r_after.json()["data"]["balance"])
        except:
            pass
        
        if balance_before and balance_after:
            difference = balance_after - balance_before
            difference_eth = difference / 1e9
            
            print(f"  Balance before slot {slot}: {balance_before / 1e9:.6f} ETH")
            print(f"  Balance after slot {slot}:  {balance_after / 1e9:.6f} ETH")
            
            if difference < 0:
                print(f"  ⚠️  PENALTY DETECTED: Validator lost {abs(difference_eth):.6f} ETH")
                return True, difference_eth
            elif difference > 0:
                print(f"  ✅ REWARD: Validator gained {difference_eth:.6f} ETH")
                return False, difference_eth
            else:
                print(f"  ⚠️  NO CHANGE: Balance unchanged")
                return None, 0
        else:
            print(f"  ⚠️  Cannot get balance information")
            return None, None
            
    except Exception as e:
        print(f"  ⚠️  Penalty check error: {e}")
        return None, None

def verify_chain_impact(slot):
    """Überprüfe die Auswirkungen auf die Chain"""
    print(f"\n[CHAIN IMPACT] Checking chain impact around slot {slot}...")
    
    try:
        # Prüfe mehrere Slots vor und nach dem angegriffenen Slot
        slots_to_check = [slot-2, slot-1, slot, slot+1, slot+2]
        
        block_status = {}
        
        for check_slot in slots_to_check:
            if check_slot < 0:
                continue
                
            r = requests.get(
                f"{BEACON_API}/eth/v2/beacon/blocks/{check_slot}",
                timeout=5
            )
            
            if r.status_code == 200:
                block_data = r.json()
                proposer = int(block_data["data"]["message"]["proposer_index"])
                block_status[check_slot] = {
                    'exists': True,
                    'proposer': proposer,
                    'block_number': block_data['data']['message']['body']['execution_payload']['block_number']
                }
            elif r.status_code == 404:
                block_status[check_slot] = {'exists': False}
            else:
                block_status[check_slot] = {'exists': None, 'error': r.status_code}
        
        # Analysiere die Ergebnisse
        print(f"  Slot analysis:")
        for check_slot in sorted(block_status.keys()):
            status = block_status[check_slot]
            
            if check_slot == slot:
                slot_marker = "← ATTACK"
            else:
                slot_marker = ""
            
            if status.get('exists') is True:
                print(f"    Slot {check_slot:4d}: ✅ Block #{status['block_number']:6d} by validator {status['proposer']:3d} {slot_marker}")
            elif status.get('exists') is False:
                print(f"    Slot {check_slot:4d}: ❌ NO BLOCK {slot_marker}")
            else:
                print(f"    Slot {check_slot:4d}: ⚠️  Unknown {slot_marker}")
        
        # Berechne Block-Produktionsrate
        total_slots = len([s for s in slots_to_check if s >= 0])
        blocks_produced = len([s for s in block_status.values() if s.get('exists') is True])
        production_rate = (blocks_produced / total_slots) * 100 if total_slots > 0 else 0
        
        print(f"\n  Block production rate around slot {slot}: {production_rate:.1f}%")
        
        if block_status.get(slot, {}).get('exists') is False:
            return True, production_rate  # Erfolg: angegriffener Slot hat keinen Block
        else:
            return False, production_rate
        
    except Exception as e:
        print(f"  ⚠️  Chain impact check error: {e}")
        return None, None

def comprehensive_verification(slot, validator_index, vc):
    """Umfassende Verifikation des Angriffs"""
    print(f"\n{'='*60}")
    print(f"COMPREHENSIVE VERIFICATION FOR SLOT {slot}")
    print(f"Target: Validator {validator_index} ({vc})")
    print(f"{'='*60}")
    
    verification_results = {
        'slot': slot,
        'validator': validator_index,
        'vc': vc,
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }
    
    # 1. Block-Verifikation
    block_success, actual_proposer, block_hash = verify_no_block_produced(slot)
    verification_results['block_missing'] = block_success
    verification_results['actual_proposer'] = actual_proposer
    verification_results['block_hash'] = block_hash
    
    # 2. Penalty-Verifikation (falls Block fehlt)
    if block_success is True:
        penalty_detected, penalty_amount = verify_validator_penalty(validator_index, slot)
        verification_results['penalty_detected'] = penalty_detected
        verification_results['penalty_amount'] = penalty_amount
    
    # 3. Chain-Impact-Verifikation
    chain_impact, production_rate = verify_chain_impact(slot)
    verification_results['chain_impact'] = chain_impact
    verification_results['production_rate'] = production_rate
    
    # 4. Zusammenfassung
    print(f"\n{'='*60}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*60}")
    
    if block_success is True:
        print(f"✅ PRIMARY SUCCESS: No block produced at slot {slot}")
        
        if penalty_detected is True:
            print(f"✅ SECONDARY SUCCESS: Validator received penalty of {abs(penalty_amount):.6f} ETH")
        elif penalty_detected is False:
            print(f"⚠️  NO PENALTY: Validator balance unchanged or increased")
        else:
            print(f"⚠️  PENALTY CHECK: Inconclusive")
            
        if chain_impact is True:
            print(f"✅ CHAIN IMPACT: Successfully disrupted block production")
            print(f"   Production rate around slot: {production_rate:.1f}%")
        else:
            print(f"⚠️  LIMITED IMPACT: Chain continued normally")
            
        verification_results['overall_success'] = True
        
    elif block_success is False:
        print(f"❌ PRIMARY FAILURE: Block was produced at slot {slot}")
        print(f"   Actual proposer: {actual_proposer}")
        print(f"   Block hash: {block_hash}")
        
        if actual_proposer == validator_index:
            print(f"❌ CRITICAL FAILURE: Target validator still produced the block!")
        else:
            print(f"⚠️  PARTIAL FAILURE: Different validator produced block")
            
        verification_results['overall_success'] = False
        
    else:
        print(f"⚠️  INCONCLUSIVE: Cannot verify block status")
        verification_results['overall_success'] = None
    
    print(f"{'='*60}")
    
    return verification_results

# =========================
# BEACON API FUNCTIONS (bleiben gleich)
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
            timeout=5
        )
        
        if r.status_code == 200:
            data = r.json()["data"]
            for duty in data:
                if int(duty["slot"]) == slot:
                    return int(duty["validator_index"])
            return None
        else:
            return None
            
    except Exception as e:
        return None

# =========================
# ENHANCED ATTACK FUNCTION MIT VERBESSERTER VERIFIKATION
# =========================

def run_enhanced_last_revealer_attack():
    """Enhanced last-revealer attack with comprehensive verification"""
    print("Starting enhanced last-revealer attack")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    
    # Zeige detaillierte Service-Informationen
    get_detailed_service_info()
    
    # Initiale Daten
    genesis_time = get_genesis_time()
    start_slot = get_head_slot()
    
    if genesis_time is None or start_slot is None:
        return
    
    end_slot = start_slot + ATTACK_EPOCHS * SLOTS_PER_EPOCH
    
    print(f"\n{'='*60}")
    print("ATTACK PARAMETERS")
    print(f"{'='*60}")
    print(f"Current slot: {start_slot}")
    print(f"Attack until slot: {end_slot}")
    print(f"Attack probability: {ATTACK_PROBABILITY*100}%")
    print(f"Offline slots: {OFFLINE_SLOTS}")
    print(f"Available VCs: {', '.join(AVAILABLE_VC_SERVICES)}")
    
    all_verifications = []
    
    for slot in range(start_slot + 1, end_slot + 1):
        if random.random() > ATTACK_PROBABILITY:
            continue
            
        proposer = get_proposer_for_slot(slot)
        if proposer is None:
            continue
        
        vc = validator_to_vc(proposer)
        if vc is None:
            continue
        
        slot_ts = genesis_time + slot * SECONDS_PER_SLOT
        current_time = time.time()
        
        if slot_ts < current_time:
            continue
        
        print(f"\n{'='*60}")
        print(f"[ATTACK] Slot {slot} | Proposer {proposer} | {vc}")
        print(f"  Slot time: {datetime.fromtimestamp(slot_ts, tz=timezone.utc).strftime('%H:%M:%S')}")
        print(f"  Current: {datetime.fromtimestamp(current_time, tz=timezone.utc).strftime('%H:%M:%S')}")
        
        try:
            # Warten und stoppen
            stop_time = slot_ts - STOP_OFFSET
            if stop_time > current_time:
                time.sleep(max(0.1, stop_time - current_time))
            
            print(f"  Stopping {vc}...")
            if stop_vc(vc):
                print(f"  Keeping offline for {OFFLINE_SLOTS} slots...")
                time.sleep(OFFLINE_SLOTS * SECONDS_PER_SLOT)
                
                print(f"  Starting {vc}...")
                start_vc(vc)
                
                # Umfassende Verifikation
                verification = comprehensive_verification(slot, proposer, vc)
                all_verifications.append(verification)
                
            else:
                print(f"  ❌ Failed to stop {vc}")
                
        except Exception as e:
            print(f"  ❌ Error during attack: {e}")
        
        print(f"{'='*60}")
        time.sleep(2)
    
    # Finale Zusammenfassung
    print(f"\n{'='*60}")
    print("FINAL ATTACK SUMMARY")
    print(f"{'='*60}")
    
    successful = sum(1 for v in all_verifications if v.get('overall_success') is True)
    failed = sum(1 for v in all_verifications if v.get('overall_success') is False)
    unknown = sum(1 for v in all_verifications if v.get('overall_success') is None)
    
    print(f"Total attacks: {len(all_verifications)}")
    print(f"Successful attacks (no block): {successful}")
    print(f"Failed attacks (block produced): {failed}")
    print(f"Unknown results: {unknown}")
    
    if successful > 0:
        success_rate = (successful / len(all_verifications)) * 100 if all_verifications else 0
        print(f"\n✅ OVERALL SUCCESS RATE: {success_rate:.1f}%")
        
        # Zeige erfolgreiche Angriffe
        print(f"\nSuccessful attacks:")
        for v in all_verifications:
            if v.get('overall_success') is True:
                print(f"  Slot {v['slot']}: Validator {v['validator']} ({v['vc']})")
    
    print(f"{'='*60}")

# =========================
# STOP/START FUNCTIONS
# =========================

def stop_vc(vc):
    if vc is None:
        return False
        
    try:
        result = subprocess.run(
            ["kurtosis", "service", "stop", ENCLAVE, vc],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False

def start_vc(vc):
    if vc is None:
        return False
        
    try:
        result = subprocess.run(
            ["kurtosis", "service", "start", ENCLAVE, vc],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False

# =========================
# ENTRYPOINT
# =========================

if __name__ == "__main__":
    print(f"{'='*60}")
    print("COMPREHENSIVE LAST-REVEALER ATTACK SCRIPT")
    print(f"{'='*60}")
    
    print("\nSelect mode:")
    print("1. Run comprehensive attack with verification")
    print("2. Get detailed service information")
    print("3. Verify specific slot")
    print("4. Quick test of verification functions")
    
    try:
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            run_enhanced_last_revealer_attack()
        elif choice == "2":
            get_detailed_service_info()
        elif choice == "3":
            try:
                slot = int(input("Enter slot to verify: "))
                validator = get_proposer_for_slot(slot)
                if validator:
                    vc = validator_to_vc(validator)
                    comprehensive_verification(slot, validator, vc)
                else:
                    print(f"No proposer found for slot {slot}")
            except ValueError:
                print("Invalid slot number")
        elif choice == "4":
            # Test der Verifikationsfunktionen
            test_slot = get_head_slot()
            if test_slot:
                print(f"\nTesting verification functions on slot {test_slot}...")
                verify_no_block_produced(test_slot)
                if test_slot > 0:
                    verify_chain_impact(test_slot-1)
            else:
                print("Cannot get current slot")
        else:
            print("Invalid choice. Running comprehensive attack...")
            run_enhanced_last_revealer_attack()
            
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\nError: {e}")