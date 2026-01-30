#!/usr/bin/env python3
"""
RANDAO Randomness Analysis Tool - FIXED VERSION
Compatible with SciPy >= 1.10.0
"""

import json
import pandas as pd
import numpy as np
from collections import defaultdict
import matplotlib.pyplot as plt
from scipy import stats
from scipy.spatial.distance import hamming
import seaborn as sns
from pathlib import Path
from typing import List, Dict, Tuple
import argparse

class RANDAOAnalyzer:
    def __init__(self, log_file: str, output_dir: str = "./randao_analysis"):
        """
        Initialize analyzer with RANDAO log file
        """
        self.log_file = Path(log_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Load and prepare data
        self.df = self.load_data()
        self.bit_arrays = self.extract_bit_arrays()
        
        print(f"📊 Loaded {len(self.df)} RANDAO samples")
        print(f"📈 Epoch range: {self.df['epoch'].min()} to {self.df['epoch'].max()}")
        
    def load_data(self) -> pd.DataFrame:
        """Load and parse the JSONL log file"""
        data = []
        with open(self.log_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    data.append(entry)
                except json.JSONDecodeError as e:
                    print(f"⚠️ Skipping malformed line {line_num}: {e}")
                    continue
        
        if not data:
            raise ValueError("No valid data found in log file")
        
        df = pd.DataFrame(data)
        
        # Check for required columns
        if 'randao_bits' not in df.columns:
            raise ValueError("Missing required column: 'randao_bits'")
        
        # Add epoch if not present (use index as fallback)
        if 'epoch' not in df.columns:
            print("⚠️ 'epoch' column not found, using index")
            df['epoch'] = df.index
        
        # Ensure bit strings are valid
        invalid_bits = []
        for idx, bits in enumerate(df['randao_bits']):
            if not isinstance(bits, str) or len(bits) != 256 or not set(bits).issubset({'0', '1'}):
                invalid_bits.append(idx)
        
        if invalid_bits:
            print(f"⚠️ Found {len(invalid_bits)} invalid bit strings, filtering them out")
            df = df.drop(invalid_bits).reset_index(drop=True)
        
        # Sort by epoch
        df = df.sort_values('epoch').reset_index(drop=True)
        df['epoch_seq'] = range(len(df))
        
        return df
    
    def extract_bit_arrays(self) -> np.ndarray:
        """Convert bit strings to numpy arrays for fast computation"""
        if len(self.df) == 0:
            return np.array([])
        
        bit_arrays = []
        for bits in self.df['randao_bits']:
            bit_array = np.array([int(b) for b in bits], dtype=np.uint8)
            bit_arrays.append(bit_array)
        
        return np.array(bit_arrays)
    
    # ==================== BIT-LEVEL ANALYSIS ====================
    
    def analyze_bit_bias(self) -> Dict:
        """Analyze bias in each bit position (0-255)"""
        print("\n🔍 Analyzing Bit Bias...")
        
        if len(self.bit_arrays) == 0:
            return {"error": "No bit arrays available"}
        
        n_samples = len(self.bit_arrays)
        bit_counts = np.sum(self.bit_arrays, axis=0)  # Sum of 1s per bit position
        
        bit_biases = bit_counts / n_samples
        expected = 0.5
        
        # Use binomtest from scipy.stats (modern version)
        try:
            from scipy.stats import binomtest
            use_binomtest = True
        except ImportError:
            from scipy.stats import binom_test
            use_binomtest = False
        
        biased_bits = []
        for bit_pos in range(256):
            ones = int(bit_counts[bit_pos])
            total = n_samples
            
            try:
                if use_binomtest:
                    # Modern SciPy (>= 1.10.0)
                    result = binomtest(ones, total, p=0.5, alternative='two-sided')
                    p_value = result.pvalue
                else:
                    # Legacy SciPy
                    p_value = binom_test(ones, total, p=0.5, alternative='two-sided')
            except Exception as e:
                print(f"Warning: Could not compute p-value for bit {bit_pos}: {e}")
                p_value = 1.0
            
            if p_value < 0.01:
                bias = float(bit_biases[bit_pos])
                biased_bits.append({
                    'position': bit_pos,
                    'bias': bias,
                    'p_value': float(p_value),
                    'ones_count': int(ones),
                    'total_samples': int(total),
                    'deviation': abs(bias - 0.5)
                })
        
        results = {
            'bit_positions': list(range(256)),
            'biases': [float(b) for b in bit_biases],
            'mean_bias': float(np.mean(np.abs(bit_biases - expected))),
            'max_bias': float(np.max(np.abs(bit_biases - expected))),
            'median_bias': float(np.median(np.abs(bit_biases - expected))),
            'biased_bits': biased_bits,
            'n_samples': n_samples
        }
        
        print(f"  Mean absolute bias from 0.5: {results['mean_bias']:.6f}")
        print(f"  Maximum bias: {results['max_bias']:.6f}")
        print(f"  Significantly biased bits (p<0.01): {len(results['biased_bits'])}")
        
        if len(results['biased_bits']) > 0:
            top_biased = sorted(results['biased_bits'], key=lambda x: x['p_value'])[:5]
            print(f"  Most biased bits:")
            for bit in top_biased:
                print(f"    Bit {bit['position']:3d}: bias={bit['bias']:.4f}, p={bit['p_value']:.6f}")
        
        return results
    
    def analyze_hamming_distances(self) -> Dict:
        """Analyze Hamming distances between consecutive and random samples"""
        print("\n🔗 Analyzing Hamming Distances...")
        
        if len(self.bit_arrays) < 2:
            return {"error": "Need at least 2 samples for Hamming analysis"}
        
        n_samples = len(self.bit_arrays)
        consecutive_distances = []
        
        # Calculate distances between consecutive samples
        for i in range(n_samples - 1):
            dist = hamming(self.bit_arrays[i], self.bit_arrays[i + 1]) * 256
            consecutive_distances.append(dist)
        
        # Calculate distances between random pairs
        random_pair_distances = []
        n_random_pairs = min(1000, max(10, n_samples // 2))
        
        np.random.seed(42)  # For reproducibility
        indices = np.arange(n_samples)
        
        for _ in range(n_random_pairs):
            i, j = np.random.choice(indices, 2, replace=False)
            dist = hamming(self.bit_arrays[i], self.bit_arrays[j]) * 256
            random_pair_distances.append(dist)
        
        # Statistical analysis
        results = {
            'consecutive': {
                'mean': float(np.mean(consecutive_distances)),
                'std': float(np.std(consecutive_distances)),
                'min': float(np.min(consecutive_distances)),
                'max': float(np.max(consecutive_distances)),
                'median': float(np.median(consecutive_distances)),
                'n': len(consecutive_distances)
            },
            'random': {
                'mean': float(np.mean(random_pair_distances)),
                'std': float(np.std(random_pair_distances)),
                'min': float(np.min(random_pair_distances)),
                'max': float(np.max(random_pair_distances)),
                'median': float(np.median(random_pair_distances)),
                'n': len(random_pair_distances)
            },
            'all': {
                'mean': float(np.mean(consecutive_distances + random_pair_distances)),
                'expected_mean': 128.0,
                'expected_std': 8.0
            }
        }
        
        # Test if consecutive differs from random
        try:
            t_stat, p_value = stats.ttest_ind(consecutive_distances, random_pair_distances, 
                                             equal_var=False)  # Welch's t-test
            results['consecutive_vs_random'] = {
                't_statistic': float(t_stat),
                'p_value': float(p_value),
                'significant': p_value < 0.05
            }
        except Exception as e:
            results['consecutive_vs_random'] = {
                'error': str(e),
                'significant': False
            }
            p_value = 1.0
        
        print(f"  Consecutive mean distance: {results['consecutive']['mean']:.2f} ± {results['consecutive']['std']:.2f}")
        print(f"  Random pairs mean distance: {results['random']['mean']:.2f} ± {results['random']['std']:.2f}")
        print(f"  Expected mean (random): {results['all']['expected_mean']:.2f}")
        print(f"  Consecutive ≠ Random? p={p_value:.6f} {'✓' if p_value < 0.05 else '✗'}")
        
        return results
    
    # ==================== ENTROPY ANALYSIS ====================
    
    def analyze_shannon_entropy(self) -> Dict:
        """Calculate Shannon entropy for each sample and overall"""
        print("\n🎲 Analyzing Shannon Entropy...")
        
        if len(self.df) == 0:
            return {"error": "No data available"}
        
        # Entropy per sample
        sample_entropies = []
        for bits in self.df['randao_bits']:
            # Count 0s and 1s
            counts = np.bincount([int(b) for b in bits], minlength=2)
            prob = counts / len(bits)
            
            # Calculate entropy (bits), handle log(0)
            ent = 0.0
            for p in prob:
                if p > 0:
                    ent -= p * np.log2(p)
            sample_entropies.append(ent)
        
        # Overall entropy across all bits
        all_bits = ''.join(self.df['randao_bits'])
        total_counts = np.bincount([int(b) for b in all_bits], minlength=2)
        total_prob = total_counts / len(all_bits)
        overall_entropy = 0.0
        for p in total_prob:
            if p > 0:
                overall_entropy -= p * np.log2(p)
        
        # Byte-wise entropy (8-bit chunks)
        byte_entropies = []
        for bits in self.df['randao_bits']:
            # Split into bytes (32 bytes = 256 bits)
            bytes_list = [bits[i:i+8] for i in range(0, 256, 8)]
            
            for byte in bytes_list:
                counts = np.bincount([int(b) for b in byte], minlength=2)
                prob = counts / 8
                ent = 0.0
                for p in prob:
                    if p > 0:
                        ent -= p * np.log2(p)
                byte_entropies.append(ent)
        
        results = {
            'sample_entropy': {
                'mean': float(np.mean(sample_entropies)),
                'std': float(np.std(sample_entropies)),
                'min': float(np.min(sample_entropies)),
                'max': float(np.max(sample_entropies)),
                'median': float(np.median(sample_entropies)),
                'n': len(sample_entropies)
            },
            'overall_entropy': float(overall_entropy),
            'expected_entropy': 1.0,
            'byte_entropy': {
                'mean': float(np.mean(byte_entropies)),
                'std': float(np.std(byte_entropies)),
                'n': len(byte_entropies)
            }
        }
        
        print(f"  Mean sample entropy: {results['sample_entropy']['mean']:.6f} ± {results['sample_entropy']['std']:.6f}")
        print(f"  Overall entropy: {results['overall_entropy']:.6f}")
        print(f"  Expected (perfect): {results['expected_entropy']:.6f}")
        print(f"  Byte-wise entropy: {results['byte_entropy']['mean']:.6f}")
        
        return results
    
    # ==================== AUTOCORRELATION ANALYSIS ====================
    
    def analyze_autocorrelation(self, max_lag: int = 50) -> Dict:
        """Analyze autocorrelation in bit sequences"""
        print(f"\n🔄 Analyzing Autocorrelation (max lag={max_lag})...")
        
        if len(self.df) == 0:
            return {"error": "No data available"}
        
        # Flatten all bits into one long sequence
        all_bits = ''.join(self.df['randao_bits'])
        if len(all_bits) < max_lag * 2:
            max_lag = len(all_bits) // 2
            print(f"  Adjusted max_lag to {max_lag} due to limited data")
        
        bit_array = np.array([int(b) for b in all_bits])
        
        # Normalize to [-1, 1] for correlation
        normalized = bit_array * 2 - 1
        
        # Calculate autocorrelation
        autocorr = []
        for lag in range(max_lag + 1):
            if lag == 0:
                corr = 1.0
            else:
                # Manual correlation calculation for efficiency
                n = len(normalized) - lag
                if n > 0:
                    corr = np.sum(normalized[:n] * normalized[lag:]) / n
                else:
                    corr = 0.0
            autocorr.append(corr)
        
        # Find significant correlations
        significant_lags = []
        n = len(bit_array)
        confidence_bound = 1.96 / np.sqrt(n)  # 95% confidence
        
        for lag in range(1, max_lag + 1):
            if abs(autocorr[lag]) > confidence_bound:
                significant_lags.append({
                    'lag': lag,
                    'correlation': float(autocorr[lag]),
                    'significant': True
                })
        
        results = {
            'autocorrelation': [float(c) for c in autocorr],
            'lags': list(range(max_lag + 1)),
            'confidence_95': float(confidence_bound),
            'significant_lags': significant_lags,
            'max_abs_correlation': float(np.max(np.abs(autocorr[1:]))) if len(autocorr) > 1 else 0.0,
            'total_bits': n
        }
        
        print(f"  95% confidence bound: ±{confidence_bound:.6f}")
        print(f"  Maximum absolute correlation: {results['max_abs_correlation']:.6f}")
        print(f"  Significant lags: {len(significant_lags)}")
        
        if significant_lags and len(significant_lags) <= 10:
            print(f"  Significant lags: {[l['lag'] for l in significant_lags]}")
        elif significant_lags:
            print(f"  First 10 significant lags: {[l['lag'] for l in significant_lags[:10]]}")
        
        return results
    
    # ==================== RUN ALL ANALYSES ====================
    
    def run_basic_analysis(self):
        """Run basic analyses (faster, for debugging)"""
        print("=" * 60)
        print("🧪 RANDAO BASIC ANALYSIS")
        print("=" * 60)
        
        results = {}
        
        # Run basic analyses
        results['bit_bias'] = self.analyze_bit_bias()
        results['hamming'] = self.analyze_hamming_distances()
        results['entropy'] = self.analyze_shannon_entropy()
        results['autocorrelation'] = self.analyze_autocorrelation(max_lag=min(20, len(self.df)))
        
        # Quick summary
        print("\n" + "=" * 60)
        print("📋 QUICK SUMMARY")
        print("=" * 60)
        
        if 'bit_bias' in results and 'mean_bias' in results['bit_bias']:
            bias_status = "✓" if results['bit_bias']['mean_bias'] < 0.01 else "⚠️"
            print(f"Bit Bias: {results['bit_bias']['mean_bias']:.6f} {bias_status}")
        
        if 'hamming' in results and 'consecutive' in results['hamming']:
            hamming_diff = abs(results['hamming']['consecutive']['mean'] - 128)
            hamming_status = "✓" if hamming_diff < 2 else "⚠️"
            print(f"Hamming Distance: {results['hamming']['consecutive']['mean']:.2f} {hamming_status}")
        
        if 'entropy' in results and 'sample_entropy' in results['entropy']:
            entropy_diff = 1.0 - results['entropy']['sample_entropy']['mean']
            entropy_status = "✓" if entropy_diff < 0.01 else "⚠️"
            print(f"Shannon Entropy: {results['entropy']['sample_entropy']['mean']:.6f} {entropy_status}")
        
        if 'autocorrelation' in results:
            autocorr_status = "✓" if len(results['autocorrelation']['significant_lags']) == 0 else "⚠️"
            print(f"Autocorrelation Issues: {len(results['autocorrelation']['significant_lags'])} {autocorr_status}")
        
        print("=" * 60)
        
        return results
    
    def run_complete_analysis(self):
        """Run all analyses and generate reports"""
        print("=" * 60)
        print("🧪 RANDAO COMPLETE ANALYSIS")
        print("=" * 60)
        
        results = {}
        
        # Run all analyses
        results['bit_bias'] = self.analyze_bit_bias()
        results['hamming'] = self.analyze_hamming_distances()
        results['entropy'] = self.analyze_shannon_entropy()
        results['autocorrelation'] = self.analyze_autocorrelation()
        
        # Generate summary
        results['summary'] = self.generate_summary(results)
        
        # Save results
        self.save_results(results)
        
        # Generate visualizations
        self.generate_visualizations(results)
        
        print("\n" + "=" * 60)
        print("✅ ANALYSIS COMPLETE")
        print(f"📁 Results saved to: {self.output_dir}")
        print("=" * 60)
        
        return results
    
    def generate_summary(self, results: Dict) -> Dict:
        """Generate a summary assessment"""
        issues = []
        warnings = []
        
        # Check bit bias
        if 'bit_bias' in results and 'mean_bias' in results['bit_bias']:
            if results['bit_bias']['mean_bias'] > 0.01:
                issues.append(f"High mean bit bias: {results['bit_bias']['mean_bias']:.4f}")
            
            if len(results['bit_bias'].get('biased_bits', [])) > 5:
                warnings.append(f"{len(results['bit_bias']['biased_bits'])} significantly biased bits")
        
        # Check Hamming distance
        if 'hamming' in results and 'consecutive' in results['hamming']:
            hamming_diff = abs(results['hamming']['consecutive']['mean'] - 128)
            if hamming_diff > 2:
                issues.append(f"Hamming distance differs from expected: {hamming_diff:.2f}")
        
        # Check entropy
        if 'entropy' in results and 'sample_entropy' in results['entropy']:
            entropy_diff = 1.0 - results['entropy']['sample_entropy']['mean']
            if entropy_diff > 0.01:
                warnings.append(f"Reduced entropy: {entropy_diff:.4f} below perfect")
        
        # Check autocorrelation
        if 'autocorrelation' in results:
            if results['autocorrelation'].get('significant_lags'):
                issues.append(f"Significant autocorrelation at {len(results['autocorrelation']['significant_lags'])} lags")
        
        # Overall assessment
        if not issues:
            assessment = "GOOD - No major randomness issues detected"
        elif len(issues) <= 2:
            assessment = "FAIR - Minor issues detected"
        else:
            assessment = "POOR - Multiple randomness issues detected"
        
        summary = {
            'assessment': assessment,
            'issues': issues,
            'warnings': warnings,
            'samples_analyzed': len(self.df),
            'bit_length': 256,
            'epoch_range': f"{self.df['epoch'].min()}-{self.df['epoch'].max()}"
        }
        
        return summary
    
    def save_results(self, results: Dict):
        """Save analysis results to files"""
        # Save full results as JSON
        results_file = self.output_dir / "analysis_results.json"
        
        # Custom JSON serializer
        def default_serializer(obj):
            if isinstance(obj, (np.integer, np.int32, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float32, np.float64)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            else:
                return str(obj)
        
        try:
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=default_serializer)
            
            # Save summary as Markdown
            summary_file = self.output_dir / "analysis_summary.md"
            with open(summary_file, 'w') as f:
                self.write_summary_markdown(f, results)
            
            print(f"  📄 Results saved to: {results_file}")
            print(f"  📄 Summary saved to: {summary_file}")
            
        except Exception as e:
            print(f"  ⚠️ Could not save results: {e}")
    
    def write_summary_markdown(self, f, results: Dict):
        """Write Markdown summary report"""
        from datetime import datetime
        
        summary = results.get('summary', {})
        
        f.write("# RANDAO Randomness Analysis Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"**Assessment:** {summary.get('assessment', 'UNKNOWN')}\n\n")
        f.write(f"**Samples analyzed:** {summary.get('samples_analyzed', 0)}\n")
        f.write(f"**Epoch range:** {summary.get('epoch_range', 'N/A')}\n")
        f.write(f"**Bit length:** {summary.get('bit_length', 256)}\n\n")
        
        issues = summary.get('issues', [])
        warnings = summary.get('warnings', [])
        
        if issues:
            f.write("## ❌ Issues Found\n\n")
            for issue in issues:
                f.write(f"- {issue}\n")
            f.write("\n")
        
        if warnings:
            f.write("## ⚠️ Warnings\n\n")
            for warning in warnings:
                f.write(f"- {warning}\n")
            f.write("\n")
        
        f.write("## Key Metrics\n\n")
        f.write("| Metric | Value | Expected | Status |\n")
        f.write("|--------|-------|----------|--------|\n")
        
        # Collect metrics safely
        metrics = []
        
        if 'bit_bias' in results and 'mean_bias' in results['bit_bias']:
            bias_val = results['bit_bias']['mean_bias']
            metrics.append(("Mean Bit Bias", f"{bias_val:.6f}", "0.000", 
                          "✓" if bias_val < 0.01 else "⚠️"))
        
        if 'bit_bias' in results and 'max_bias' in results['bit_bias']:
            max_bias_val = results['bit_bias']['max_bias']
            metrics.append(("Max Bit Bias", f"{max_bias_val:.6f}", "0.000", 
                          "✓" if max_bias_val < 0.05 else "⚠️"))
        
        if 'hamming' in results and 'consecutive' in results['hamming']:
            hamming_val = results['hamming']['consecutive']['mean']
            hamming_diff = abs(hamming_val - 128)
            metrics.append(("Hamming Distance", f"{hamming_val:.2f}", "128.00", 
                          "✓" if hamming_diff < 2 else "⚠️"))
        
        if 'entropy' in results and 'sample_entropy' in results['entropy']:
            entropy_val = results['entropy']['sample_entropy']['mean']
            metrics.append(("Shannon Entropy", f"{entropy_val:.6f}", "1.0000", 
                          "✓" if entropy_val > 0.99 else "⚠️"))
        
        if 'autocorrelation' in results and 'max_abs_correlation' in results['autocorrelation']:
            autocorr_val = results['autocorrelation']['max_abs_correlation']
            metrics.append(("Autocorrelation Max", f"{autocorr_val:.6f}", "<0.01", 
                          "✓" if autocorr_val < 0.01 else "⚠️"))
        
        for name, value, expected, status in metrics:
            f.write(f"| {name} | {value} | {expected} | {status} |\n")
        
        f.write("\n## Notes\n\n")
        f.write("See `analysis_results.json` for complete data.\n")
        f.write(f"\nAnalysis based on {len(self.df)} samples from epoch {self.df['epoch'].min()} to {self.df['epoch'].max()}.\n")
    
    def generate_visualizations(self, results: Dict):
        """Generate visualization plots"""
        print("\n📈 Generating visualizations...")
        
        try:
            # 1. Bit bias plot
            if 'bit_bias' in results and 'biases' in results['bit_bias']:
                plt.figure(figsize=(12, 6))
                biases = results['bit_bias']['biases'][:256]  # Ensure we only plot 256 bits
                plt.plot(range(len(biases)), biases)
                plt.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Expected (0.5)')
                plt.xlabel('Bit Position (0-255)')
                plt.ylabel('Frequency of 1s')
                plt.title('Bit Bias Analysis')
                plt.legend()
                plt.tight_layout()
                plt.savefig(self.output_dir / 'bit_bias.png', dpi=150)
                plt.close()
                print("  ✓ Bit bias plot saved")
            
            # 2. Hamming distance distribution
            if 'hamming' in results and 'consecutive' in results['hamming']:
                plt.figure(figsize=(10, 6))
                consecutive_vals = results['hamming']['consecutive'].get('values', [])
                random_vals = results['hamming']['random'].get('values', [])
                
                if consecutive_vals and random_vals:
                    plt.hist(consecutive_vals, alpha=0.5, bins=30, label='Consecutive', density=True)
                    plt.hist(random_vals, alpha=0.5, bins=30, label='Random Pairs', density=True)
                    plt.axvline(x=128, color='r', linestyle='--', label='Expected Mean (128)')
                    plt.xlabel('Hamming Distance')
                    plt.ylabel('Density')
                    plt.title('Hamming Distance Distribution')
                    plt.legend()
                    plt.tight_layout()
                    plt.savefig(self.output_dir / 'hamming_distance.png', dpi=150)
                    plt.close()
                    print("  ✓ Hamming distance plot saved")
            
            # 3. Entropy distribution
            if 'entropy' in results and 'sample_entropy' in results['entropy']:
                plt.figure(figsize=(10, 6))
                entropy_vals = results['entropy']['sample_entropy'].get('values', [])
                if entropy_vals:
                    plt.hist(entropy_vals, bins=20, alpha=0.7)
                    plt.axvline(x=1.0, color='r', linestyle='--', label='Perfect Entropy (1.0)')
                    plt.xlabel('Shannon Entropy (bits)')
                    plt.ylabel('Frequency')
                    plt.title('Sample Entropy Distribution')
                    plt.legend()
                    plt.tight_layout()
                    plt.savefig(self.output_dir / 'entropy_distribution.png', dpi=150)
                    plt.close()
                    print("  ✓ Entropy distribution plot saved")
            
            # 4. Autocorrelation plot
            if 'autocorrelation' in results and 'autocorrelation' in results['autocorrelation']:
                plt.figure(figsize=(10, 6))
                autocorr_vals = results['autocorrelation']['autocorrelation']
                lags = results['autocorrelation'].get('lags', range(len(autocorr_vals)))
                conf_bound = results['autocorrelation'].get('confidence_95', 0.0)
                
                if len(autocorr_vals) > 1:
                    plt.plot(lags, autocorr_vals, marker='o', markersize=3)
                    plt.axhline(y=conf_bound, color='r', linestyle='--', alpha=0.5, label='95% Confidence')
                    plt.axhline(y=-conf_bound, color='r', linestyle='--', alpha=0.5)
                    plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
                    plt.xlabel('Lag')
                    plt.ylabel('Autocorrelation')
                    plt.title('Autocorrelation Function')
                    plt.legend()
                    plt.tight_layout()
                    plt.savefig(self.output_dir / 'autocorrelation.png', dpi=150)
                    plt.close()
                    print("  ✓ Autocorrelation plot saved")
            
            print(f"  📊 Visualizations saved to {self.output_dir}")
            
        except Exception as e:
            print(f"  ⚠️ Could not generate some visualizations: {e}")

# ==================== MAIN EXECUTION ====================

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Analyze RANDAO randomness')
    parser.add_argument('--log-file', '-l', required=True, 
                       help='Path to JSONL log file with RANDAO data')
    parser.add_argument('--output-dir', '-o', default='./randao_analysis',
                       help='Output directory for analysis results')
    parser.add_argument('--basic', '-b', action='store_true',
                       help='Run only basic analysis (faster)')
    
    args = parser.parse_args()
    
    try:
        # Run analysis
        analyzer = RANDAOAnalyzer(args.log_file, args.output_dir)
        
        if args.basic:
            results = analyzer.run_basic_analysis()
        else:
            results = analyzer.run_complete_analysis()
        
        # Print quick summary
        if 'summary' in results:
            print("\n📋 Final Summary:")
            print(f"  Assessment: {results['summary']['assessment']}")
            print(f"  Issues: {len(results['summary']['issues'])}")
            print(f"  Warnings: {len(results['summary']['warnings'])}")
        
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()