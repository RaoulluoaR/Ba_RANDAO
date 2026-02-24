
# ============================================================
# RANDAO Statistical Analysis Script
# ============================================================

import numpy as np
import matplotlib.pyplot as plt
from scipy.special import erfc
from scipy.stats import chi2
import math

# ============================================================
# CHANGE THIS TO YOUR INPUT FILE
# ============================================================
INPUT_FILE = "randao_binary_stream_UnMOD_Base.txt"

# ============================================================
# LOAD BITSTREAM
# ============================================================

with open(INPUT_FILE, "r") as f:
    bitstream = f.read().strip()

bitstream = "".join(bitstream.split())
bits = np.array([int(b) for b in bitstream])
n = len(bits)

print("Total bits loaded:", n)

# ============================================================
# MONOBIT TEST
# ============================================================

num_ones = np.sum(bits)
num_zeros = n - num_ones

S_obs = abs(num_ones - num_zeros) / np.sqrt(n)
p_value_monobit = erfc(S_obs / np.sqrt(2))

print("\n--- Monobit Test ---")
print("Zeros:", num_zeros)
print("Ones :", num_ones)
print("Z-score:", S_obs)
print("p-value:", p_value_monobit)

cumsum = np.cumsum(2*bits - 1)
plt.figure()
plt.plot(cumsum)
plt.title("Cumulative Sum of Bitstream")
plt.xlabel("Bit Index")
plt.ylabel("Cumulative Sum")
plt.show()

# ============================================================
# SHANNON ENTROPY
# ============================================================

p = num_ones / n
if p in [0, 1]:
    shannon_entropy = 0
else:
    shannon_entropy = -p*np.log2(p) - (1-p)*np.log2(1-p)

print("\n--- Shannon Entropy ---")
print("Entropy:", shannon_entropy)

# ============================================================
# MIN-ENTROPY
# ============================================================

max_prob = max(p, 1-p)
min_entropy = -np.log2(max_prob)

print("\n--- Min-Entropy ---")
print("Min-Entropy:", min_entropy)

# ============================================================
# 2-BIT SERIAL TEST
# ============================================================

pairs = [bitstream[i:i+2] for i in range(n-1)]
counts = {
    "00": pairs.count("00"),
    "01": pairs.count("01"),
    "10": pairs.count("10"),
    "11": pairs.count("11")
}

expected = (n-1)/4
chi_square = sum((counts[k] - expected)**2 / expected for k in counts)
p_value_serial = 1 - chi2.cdf(chi_square, df=3)

print("\n--- 2-Bit Serial Test ---")
print("Counts:", counts)
print("Chi-square:", chi_square)
print("p-value:", p_value_serial)

plt.figure()
plt.bar(counts.keys(), counts.values())
plt.title("2-Bit Pair Frequencies")
plt.xlabel("Bit Pair")
plt.ylabel("Count")
plt.show()

# ============================================================
# RUNS TEST
# ============================================================

runs = 1
for i in range(1, n):
    if bits[i] != bits[i-1]:
        runs += 1

expected_runs = 2*n*p*(1-p)
variance_runs = 2*n*p*(1-p)*(1 - 2*p*(1-p))
z_runs = (runs - expected_runs) / np.sqrt(variance_runs)
p_value_runs = erfc(abs(z_runs)/np.sqrt(2))

print("\n--- Runs Test ---")
print("Observed runs:", runs)
print("Z-score:", z_runs)
print("p-value:", p_value_runs)

# ============================================================
# AUTOCORRELATION (Lag 1–10)
# ============================================================

print("\n--- Autocorrelation ---")
lags = range(1, 11)
autocorr_values = []

for lag in lags:
    corr = np.corrcoef(bits[:-lag], bits[lag:])[0,1]
    autocorr_values.append(corr)
    print(f"Lag {lag}: {corr}")

plt.figure()
plt.plot(list(lags), autocorr_values)
plt.title("Autocorrelation (Lag 1–10)")
plt.xlabel("Lag")
plt.ylabel("Correlation")
plt.show()

# ============================================================
# HAMMING DISTANCE BETWEEN 256-BIT SEEDS
# ============================================================

seed_length = 256
num_seeds = n // seed_length

seeds = [
    bits[i*seed_length:(i+1)*seed_length]
    for i in range(num_seeds)
]

hamming_distances = []

for i in range(len(seeds)-1):
    dist = np.sum(seeds[i] != seeds[i+1])
    hamming_distances.append(dist)

mean_hd = np.mean(hamming_distances)
std_hd = np.std(hamming_distances)

print("\n--- Hamming Distance Between Consecutive Seeds ---")
print("Number of seeds:", num_seeds)
print("Mean Hamming Distance:", mean_hd)
print("Std Dev:", std_hd)
print("Expected mean (ideal): 128")
print("Expected std (ideal): 8")

plt.figure()
plt.hist(hamming_distances, bins=15)
plt.title("Hamming Distance Distribution")
plt.xlabel("Hamming Distance")
plt.ylabel("Frequency")
plt.show()

print("\nAnalysis complete.")
