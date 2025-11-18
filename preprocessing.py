import pandas as pd
import numpy as np
import json
import os
import sqlite3

class FingerprintDatabase:
    """Load, process, and query fingerprint data for BMSIT campus"""
    
    def __init__(self, data_dir='data'):
        self.data_dir = data_dir
        self.df = None
        self.reference_points = None
        self.all_bssids = None
        
        # Your coordinate system: grid coordinates
        # Left: X=0-2, Y=0-3 (3×4 = 12 points)
        # Corridor: X=3-19, Y=2.5 (17 points)
        # Right: X=20-22, Y=0-3 (3×4 = 12 points)
    
    def load_from_json(self, filename):
        """Load fingerprint data from JSON"""
        filepath = os.path.join(self.data_dir, filename)
        print(f"📂 Loading data from {filepath}...")
        
        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            return self
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        print(f"✅ Loaded {len(data)} samples")
        
        # Convert to DataFrame
        rows = []
        for sample in data:
            row = {
                'timestamp': sample['timestamp'],
                'floor': int(sample['floor']),  # Convert "0" to 0
                'section': sample['section'],
                'x': float(sample['x']),  # Grid coordinate
                'y': float(sample['y']),  # Grid coordinate
                'sample_num': sample['sample_num']
            }
            
            # Handle both 'networks' and 'rssi' field names
            rssi_data = sample.get('rssi', sample.get('networks', {}))
            
            # Add RSSI values
            row.update(rssi_data)
            
            rows.append(row)
        
        self.df = pd.DataFrame(rows)
        
        # Identify BSSID columns (format: "xx:xx:xx:xx:xx:xx|BMSIT-XXX")
        metadata_cols = ['timestamp', 'floor', 'section', 'x', 'y', 'sample_num']
        self.all_bssids = [col for col in self.df.columns if col not in metadata_cols]
        
        print(f"📡 Detected {len(self.all_bssids)} unique BSSIDs")
        
        # Show network breakdown
        self._show_network_breakdown()
        
        return self
    
    def _show_network_breakdown(self):
        """Show breakdown of BMSIT network types"""
        if not self.all_bssids:
            return
        
        student_aps = [b for b in self.all_bssids if 'Student' in b]
        faculty_aps = [b for b in self.all_bssids if 'Faculty' in b]
        wifi_aps = [b for b in self.all_bssids if 'WiFi' in b]
        
        print(f"\n📊 BMSIT Network Breakdown:")
        print(f"   BMSIT-Student:  {len(student_aps):3d} APs")
        print(f"   BMSIT-Faculty:  {len(faculty_aps):3d} APs")
        print(f"   BMSIT_WiFi:     {len(wifi_aps):3d} APs")
        print(f"   ─────────────────────────")
        print(f"   Total:          {len(self.all_bssids):3d} APs")
    
    def load_all_floors(self):
        """Load data from all floor files"""
        all_dfs = []
        
        # Try to load floor 0, 1, 2, etc.
        for floor_num in [0, 1, 2]:
            filename = f'fingerprints_floor{floor_num}.json'
            filepath = os.path.join(self.data_dir, filename)
            
            if os.path.exists(filepath):
                print(f"\n{'='*70}")
                print(f"📂 Loading Floor {floor_num} data...")
                print(f"{'='*70}")
                
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                rows = []
                for sample in data:
                    row = {
                        'timestamp': sample['timestamp'],
                        'floor': int(sample['floor']),
                        'section': sample['section'],
                        'x': float(sample['x']),
                        'y': float(sample['y']),
                        'sample_num': sample['sample_num']
                    }
                    
                    # Handle both field names
                    rssi_data = sample.get('rssi', sample.get('networks', {}))
                    row.update(rssi_data)
                    
                    rows.append(row)
                
                df_temp = pd.DataFrame(rows)
                all_dfs.append(df_temp)
                
                # Show stats for this floor
                sections = df_temp['section'].value_counts()
                unique_points = df_temp.groupby(['section', 'x', 'y']).size()
                
                print(f"✅ Floor {floor_num}: {len(df_temp)} samples")
                print(f"   Sections: {dict(sections)}")
                print(f"   Reference points: {len(unique_points)}")
        
        if all_dfs:
            self.df = pd.concat(all_dfs, ignore_index=True)
            
            print(f"\n{'='*70}")
            print(f"📦 COMBINED DATA")
            print(f"{'='*70}")
            print(f"✅ Total samples: {len(self.df)}")
            
            metadata_cols = ['timestamp', 'floor', 'section', 'x', 'y', 'sample_num']
            self.all_bssids = [col for col in self.df.columns if col not in metadata_cols]
            print(f"📡 Total unique BSSIDs: {len(self.all_bssids)}")
            
            self._show_network_breakdown()
        else:
            print("❌ No fingerprint data files found in 'data' folder!")
        
        return self
    
    def create_reference_points(self):
        """Create averaged fingerprint for each reference point"""
        print(f"\n{'='*70}")
        print("🔄 Creating Reference Point Database...")
        print(f"{'='*70}")
        
        # Group by location and average RSSI values
        grouped = self.df.groupby(['floor', 'section', 'x', 'y'])
        
        reference_data = []
        
        for (floor, section, x, y), group in grouped:
            ref_point = {
                'floor': floor,
                'section': section,
                'x': x,
                'y': y,
                'num_samples': len(group)
            }
            
            # Average RSSI for each BSSID
            for bssid in self.all_bssids:
                if bssid in group.columns:
                    # Convert to numeric and drop NaN/missing values
                    values = pd.to_numeric(group[bssid], errors='coerce').dropna()
                    if len(values) > 0:
                        ref_point[bssid] = values.mean()
            
            reference_data.append(ref_point)
        
        self.reference_points = pd.DataFrame(reference_data)
        
        print(f"✅ Created {len(self.reference_points)} reference points\n")
        
        # Show detailed breakdown by floor and section
        for floor in sorted(self.reference_points['floor'].unique()):
            floor_data = self.reference_points[self.reference_points['floor'] == floor]
            print(f"Floor {floor}:")
            
            for section in ['left', 'corridor', 'right']:
                section_data = floor_data[floor_data['section'] == section]
                if len(section_data) > 0:
                    samples = section_data['num_samples']
                    print(f"  {section:10s}: {len(section_data):2d} points "
                          f"({samples.min()}-{samples.max()} samples each)")
        
        return self
    
    def get_rssi_vector(self, location_data):
        """Extract RSSI vector for a given location"""
        rssi_vector = []
        for bssid in self.all_bssids:
            rssi_vector.append(location_data.get(bssid, -100))  # -100 for missing
        return np.array(rssi_vector)
    
    def save_to_sqlite(self, db_name='fingerprints.db'):
        """Save reference points to SQLite database"""
        db_path = os.path.join(self.data_dir, db_name)
        conn = sqlite3.connect(db_path)
        
        # Save reference points
        self.reference_points.to_sql('reference_points', conn, if_exists='replace', index=False)
        
        # Save BSSID list
        bssid_df = pd.DataFrame({'bssid': self.all_bssids})
        bssid_df.to_sql('bssids', conn, if_exists='replace', index=False)
        
        conn.close()
        print(f"\n💾 Saved to database: {db_path}")
    
    def get_stats(self):
        """Get comprehensive statistics"""
        stats = {
            'total_samples': len(self.df),
            'total_reference_points': len(self.reference_points) if self.reference_points is not None else 0,
            'total_bssids': len(self.all_bssids),
            'floors': sorted(self.df['floor'].unique().tolist()),
            'sections': sorted(self.df['section'].unique().tolist())
        }
        
        print(f"\n{'='*70}")
        print("📊 DATABASE STATISTICS")
        print(f"{'='*70}")
        print(f"Total samples collected:    {stats['total_samples']:,}")
        print(f"Reference points:           {stats['total_reference_points']}")
        print(f"Unique BSSIDs (APs):        {stats['total_bssids']}")
        print(f"Floors:                     {stats['floors']}")
        print(f"Sections:                   {stats['sections']}")
        
        if len(self.df) > 0:
            # Samples per reference point
            samples_per_point = self.df.groupby(['floor', 'section', 'x', 'y']).size()
            print(f"\nSamples per reference point:")
            print(f"  Min:     {samples_per_point.min()}")
            print(f"  Max:     {samples_per_point.max()}")
            print(f"  Mean:    {samples_per_point.mean():.1f}")
            print(f"  Median:  {samples_per_point.median():.0f}")
        
        print(f"{'='*70}\n")
        
        return stats

# Test the preprocessing
if __name__ == "__main__":
    # Make sure data directory exists
    if not os.path.exists('data'):
        print("❌ 'data' folder not found!")
        print("   Please run convert_data.py first to convert your data.")
        exit(1)
    
    print("\n" + "="*70)
    print("🚀 BMSIT Indoor Positioning - Data Preprocessing")
    print("="*70)
    
    db = FingerprintDatabase(data_dir='data')
    db.load_all_floors()
    
    if db.df is not None and len(db.df) > 0:
        db.create_reference_points()
        db.get_stats()
        db.save_to_sqlite('fingerprints.db')
        
        print("\n✅ Preprocessing complete!")
        print("   Next step: Run algorithms.py to test positioning")
    else:
        print("\n❌ No data loaded. Please check your data files.")