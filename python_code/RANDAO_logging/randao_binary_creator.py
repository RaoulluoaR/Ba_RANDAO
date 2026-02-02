#BitStreamCreator -> json log file to bit randao data
import json

INPUT_FILE = "randao_log.jsonl"
BITSTREAM_FILE = "randao_binary_stream.txt"
BITLINE_FILE = "randao_binary_sep.txt"


def hex_to_256bit_binary(hex_str):
    """
    Converts 0x-prefixed hex string to a 256-bit binary string
    """
    hex_str = hex_str.lower().replace("0x", "")
    return format(int(hex_str, 16), "0256b")


def process_randao_log():
    bitstream = []
    bitlines = []

    with open(INPUT_FILE, "r") as f:
        for line in f:
            if not line.strip():
                continue

            entry = json.loads(line)
            hex_seed = entry["randao_seed_for_next_epoch"]

            binary = hex_to_256bit_binary(hex_seed)

            # 1) continuous bitstream
            bitstream.append(binary)

            # 2) comma-separated bits per seed
            bitlines.append(binary)

    # write bitstream
    with open(BITSTREAM_FILE, "w") as f:
        f.write("".join(bitstream))

    # write csv-style bit file
    with open(BITLINE_FILE, "w") as f:
        for line in bitlines:
            f.write(line + "\n")

    print(f"Processed {len(bitlines)} RANDAO seeds")
    print(f"→ {BITSTREAM_FILE}")
    print(f"→ {BITLINE_FILE}")


if __name__ == "__main__":
    process_randao_log()
