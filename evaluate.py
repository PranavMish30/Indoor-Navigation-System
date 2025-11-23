import numpy as np
import pandas as pd
from preprocessing import FingerprintDatabase
from algorithms import KNN, WeightedKNN, RandomForestPositioning
import random
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

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
    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*15 + "📊 INDOOR POSITIONING SYSTEM EVALUATION" + " "*14 + "║")
    print("║" + " "*20 + "BMSIT WiFi Fingerprinting Demo" + " "*18 + "║")
    print("╚" + "═"*68 + "╝")
    
    # Load database
    print("\n┌─ 🔄 SYSTEM INITIALIZATION")
    print("│")
    db = FingerprintDatabase(data_dir='data')
    db.load_all_floors()
    db.create_reference_points()
    print("│  ✓ Database loaded successfully")
    print("│  ✓ Total Samples: {:,}".format(len(db.df)))
    print("│  ✓ Reference Points: {}".format(len(db.reference_points)))
    print("│  ✓ Unique Access Points: {}".format(len(db.all_bssids)))
    print("└─ Ready!")
    
    # Select random test samples (10% of data)
    num_test_samples = int(len(db.df) * 0.1)
    print(f"\n┌─ 🎯 TEST DATASET PREPARATION")
    print(f"│  Selecting {num_test_samples} random samples (10% of dataset)")
    
    test_indices = random.sample(range(len(db.df)), num_test_samples)
    test_samples = db.df.iloc[test_indices]
    
    print(f"│")
    print(f"│  Distribution by Section:")
    for section in test_samples['section'].unique():
        count = len(test_samples[test_samples['section'] == section])
        pct = (count / len(test_samples)) * 100
        bar = "█" * int(pct / 5)
        print(f"│    • {section:10s}: {count:3d} samples [{bar:<20s}] {pct:5.1f}%")
    print("└─ Dataset ready!")
    
    # Initialize algorithms
    print("\n┌─ 🔧 ALGORITHM INITIALIZATION")
    print("│")
    knn = KNN(db.reference_points, db.all_bssids, k=3)
    print("│  ✓ K-Nearest Neighbors (k=3)")
    wknn = WeightedKNN(db.reference_points, db.all_bssids, k=4)
    print("│  ✓ Weighted KNN (k=4)")
    rf = RandomForestPositioning(db.reference_points, db.all_bssids)
    rf.train()
    print("│  ✓ Random Forest (trained)")
    print("└─ All algorithms ready!")
    
    # Evaluate each algorithm
    results = {}
    
    print("\n" + "┌" + "─"*68 + "┐")
    print("│" + " "*15 + "🧪 RUNNING ALGORITHM TESTS" + " "*27 + "│")
    print("└" + "─"*68 + "┘")
    
    print("\n[1/3] Testing K-Nearest Neighbors...")
    results['KNN'], knn_errors = evaluate_algorithm(knn, test_samples, db, 'KNN')
    print("      ✓ Complete!")
    
    print("\n[2/3] Testing Weighted K-Nearest Neighbors...")
    results['WKNN'], wknn_errors = evaluate_algorithm(wknn, test_samples, db, 'WKNN')
    print("      ✓ Complete!")
    
    print("\n[3/3] Testing Random Forest...")
    results['RF'], rf_errors = evaluate_algorithm(rf, test_samples, db, 'Random Forest')
    print("      ✓ Complete!")
    
    # Display results
    print("\n\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*20 + "📊 PERFORMANCE METRICS" + " "*26 + "║")
    print("╚" + "═"*68 + "╝")
    
    # Key metrics showcase
    print("\n┌─ 🎯 ACCURACY METRICS")
    print("│")
    print(f"│  {'Algorithm':<20} {'Floor Accuracy':>15} {'Section Accuracy':>15}")
    print(f"│  {'-'*20} {'-'*15} {'-'*15}")
    for algo_name in ['KNN', 'WKNN', 'RF']:
        floor_acc = results[algo_name]['floor_accuracy']
        section_acc = results[algo_name]['section_accuracy']
        
        # Add visual indicators
        floor_icon = "🟢" if floor_acc >= 95 else "🟡" if floor_acc >= 90 else "🟠"
        section_icon = "🟢" if section_acc >= 85 else "🟡" if section_acc >= 75 else "🟠"
        
        print(f"│  {algo_name:<20} {floor_icon} {floor_acc:>10.1f}%   {section_icon} {section_acc:>10.1f}%")
    print("│")
    
    # Position error metrics
    print("├─ 📏 POSITIONING ERROR (Grid Units)")
    print("│")
    print(f"│  {'Algorithm':<12} {'Mean':>8} {'Median':>8} {'90th %ile':>10} {'95th %ile':>10}")
    print(f"│  {'-'*12} {'-'*8} {'-'*8} {'-'*10} {'-'*10}")
    for algo_name in ['KNN', 'WKNN', 'RF']:
        mean_err = results[algo_name]['mean_error']
        median_err = results[algo_name]['median_error']
        p90 = results[algo_name]['percentile_90']
        p95 = results[algo_name]['percentile_95']
        print(f"│  {algo_name:<12} {mean_err:>8.2f} {median_err:>8.2f} {p90:>10.2f} {p95:>10.2f}")
    print("│")
    
    # Confidence and AP metrics
    print("├─ 📊 SYSTEM STATISTICS")
    print("│")
    print(f"│  {'Algorithm':<15} {'Avg Confidence':>15} {'Avg APs Detected':>18}")
    print(f"│  {'-'*15} {'-'*15} {'-'*18}")
    for algo_name in ['KNN', 'WKNN', 'RF']:
        conf = results[algo_name]['mean_confidence']
        aps = results[algo_name]['mean_aps']
        conf_bar = "█" * int(conf / 10)
        print(f"│  {algo_name:<15} {conf:>10.1f}% [{conf_bar:<10s}] {aps:>6.1f} APs")
    print("└─")
    
    # Find best algorithm
    best_algo = min(results.items(), key=lambda x: x[1]['mean_error'] if x[1] else float('inf'))
    
    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*23 + "🏆 BEST PERFORMING ALGORITHM" + " "*18 + "║")
    print("╠" + "═"*68 + "╣")
    print(f"║  Algorithm:         {best_algo[0]:<47}║")
    print(f"║  Mean Error:        {best_algo[1]['mean_error']:.2f} grid units{' '*31}║")
    print(f"║  Floor Accuracy:    {best_algo[1]['floor_accuracy']:.1f}%{' '*41}║")
    print(f"║  Section Accuracy:  {best_algo[1]['section_accuracy']:.1f}%{' '*41}║")
    print(f"║  Confidence:        {best_algo[1]['mean_confidence']:.1f}%{' '*41}║")
    print("╚" + "═"*68 + "╝")
    
    # Error distribution analysis
    print("\n┌─ 📈 ERROR DISTRIBUTION ANALYSIS")
    print("│")
    
    for algo_name, errors_df in [('KNN', knn_errors), ('WKNN', wknn_errors), ('RF', rf_errors)]:
        print(f"│  {algo_name} Algorithm:")
        
        ranges = [
            ("  Excellent (< 0.5 units)", 0, 0.5),
            ("  Good      (< 1.0 units)", 0, 1.0),
            ("  Fair      (< 2.0 units)", 0, 2.0),
            ("  Poor      (≥ 2.0 units)", 2.0, 999)
        ]
        
        for label, min_err, max_err in ranges:
            if max_err == 999:
                count = len(errors_df[errors_df['error_distance'] >= min_err])
            else:
                count = len(errors_df[errors_df['error_distance'] < max_err])
            pct = (count / len(errors_df)) * 100
            bar = "█" * int(pct / 5)
            print(f"│    {label}: {count:3d} samples [{bar:<20s}] {pct:5.1f}%")
        print("│")
    
    # AP detection vs accuracy
    print("├─ 📡 PERFORMANCE vs ACCESS POINT DETECTION (Best Algorithm)")
    print("│")
    print(f"│  {'AP Range':<15} {'Samples':>10} {'Mean Error':>15} {'Quality':>10}")
    print(f"│  {'-'*15} {'-'*10} {'-'*15} {'-'*10}")
    
    ap_ranges = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 100)]
    for min_ap, max_ap in ap_ranges:
        subset = wknn_errors[(wknn_errors['num_aps'] >= min_ap) & (wknn_errors['num_aps'] <= max_ap)]
        if len(subset) > 0:
            mean_err = subset['error_distance'].mean()
            quality = "Excellent" if mean_err < 0.5 else "Good" if mean_err < 1.0 else "Fair" if mean_err < 2.0 else "Poor"
            quality_icon = "🟢" if mean_err < 1.0 else "🟡" if mean_err < 2.0 else "🟠"
            print(f"│  {min_ap:2d}-{max_ap:2d} APs{' '*7} {len(subset):>10} {mean_err:>12.2f} units  {quality_icon} {quality}")
    print("└─")
    
    # Summary statistics box
    print("\n╔" + "═"*68 + "╗")
    print("║" + " "*22 + "📋 EVALUATION SUMMARY" + " "*26 + "║")
    print("╠" + "═"*68 + "╣")
    print(f"║  Total Tests Conducted:    {results['WKNN']['num_tests']:<39}║")
    print(f"║  Dataset Coverage:         10% random sampling{' '*22}║")
    print(f"║  Algorithms Evaluated:     3 (KNN, WKNN, Random Forest){' '*11}║")
    print(f"║  Best Algorithm:           {best_algo[0]:<39}║")
    print(f"║  Best Mean Error:          {best_algo[1]['mean_error']:.2f} grid units{' '*29}║")
    print(f"║  Best Floor Accuracy:      {best_algo[1]['floor_accuracy']:.1f}%{' '*39}║")
    print("╚" + "═"*68 + "╝")
    
    print("\n✅ Evaluation Complete! System ready for demo presentation.\n")
    
    # Generate visualizations
    print("\n" + "┌" + "─"*68 + "┐")
    print("│" + " "*18 + "📊 GENERATING VISUALIZATIONS" + " "*22 + "│")
    print("└" + "─"*68 + "┘\n")
    
    # Set up the plotting style
    plt.style.use('seaborn-v0_8-darkgrid')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create a figure with multiple subplots
    fig = plt.figure(figsize=(20, 12))
    fig.suptitle('BMSIT Indoor Positioning System - Algorithm Evaluation Results', 
                 fontsize=20, fontweight='bold', y=0.995)
    
    # 1. Algorithm Comparison - Accuracy Metrics (Top Left)
    ax1 = plt.subplot(2, 3, 1)
    algorithms = ['KNN', 'WKNN', 'RF']
    floor_acc = [results[algo]['floor_accuracy'] for algo in algorithms]
    section_acc = [results[algo]['section_accuracy'] for algo in algorithms]
    
    x = np.arange(len(algorithms))
    width = 0.35
    bars1 = ax1.bar(x - width/2, floor_acc, width, label='Floor Accuracy', 
                     color='#4CAF50', alpha=0.8)
    bars2 = ax1.bar(x + width/2, section_acc, width, label='Section Accuracy', 
                     color='#2196F3', alpha=0.8)
    
    ax1.set_ylabel('Accuracy (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Algorithm Accuracy Comparison', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(algorithms)
    ax1.legend(loc='lower right')
    ax1.set_ylim([0, 100])
    ax1.grid(axis='y', alpha=0.3)
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%', ha='center', va='bottom', fontsize=9)
    
    # 2. Positioning Error Comparison (Top Middle)
    ax2 = plt.subplot(2, 3, 2)
    mean_errors = [results[algo]['mean_error'] for algo in algorithms]
    median_errors = [results[algo]['median_error'] for algo in algorithms]
    
    x = np.arange(len(algorithms))
    bars1 = ax2.bar(x - width/2, mean_errors, width, label='Mean Error', 
                     color='#FF9800', alpha=0.8)
    bars2 = ax2.bar(x + width/2, median_errors, width, label='Median Error', 
                     color='#F44336', alpha=0.8)
    
    ax2.set_ylabel('Error (Grid Units)', fontsize=12, fontweight='bold')
    ax2.set_title('Positioning Error Comparison', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(algorithms)
    ax2.legend(loc='upper right')
    ax2.grid(axis='y', alpha=0.3)
    
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}', ha='center', va='bottom', fontsize=9)
    
    # 3. Error Distribution (Top Right)
    ax3 = plt.subplot(2, 3, 3)
    colors = ['#4CAF50', '#2196F3', '#9C27B0']
    
    for idx, (algo_name, errors_df) in enumerate([('KNN', knn_errors), 
                                                    ('WKNN', wknn_errors), 
                                                    ('RF', rf_errors)]):
        ax3.hist(errors_df['error_distance'], bins=30, alpha=0.6, 
                label=algo_name, color=colors[idx], edgecolor='black')
    
    ax3.set_xlabel('Error Distance (Grid Units)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Frequency', fontsize=12, fontweight='bold')
    ax3.set_title('Error Distribution', fontsize=14, fontweight='bold')
    ax3.legend()
    ax3.grid(axis='y', alpha=0.3)
    
    # 4. Cumulative Error Distribution (Bottom Left)
    ax4 = plt.subplot(2, 3, 4)
    
    for idx, (algo_name, errors_df) in enumerate([('KNN', knn_errors), 
                                                    ('WKNN', wknn_errors), 
                                                    ('RF', rf_errors)]):
        sorted_errors = np.sort(errors_df['error_distance'])
        cumulative = np.arange(1, len(sorted_errors) + 1) / len(sorted_errors) * 100
        ax4.plot(sorted_errors, cumulative, label=algo_name, 
                linewidth=2.5, color=colors[idx])
    
    ax4.set_xlabel('Error Distance (Grid Units)', fontsize=12, fontweight='bold')
    ax4.set_ylabel('Cumulative Percentage (%)', fontsize=12, fontweight='bold')
    ax4.set_title('Cumulative Error Distribution (CDF)', fontsize=14, fontweight='bold')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim([0, 5])
    
    # Add reference lines
    ax4.axhline(y=90, color='gray', linestyle='--', alpha=0.5, label='90th percentile')
    ax4.axhline(y=95, color='gray', linestyle=':', alpha=0.5, label='95th percentile')
    
    # 5. AP Detection vs Error (Bottom Middle)
    ax5 = plt.subplot(2, 3, 5)
    
    ap_ranges_plot = ['1-5', '6-10', '11-15', '16-20', '21+']
    ap_ranges = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 100)]
    
    for idx, (algo_name, errors_df) in enumerate([('KNN', knn_errors), 
                                                    ('WKNN', wknn_errors), 
                                                    ('RF', rf_errors)]):
        mean_errors_by_ap = []
        for min_ap, max_ap in ap_ranges:
            subset = errors_df[(errors_df['num_aps'] >= min_ap) & 
                              (errors_df['num_aps'] <= max_ap)]
            if len(subset) > 0:
                mean_errors_by_ap.append(subset['error_distance'].mean())
            else:
                mean_errors_by_ap.append(0)
        
        ax5.plot(ap_ranges_plot, mean_errors_by_ap, marker='o', 
                linewidth=2.5, markersize=8, label=algo_name, color=colors[idx])
    
    ax5.set_xlabel('Number of Access Points Detected', fontsize=12, fontweight='bold')
    ax5.set_ylabel('Mean Error (Grid Units)', fontsize=12, fontweight='bold')
    ax5.set_title('Performance vs AP Detection', fontsize=14, fontweight='bold')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    
    # 6. Algorithm Performance Summary (Bottom Right)
    ax6 = plt.subplot(2, 3, 6)
    ax6.axis('off')
    
    # Create summary table
    summary_data = []
    for algo in algorithms:
        summary_data.append([
            algo,
            f"{results[algo]['floor_accuracy']:.1f}%",
            f"{results[algo]['section_accuracy']:.1f}%",
            f"{results[algo]['mean_error']:.2f}",
            f"{results[algo]['percentile_90']:.2f}",
            f"{results[algo]['mean_confidence']:.1f}%"
        ])
    
    table = ax6.table(cellText=summary_data,
                     colLabels=['Algorithm', 'Floor Acc', 'Section Acc', 
                               'Mean Error', '90th %ile', 'Confidence'],
                     cellLoc='center',
                     loc='center',
                     colWidths=[0.15, 0.15, 0.15, 0.15, 0.15, 0.15])
    
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 3)
    
    # Style the table
    for i in range(len(algorithms) + 1):
        for j in range(6):
            cell = table[(i, j)]
            if i == 0:  # Header row
                cell.set_facecolor('#667eea')
                cell.set_text_props(weight='bold', color='white')
            else:
                if j == 0:  # Algorithm names
                    cell.set_facecolor('#e3f2fd')
                    cell.set_text_props(weight='bold')
                else:
                    cell.set_facecolor('#f5f5f5')
    
    ax6.set_title('Performance Summary Table', fontsize=14, fontweight='bold', pad=20)
    
    # Adjust layout and save
    plt.tight_layout()
    
    # Save the figure
    filename = f'evaluation_results_{timestamp}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved comprehensive visualization: {filename}")
    
    # Create individual focused plots
    
    # Box plot comparison
    fig2, ax = plt.subplots(figsize=(10, 6))
    data_to_plot = [knn_errors['error_distance'], 
                    wknn_errors['error_distance'], 
                    rf_errors['error_distance']]
    
    bp = ax.boxplot(data_to_plot, labels=algorithms, patch_artist=True,
                    medianprops=dict(color='red', linewidth=2),
                    boxprops=dict(facecolor='lightblue', alpha=0.7),
                    whiskerprops=dict(linewidth=1.5),
                    capprops=dict(linewidth=1.5))
    
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    
    ax.set_ylabel('Error Distance (Grid Units)', fontsize=12, fontweight='bold')
    ax.set_title('Algorithm Error Distribution - Box Plot Comparison', 
                fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    
    filename2 = f'boxplot_comparison_{timestamp}.png'
    plt.savefig(filename2, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved box plot comparison: {filename2}")
    
    # Best algorithm spotlight
    fig3, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    fig3.suptitle(f'Best Algorithm Spotlight: {best_algo[0]}', 
                 fontsize=16, fontweight='bold')
    
    best_errors = wknn_errors if best_algo[0] == 'WKNN' else (knn_errors if best_algo[0] == 'KNN' else rf_errors)
    
    # Error histogram
    ax1.hist(best_errors['error_distance'], bins=30, color='#2196F3', 
            alpha=0.7, edgecolor='black')
    ax1.axvline(best_errors['error_distance'].mean(), color='red', 
               linestyle='--', linewidth=2, label=f"Mean: {best_errors['error_distance'].mean():.2f}")
    ax1.axvline(best_errors['error_distance'].median(), color='green', 
               linestyle='--', linewidth=2, label=f"Median: {best_errors['error_distance'].median():.2f}")
    ax1.set_xlabel('Error Distance (Grid Units)', fontweight='bold')
    ax1.set_ylabel('Frequency', fontweight='bold')
    ax1.set_title('Error Distribution', fontweight='bold')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Scatter plot: APs vs Error
    ax2.scatter(best_errors['num_aps'], best_errors['error_distance'], 
               alpha=0.5, c=best_errors['error_distance'], cmap='RdYlGn_r', s=50)
    ax2.set_xlabel('Number of APs Detected', fontweight='bold')
    ax2.set_ylabel('Error Distance (Grid Units)', fontweight='bold')
    ax2.set_title('AP Detection vs Positioning Error', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    # Confidence distribution
    ax3.hist(best_errors['confidence'], bins=20, color='#4CAF50', 
            alpha=0.7, edgecolor='black')
    ax3.set_xlabel('Confidence (%)', fontweight='bold')
    ax3.set_ylabel('Frequency', fontweight='bold')
    ax3.set_title('Confidence Distribution', fontweight='bold')
    ax3.grid(axis='y', alpha=0.3)
    
    # Floor and Section accuracy pie charts
    floor_correct = sum(best_errors['floor_correct'])
    floor_incorrect = len(best_errors) - floor_correct
    section_correct = sum(best_errors['section_correct'])
    section_incorrect = len(best_errors) - section_correct
    
    ax4.clear()
    ax4.axis('off')
    
    # Create two small pie charts
    pie1_ax = fig3.add_axes([0.58, 0.15, 0.15, 0.15])
    pie1_ax.pie([floor_correct, floor_incorrect], 
                labels=['Correct', 'Incorrect'],
                autopct='%1.1f%%', colors=['#4CAF50', '#F44336'],
                startangle=90)
    pie1_ax.set_title('Floor Accuracy', fontweight='bold', fontsize=10)
    
    pie2_ax = fig3.add_axes([0.78, 0.15, 0.15, 0.15])
    pie2_ax.pie([section_correct, section_incorrect],
                labels=['Correct', 'Incorrect'],
                autopct='%1.1f%%', colors=['#2196F3', '#FF9800'],
                startangle=90)
    pie2_ax.set_title('Section Accuracy', fontweight='bold', fontsize=10)
    
    plt.tight_layout()
    filename3 = f'best_algorithm_spotlight_{timestamp}.png'
    plt.savefig(filename3, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved best algorithm spotlight: {filename3}")
    
    print(f"\n📊 All visualizations saved successfully!")
    print(f"   Generated {3} detailed charts for demo presentation\n")

if __name__ == "__main__":
    main()