# randao_mix_cl_logger
# -> Script to log the randao_mix value before it is transmittted from the consensus layer to the execution layer as "prevrandao".

import requests
import time
import json


API = "http://127.0.0.1:41815"       # lighthouse beacon API
POLL_INTERVAL = 3                    # duration between logs in seconds
OUTPUT_FILE = "cl_randao_log.jsonl"  # logfile name and destination


def get_randao():                    # get the randao_mix value
    r = requests.get(
        f"{API}/eth/v1/beacon/states/head/randao",
        timeout=5
    )
    r.raise_for_status()
    return r.json()["data"]


def get_head_slot():                # get the slot number
    r = requests.get(
        f"{API}/eth/v1/beacon/headers/head",
        timeout=5
    )
    r.raise_for_status()
    return int(r.json()["data"]["header"]["message"]["slot"])


def hex_to_bits(hexstr):            # convert the Hex to binary for later analysing
    return bin(int(hexstr, 16))[2:].zfill(256)


def main():
    print("Start randao logger")
    last_seen_slot = -1

    while True:
        try:
            slot = get_head_slot()

            if slot != last_seen_slot:         # check if new slot is filled
                randao = get_randao()
                randaostr = randao["randao"]   # convert input to string

                entry = {
                    "slot": slot,
                    "epoch": slot // 32,       # randao is finalized at the end of each epoch
                    "randao_hex": randaostr,
                    "randao_bits": hex_to_bits(randaostr)
                }

                with open(OUTPUT_FILE, "a") as f:           # append new entrys to the logfile
                    f.write(json.dumps(entry) + "\n")

                print(f"Slot {slot} | epoch {slot // 32}")  # check if the log is written

                last_seen_slot = slot

            time.sleep(POLL_INTERVAL)

        except Exception as e:     # catch errors
            print(f"error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    main()

