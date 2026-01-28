# randao_mix_cl_logger
# -> Script to log the randao_mix value before it is transmittted from the consensus layer to the execution layer as "prevrandao".

import requests
import time
import json


API = "http://127.0.0.1:32784"       # lighthouse beacon API
POLL_INTERVAL = 3                    # duration between logs in seconds
OUTPUT_FILE = "cl_randao_log.jsonl"  # logfile name and destination


def get_randao():                    # get the randao_mix value
    r = requests.get(
        f"{API}/eth/v1/beacon/states/head/randao",
        timeout=5
    )
    r.raise_for_status()
    return r.json()["data"]


def get_randao_at_slot(slot):       # get the randao_mix value at a certain slot
    r = requests.get(
        f"{API}/eth/v1/beacon/states/{slot}/randao",
        timeout=5
    )
    r.raise_for_status()
    return r.json()["data"]


def get_head_slot():                # get the current slot number
    r = requests.get(
        f"{API}/eth/v1/beacon/headers/head",
        timeout=5
    )
    r.raise_for_status()
    return int(r.json()["data"]["header"]["message"]["slot"]) # int of the slot


def get_randao_at_final_slot(epoch):    # get the randao_mix value at the final slot
    first = (epoch-1) * 32
    last = first + 31

    for slot in range(last, first - 1, -1):
        try:
            r = requests.get(
                f"{API}/eth/v1/beacon/states/{slot}/randao",
                timeout=5
            )
            r.raise_for_status()
            return r.json()["data"], slot   # logging slot for later attack analyse
        
        except Exception as e:     # catch errors

            if e.response.status_code == 400:   # 400er errors überspringen
                continue  # skip invalid slots
            else:
                raise e

    raise RuntimeError(f"No blocks found in epoch {epoch}") # function can not return none



def hex_to_bits(hexstr):            # convert the Hex to binary for later analysing
    return bin(int(hexstr, 16))[2:].zfill(256)


def main():
    print("Start randao logger")
    #last_seen_slot = -1
    last_seen_epoch = -1

    while last_seen_epoch < 3907:    # allows for 10 sequenzes of NIST testing as 1 epoch equals 256 bits
        try:
            slot = get_head_slot()
            epoch = slot // 32
            completed_epoch = epoch - 1
            #last_slot_of_epoch = epoch * 32 + 31    # determins the slot of the finalized randao

            #if slot != last_seen_slot:         # check if new slot is filled
            if completed_epoch >= 0 and completed_epoch != last_seen_epoch: #and slot >= last_slot_of_epoch:   # check if new epoch and final Slot
                #randao = get_randao()
                #randao = get_randao_at_slot(last_slot_of_epoch)
                randao, used_slot = get_randao_at_final_slot(completed_epoch)

                if randao is None:
                    print(f"No finalized randao yet for epoch {completed_epoch}, retrying...")
                    time.sleep(POLL_INTERVAL)
                    continue

                randaostr = randao["randao"]   # convert input to string

                entry = {
                    #"slot": slot,
                    "used_slot": used_slot, # may differ as result of l.r. attack
                    "epoch": completed_epoch,         # randao is finalized at the end of each epoch
                    "randao_hex": randaostr,
                    "randao_bits": hex_to_bits(randaostr)
                }

                with open(OUTPUT_FILE, "a") as f:           # append new entrys to the logfile
                    f.write(json.dumps(entry) + "\n")

                #print(f"Slot {slot} | epoch {slot // 32}")  # check if the log is written
                print(f"Slot {used_slot} | epoch {completed_epoch}")

                #last_seen_slot = slot
                last_seen_epoch = completed_epoch

            time.sleep(POLL_INTERVAL)

        except Exception as e:     # catch errors
            print(f"error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    main()

