import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import re
import os

from preprocessing import FingerprintDatabase
from algorithms import KNN, WeightedKNN, RandomForestPositioning, HybridWKNNRF
from navigation import build_graph, find_closest_node, shortest_path

app = Flask(__name__, static_folder='static')
CORS(app)

db = None
knn_algo = None
wknn_algo = None
rf_algo = None
hybrid_algo = None
nav_graph = None

# LOAD POIs from floor_plan.json at startup
with open('pois.json', 'r', encoding='utf-8') as f:
    POIS = json.load(f)

def initialize_system():
    global db, knn_algo, wknn_algo, rf_algo, hybrid_algo, nav_graph
    print("\n" + "="*70)
    print("🚀 Initializing Indoor Positioning System")
    print("="*70)

    db = FingerprintDatabase(data_dir='data')
    db.load_all_floors()
    db.create_reference_points()
    db.get_stats()
    print("\n🔧 Initializing positioning algorithms...")
    knn_algo = KNN(db.reference_points, db.all_bssids, k=3)
    wknn_algo = WeightedKNN(db.reference_points, db.all_bssids, k=4)
    rf_algo = RandomForestPositioning(db.reference_points, db.all_bssids)
    hybrid_algo = HybridWKNNRF(db.reference_points, db.all_bssids, k=4)
    nav_graph = build_graph(db.reference_points, pois=POIS)
    print("✅ System initialized successfully!")
    print("="*70 + "\n")

initialize_system()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'total_reference_points': len(db.reference_points),
        'total_bssids': len(db.all_bssids),
        'floors': sorted(db.reference_points['floor'].unique().tolist()),
        'sections': sorted(db.reference_points['section'].unique().tolist()),
        'algorithms': ['knn', 'wknn', 'rf', 'hybrid']
    })

@app.route('/api/scan', methods=['GET'])
def scan_wifi():
    try:
        import platform
        if platform.system() != 'Windows':
            return jsonify({'error': 'WiFi scan is only supported on Windows hosts.'}), 501
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return jsonify({'error': 'netsh command failed. Are you on WiFi?'}), 500
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
                        continue
        return jsonify({
            'aps': aps,
            'count': len(aps)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/locate', methods=['POST'])
def locate():
    data = request.json
    current_scan = data.get('scan', {})
    algorithm = data.get('algorithm', 'wknn')
    if not current_scan:
        return jsonify({'error': 'No WiFi scan data provided'}), 400
    current_scan = {str(k): int(v) for k, v in current_scan.items()}
    try:
        if algorithm == 'knn':
            result = knn_algo.estimate_position(current_scan)
        elif algorithm == 'wknn':
            result = wknn_algo.estimate_position(current_scan)
        elif algorithm == 'rf':
            result = rf_algo.estimate_position(current_scan)
        elif algorithm == 'hybrid':
            result = hybrid_algo.estimate_position(current_scan)
        else:
            return jsonify({'error': f'Unknown algorithm: {algorithm}'}), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reference-points', methods=['GET'])
def get_reference_points():
    floor = request.args.get('floor', type=int)
    if floor is not None:
        points = db.reference_points[db.reference_points['floor'] == floor]
    else:
        points = db.reference_points
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
    return jsonify({
        'bssids': db.all_bssids,
        'count': len(db.all_bssids)
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
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

# --- Navigation Endpoints using POIs from floor_plan.json ---

@app.route('/api/destinations', methods=['GET'])
def list_destinations():
    result = []
    for label, info in POIS.items():
        result.append({
            "label": label,
            "floor": info["floor"],
            "x": info["x"],
            "y": info["y"],
            "type": info.get("type", ""),
            "side": info.get("side", "")
        })
    return jsonify(result)

@app.route('/api/navigate', methods=['POST'])
def api_navigate():
    data = request.json
    current = data.get('current')
    dest_label = data.get('destination_label')
    if current is None or dest_label is None:
        return jsonify({"error": "current and destination_label required"}), 400
    dest_info = POIS.get(dest_label)
    if not dest_info:
        return jsonify({"error": "Destination not found"}), 404
    # Find graph nodes closest to user and destination
    start = find_closest_node(nav_graph, int(current['floor']), float(current['x']), float(current['y']))
    goal = find_closest_node(nav_graph, int(dest_info['floor']), float(dest_info['x']), float(dest_info['y']))
    path = shortest_path(nav_graph, start, goal)
    response = [{"floor": n[0], "x": n[1], "y": n[2]} for n in path]
    return jsonify({"path": response})

if __name__ == '__main__':
    print("\n🌐 Starting Indoor Positioning Server")
    print("   Server: http://localhost:5000")
    print("   Press Ctrl+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=5000)