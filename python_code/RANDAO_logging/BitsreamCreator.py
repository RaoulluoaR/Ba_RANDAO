#BitStreamCreator -> json log file to NIST usable bitstream
import json

INPUT = "cl_randao_log.jsonl"
OUTPUT = "randao_nist_bits.txt"

seen_epochs = set()
bitstream = []

with open(INPUT) as f:
    for line in f:
        entry = json.loads(line)
        epoch = entry["epoch"]

        # only one value per epoch
        if epoch in seen_epochs:
            continue

        # seen_epochs.add(epoch) # count all slots or only finalized ones
        bitstream.append(entry["randao_bits"])


with open(OUTPUT, "w") as f:    # w modus to overwrite any old version
    f.write("".join(bitstream))

print(f"Wrote {len(bitstream)} epochs × 256 bits")

