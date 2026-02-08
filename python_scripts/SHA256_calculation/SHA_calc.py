import hashlib
import os


# Input RANDAO_value (signes epoch Bls Signature)
# hex_input = "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
hex_input = "111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111"

# Generate random 96 bytes (valid BLS signature length)
# random_bytes = os.urandom(96)
# hex_input = random_bytes.hex()

# Convert hex to bytes
bytes_data = bytes.fromhex(hex_input)

# Calculate SHA256
hash_bytes = hashlib.sha256(bytes_data).digest()
hash_hex = hash_bytes.hex()

# Print all 4 values
print("1. RANDAO_reveal:")
print(hex_input)
print()

print("2. RANDAO_reveal binary:")
for byte in bytes_data:
    print(format(byte, '08b'), end=' ')
print("\n")

print("3. SHA256_hash_(hex):")
print(hash_hex)
print()

print("4. SHA256_hash_(binary):")
for byte in hash_bytes:
    print(format(byte, '08b'), end=' ')
print()
