import numpy as np
import pandas as pd
from preprocessing import FingerprintDatabase
from algorithms import KNN, WeightedKNN, RandomForestPositioning
import random

def evaluate_algorithm(algo, test_samples, db, algo_name):
    """Evaluate algorithm on test samples"""
    
    errors = []
    floor_correct = 0
    section_correct = 0
    
    for idx, sample in test_samples.iterrows():
        # Extract current scan
        current_scan = {}
        for bssid in db.all_bssids:
            if bssid in sample and pd.notna(sample[bssid]):
                current_scan[bssid] = int(sample[bssid])
        
        # Skip if no APs detected
        if len(current_scan) == 0:
            continue
        
        # Get ground truth
        actual_floor = sample['floor']
        actual_section = sample['section']
        actual_x = sample['x']
        actual_y = sample['y']
        
        # Estimate position
        try:
            result = algo.estimate_position(current_scan)
            
            # Calculate error
            error_x = abs(result['x'] - actual_x)
            error_y = abs(result['y'] - actual_y)
            error_distance = np.sqrt(error_x**2 + error_y**2)
            
            errors.append({
                'num_aps': len(current_scan),
                'error_x': error_x,
                'error_y': error_y,
                'error_distance': error_distance,
                'floor_correct': result['floor'] == actual_floor,
                'section_correct': result['section'] == actual_section,
                'confidence': result['confidence']
            })
            
            if result['floor'] == actual_floor:
                floor_correct += 1
            if result['section'] == actual_section:
                section_correct += 1
                
        except Exception as e:
            print(f"   Error on sample: {e}")
            continue
    
    # Calculate statistics
    if not errors:
        return None
    
    errors_df = pd.DataFrame(errors)
    
    stats = {
        'algorithm': algo_name,
        'num_tests': len(errors),
        'floor_accuracy': (floor_correct / len(errors)) * 100,
        'section_accuracy': (section_correct / len(errors)) * 100,
        'mean_error': errors_df['error_distance'].mean(),
        'median_error': errors_df['error_distance'].median(),
        'min_error': errors_df['error_distance'].min(),
        'max_error': errors_df['error_distance'].max(),
        'std_error': errors_df['error_distance'].std(),
        'percentile_90': errors_df['error_distance'].quantile(0.9),
        'percentile_95': errors_df['error_distance'].quantile(0.95),
        'mean_confidence': errors_df['confidence'].mean(),
        'mean_aps': errors_df['num_aps'].mean()
    }
    
    return stats, errors_df

def main():
    print("\n" + "="*70)
    print("📊 COMPREHENSIVE ALGORITHM EVALUATION")
    print("="*70)
    
    # Load database
    print("\n🔄 Loading fingerprint database...")
    db = FingerprintDatabase(data_dir='data')
    db.load_all_floors()
    db.create_reference_points()
    
    # Select random test samples (10% of data)
    num_test_samples = int(len(db.df) * 0.1)
    print(f"\n🎯 Selecting {num_test_samples} random test samples...")
    
    test_indices = random.sample(range(len(db.df)), num_test_samples)
    test_samples = db.df.iloc[test_indices]
    
    print(f"   Test samples by section:")
    for section in test_samples['section'].unique():
        count = len(test_samples[test_samples['section'] == section])
        print(f"     {section}: {count} samples")
    
    # Initialize algorithms
    print("\n🔧 Initializing algorithms...")
    knn = KNN(db.reference_points, db.all_bssids, k=3)
    wknn = WeightedKNN(db.reference_points, db.all_bssids, k=4)
    rf = RandomForestPositioning(db.reference_points, db.all_bssids)
    rf.train()
    
    # Evaluate each algorithm
    results = {}
    
    print("\n" + "="*70)
    print("🧪 TESTING K-NEAREST NEIGHBORS (KNN)")
    print("="*70)
    results['KNN'], knn_errors = evaluate_algorithm(knn, test_samples, db, 'KNN')
    
    print("\n" + "="*70)
    print("🧪 TESTING WEIGHTED K-NEAREST NEIGHBORS (WKNN)")
    print("="*70)
    results['WKNN'], wknn_errors = evaluate_algorithm(wknn, test_samples, db, 'WKNN')
    
    print("\n" + "="*70)
    print("🧪 TESTING RANDOM FOREST")
    print("="*70)
    results['RF'], rf_errors = evaluate_algorithm(rf, test_samples, db, 'Random Forest')
    
    # Display results
    print("\n" + "="*70)
    print("📊 EVALUATION RESULTS SUMMARY")
    print("="*70)
    
    # Create comparison table
    print(f"\n{'Metric':<25} {'KNN':>12} {'WKNN':>12} {'RF':>12}")
    print("-" * 70)
    
    metrics = [
        ('Tests', 'num_tests', ''),
        ('Floor Accuracy', 'floor_accuracy', '%'),
        ('Section Accuracy', 'section_accuracy', '%'),
        ('Mean Error', 'mean_error', ' units'),
        ('Median Error', 'median_error', ' units'),
        ('Min Error', 'min_error', ' units'),
        ('Max Error', 'max_error', ' units'),
        ('Std Dev', 'std_error', ' units'),
        ('90th Percentile', 'percentile_90', ' units'),
        ('95th Percentile', 'percentile_95', ' units'),
        ('Mean Confidence', 'mean_confidence', '%'),
        ('Avg APs Detected', 'mean_aps', '')
    ]
    
    for metric_name, metric_key, unit in metrics:
        knn_val = results['KNN'][metric_key] if results['KNN'] else 0
        wknn_val = results['WKNN'][metric_key] if results['WKNN'] else 0
        rf_val = results['RF'][metric_key] if results['RF'] else 0
        
        if unit == '%':
            print(f"{metric_name:<25} {knn_val:>10.1f}{unit:>2} {wknn_val:>10.1f}{unit:>2} {rf_val:>10.1f}{unit:>2}")
        elif unit == ' units':
            print(f"{metric_name:<25} {knn_val:>10.2f}{unit:>2} {wknn_val:>10.2f}{unit:>2} {rf_val:>10.2f}{unit:>2}")
        else:
            print(f"{metric_name:<25} {knn_val:>10.0f}{unit:>2} {wknn_val:>10.0f}{unit:>2} {rf_val:>10.0f}{unit:>2}")
    
    print("\n" + "="*70)
    
    # Find best algorithm
    best_algo = min(results.items(), key=lambda x: x[1]['mean_error'] if x[1] else float('inf'))
    print(f"\n🏆 BEST ALGORITHM: {best_algo[0]}")
    print(f"   Mean Error: {best_algo[1]['mean_error']:.2f} grid units")
    print(f"   Floor Accuracy: {best_algo[1]['floor_accuracy']:.1f}%")
    print(f"   Section Accuracy: {best_algo[1]['section_accuracy']:.1f}%")
    
    # Error distribution analysis
    print("\n" + "="*70)
    print("📈 ERROR DISTRIBUTION (All Algorithms)")
    print("="*70)
    
    for algo_name, errors_df in [('KNN', knn_errors), ('WKNN', wknn_errors), ('RF', rf_errors)]:
        print(f"\n{algo_name}:")
        print(f"  Errors < 0.5 units:  {len(errors_df[errors_df['error_distance'] < 0.5]):>4} ({len(errors_df[errors_df['error_distance'] < 0.5])/len(errors_df)*100:>5.1f}%)")
        print(f"  Errors < 1.0 units:  {len(errors_df[errors_df['error_distance'] < 1.0]):>4} ({len(errors_df[errors_df['error_distance'] < 1.0])/len(errors_df)*100:>5.1f}%)")
        print(f"  Errors < 2.0 units:  {len(errors_df[errors_df['error_distance'] < 2.0]):>4} ({len(errors_df[errors_df['error_distance'] < 2.0])/len(errors_df)*100:>5.1f}%)")
        print(f"  Errors >= 2.0 units: {len(errors_df[errors_df['error_distance'] >= 2.0]):>4} ({len(errors_df[errors_df['error_distance'] >= 2.0])/len(errors_df)*100:>5.1f}%)")
    
    # AP detection vs accuracy
    print("\n" + "="*70)
    print("📡 AP DETECTION vs ACCURACY (WKNN)")
    print("="*70)
    
    ap_ranges = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 100)]
    for min_ap, max_ap in ap_ranges:
        subset = wknn_errors[(wknn_errors['num_aps'] >= min_ap) & (wknn_errors['num_aps'] <= max_ap)]
        if len(subset) > 0:
            print(f"  {min_ap:2d}-{max_ap:2d} APs: {len(subset):>4} samples, Mean Error: {subset['error_distance'].mean():>5.2f} units")
    
    print("\n" + "="*70)
    print("✅ Evaluation complete!")
    print("="*70)

if __name__ == "__main__":
    main()