import requests
import time
import json

BEACON_API = "http://127.0.0.1:32865"
POLL_INTERVAL = 3  # seconds

def get_finalized_randao():
    r = requests.get(
        f"{BEACON_API}/eth/v1/beacon/states/finalized/randao",
        timeout=5,
    )
    r.raise_for_status()
    return r.json()["data"]["randao"]

def get_finalized_epoch():
    r = requests.get(
        f"{BEACON_API}/eth/v1/beacon/states/finalized/finality_checkpoints",
        timeout=5,
    )
    r.raise_for_status()
    return int(r.json()["data"]["finalized"]["epoch"])

def collect_finalized_randao_seeds(output_file="randao_log.jsonl"):
    last_collected_epoch = -1
    print("Waiting for finalized epochs...")

    while True:
        try:
            finalized_epoch = get_finalized_epoch()

            for epoch in range(last_collected_epoch + 1, finalized_epoch + 1):
                randao_seed = get_finalized_randao()

                log_entry = {
                    "epoch_finalized": epoch,
                    "capture_at_epoch": finalized_epoch,
                    "randao_seed_for_next_epoch": randao_seed
                }

                print(f"Epoch {epoch} finalized → RANDAO: {randao_seed}")

                with open(output_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")

                last_collected_epoch = epoch

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    collect_finalized_randao_seeds()
