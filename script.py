import subprocess
import json
from datetime import datetime
import re
import os

def scan_wifi():
    """Scan WiFi for networks starting with 'BMSIT-' on Windows."""
    print("🔍 Attempting WiFi scan on Windows with SSID filtering (Prefix: 'BMSIT')...")
    
    try:
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print(f"❌ netsh error: {result.stderr}")
            return None
        
        print(f"📡 Raw netsh output (first 1000 chars):\n{result.stdout[:1000]}\n")
        
        aps = {}
        lines = result.stdout.split('\n')
        current_ssid = None
        current_bssid = None
        
        for line in lines:
            line = line.strip()
            
            # Extract SSID
            if line.startswith('SSID') and ':' in line and 'BSSID' not in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current_ssid = parts[1].strip()
            
            # Extract BSSID
            elif 'BSSID' in line and ':' in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    # BSSID format: "BSSID 1 : aa:bb:cc:dd:ee:ff"
                    bssid_part = parts[1].strip()
                    # Extract actual MAC address
                    mac_match = re.search(r'([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})', bssid_part)
                    if mac_match:
                        current_bssid = mac_match.group(1)
            
            # Filter by SSID starting with "BMSIT" and Extract Signal
            elif 'Signal' in line and ':' in line and current_bssid and current_ssid:
                parts = line.split(':', 1)
                if len(parts) > 1 and current_ssid.startswith("BMSIT"):
                    signal_str = parts[1].strip().replace('%', '')
                    try:
                        signal_percent = int(signal_str)
                        # Convert percentage to approximate dBm
                        # 100% ≈ -50 dBm, 0% ≈ -100 dBm
                        signal_dbm = int((signal_percent / 2) - 100)
                        
                        # Use "BSSID|ESSID" as JSON-safe string keys
                        json_safe_key = f"{current_bssid}|{current_ssid}"
                        aps[json_safe_key] = signal_dbm
                        print(f"   Found: {json_safe_key} = {signal_dbm} dBm")
                        current_bssid = None  # Reset for next AP
                    except ValueError:
                        print(f"   ⚠️ Invalid signal value: {signal_str}")
        
        return aps if aps else None
        
    except FileNotFoundError:
        print("❌ netsh command not found. Are you on Windows?")
        return None
    except Exception as e:
        print(f"❌ Error with netsh: {e}")
        return None
    
def collect_fingerprint(floor, section, x, y, num_samples=50, interval=1):
    """Collect multiple RSSI samples at a reference point."""
    
    print(f"\n📍 Collecting data at Floor {floor}, Section {section}, Position ({x}, {y})...")
    print(f"   Collecting {num_samples} samples with {interval} second interval.")
    
    all_samples = []
    
    for i in range(num_samples):
        print(f"Sample {i+1}/{num_samples}...", end='\r')
        
        # Perform scan
        aps = scan_wifi()
        
        # Prepare sample entry
        sample = {
            'timestamp': datetime.now().isoformat(),
            'floor': floor,
            'section': section,
            'x': x,
            'y': y,
            'sample_num': i,
            'networks': aps
        }
        
        # Add the sample to the list
        all_samples.append(sample)
    
    print("\n✅ Data collection complete!")
    return all_samples

def save_to_json(samples, filename='fingerprint_data.json'):
    """Save collected data to a JSON file."""
    existing_data = []
    if os.path.isfile(filename):
        try:
            with open(filename, 'r') as f:
                # Load existing data from the file
                existing_data = json.load(f)
        except json.JSONDecodeError:
            # Handle file corruption or invalid JSON gracefully
            print(f"⚠️ Warning: The file '{filename}' contains invalid JSON. Starting fresh.")
            existing_data = []
    
    # Add new samples to the existing data list
    existing_data.extend(samples)  # This merges previous and new data
    
    # Write the updated combined data back to the JSON file
    with open(filename, 'w') as f:
        json.dump(existing_data, f, indent=2)  # Pretty-printing with `indent=2`
    
    print(f"✅ Successfully saved {len(samples)} new samples to '{filename}'.")

def main():
    """Main function."""
    print("\n" + "="*70)
    print("📡 WiFi RSSI Data Collection Tool (Windows)")
    print("="*70)
    
    floor = input("Enter floor number (1, 2, etc.): ")
    section = input("Enter section (e.g., left, right, corridor): ")
    x = float(input("Enter X coordinate: "))
    y = float(input("Enter Y coordinate: "))
    num_samples = int(input("Number of samples (default: 50): ") or 100)
    interval = float(input("Interval between samples in seconds (default: 1): ") or 1)
    
    # Collect WiFi data
    samples = collect_fingerprint(floor, section, x, y, num_samples, interval)
    
    # Save to files
    save_to_json(samples, 'fingerprint_data.json')

if __name__ == "__main__":
    main()