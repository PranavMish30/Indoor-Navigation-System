from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import subprocess
import re

from preprocessing import FingerprintDatabase
from algorithms import KNN, WeightedKNN, RandomForestPositioning

app = Flask(__name__, static_folder='static')
CORS(app)

# Global variables
db = None
knn_algo = None
wknn_algo = None
rf_algo = None

def initialize_system():
    """Initialize the positioning system"""
    global db, knn_algo, wknn_algo, rf_algo
    
    print("\n" + "="*70)
    print("🚀 Initializing BMSIT Indoor Positioning System")
    print("="*70)
    
    # Load fingerprint database
    db = FingerprintDatabase(data_dir='data')
    db.load_all_floors()
    db.create_reference_points()
    db.get_stats()
    
    # Initialize algorithms
    print("\n🔧 Initializing positioning algorithms...")
    knn_algo = KNN(db.reference_points, db.all_bssids, k=3)
    wknn_algo = WeightedKNN(db.reference_points, db.all_bssids, k=4)
    
    # Initialize Random Forest
    try:
        rf_algo = RandomForestPositioning(db.reference_points, db.all_bssids)
        rf_algo.train()
    except ImportError:
        print("⚠️ scikit-learn not installed. Random Forest disabled.")
        rf_algo = None
    
    print("✅ System initialized successfully!")
    print("="*70 + "\n")

# Initialize on startup
initialize_system()

@app.route('/')
def index():
    """Serve the main webapp"""
    return send_from_directory('static', 'index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'total_reference_points': len(db.reference_points),
        'total_bssids': len(db.all_bssids),
        'floors': sorted(db.reference_points['floor'].unique().tolist()),
        'sections': sorted(db.reference_points['section'].unique().tolist()),
        'algorithms': ['knn', 'wknn'] + (['rf'] if rf_algo else [])
    })

@app.route('/api/scan', methods=['GET'])
def scan_wifi():
    """Scan WiFi networks on server (Windows)"""
    try:
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return jsonify({'error': 'WiFi scan failed'}), 500
        
        aps = {}
        lines = result.stdout.split('\n')
        current_ssid = None
        current_bssid = None
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('SSID') and ':' in line and 'BSSID' not in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current_ssid = parts[1].strip()
            
            elif 'BSSID' in line and ':' in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    bssid_part = parts[1].strip()
                    mac_match = re.search(r'([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})', bssid_part)
                    if mac_match:
                        current_bssid = mac_match.group(1).lower()
            
            elif 'Signal' in line and ':' in line and current_bssid and current_ssid:
                parts = line.split(':', 1)
                if len(parts) > 1 and current_ssid.startswith("BMSIT"):
                    signal_str = parts[1].strip().replace('%', '')
                    try:
                        signal_percent = int(signal_str)
                        signal_dbm = int((signal_percent / 2) - 100)
                        
                        json_safe_key = f"{current_bssid}|{current_ssid}"
                        aps[json_safe_key] = signal_dbm
                        current_bssid = None
                    except ValueError:
                        pass
        
        return jsonify({
            'aps': aps,
            'count': len(aps)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/locate', methods=['POST'])
def locate():
    """Main positioning endpoint"""
    
    data = request.json
    
    # Extract current WiFi scan from request
    current_scan = data.get('scan', {})
    algorithm = data.get('algorithm', 'wknn')  # default to wknn
    
    if not current_scan:
        return jsonify({'error': 'No WiFi scan data provided'}), 400
    
    # Convert to correct format
    current_scan = {str(k): int(v) for k, v in current_scan.items()}
    
    print(f"\n📍 Positioning request:")
    print(f"   Algorithm: {algorithm}")
    print(f"   APs detected: {len(current_scan)}")
    
    # Select algorithm
    try:
        if algorithm == 'knn':
            result = knn_algo.estimate_position(current_scan)
        elif algorithm == 'wknn':
            result = wknn_algo.estimate_position(current_scan)
        elif algorithm == 'rf' and rf_algo:
            result = rf_algo.estimate_position(current_scan)
        else:
            return jsonify({'error': f'Unknown algorithm: {algorithm}'}), 400
        
        print(f"   Result: Floor {result['floor']}, Section '{result['section']}', ({result['x']:.2f}, {result['y']:.2f})")
        print(f"   Confidence: {result['confidence']:.1f}%")
        
        return jsonify(result)
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reference-points', methods=['GET'])
def get_reference_points():
    """Get all reference points for visualization"""
    
    floor = request.args.get('floor', type=int)
    
    if floor is not None:
        points = db.reference_points[db.reference_points['floor'] == floor]
    else:
        points = db.reference_points
    
    # Convert to list of dicts
    result = []
    for idx, point in points.iterrows():
        result.append({
            'floor': int(point['floor']),
            'section': point['section'],
            'x': float(point['x']),
            'y': float(point['y']),
            'num_samples': int(point.get('num_samples', 0))
        })
    
    return jsonify(result)

@app.route('/api/bssids', methods=['GET'])
def get_bssids():
    """Get list of all known BSSIDs"""
    return jsonify({
        'bssids': db.all_bssids,
        'count': len(db.all_bssids)
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    return jsonify({
        'total_reference_points': len(db.reference_points),
        'total_bssids': len(db.all_bssids),
        'floors': sorted(db.reference_points['floor'].unique().tolist()),
        'sections': sorted(db.reference_points['section'].unique().tolist()),
        'reference_points_by_section': {
            section: len(db.reference_points[db.reference_points['section'] == section])
            for section in db.reference_points['section'].unique()
        }
    })

if __name__ == '__main__':
    print("\n🌐 Starting BMSIT Indoor Positioning Server")
    print("   Server: http://localhost:5000")
    print("   Press Ctrl+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=5000)