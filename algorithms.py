import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from scipy.spatial.distance import euclidean

class PositioningAlgorithm:
    """Base class for positioning algorithms"""
    
    def __init__(self, reference_points: pd.DataFrame, all_bssids: List[str]):
        self.reference_points = reference_points
        self.all_bssids = all_bssids
        print(f"🔧 Initialized with {len(reference_points)} reference points and {len(all_bssids)} BSSIDs")
    
    def prepare_rssi_vector(self, current_scan: Dict[str, int]) -> np.ndarray:
        """Convert current WiFi scan to RSSI vector"""
        rssi_vector = []
        for bssid in self.all_bssids:
            value = current_scan.get(bssid, -100)
            # Ensure the value is valid
            if pd.isna(value) or value is None:
                rssi_vector.append(-100)
            else:
                try:
                    rssi_vector.append(float(value))
                except (ValueError, TypeError):
                    rssi_vector.append(-100)
        return np.array(rssi_vector)
    
    def get_reference_rssi_vector(self, ref_point: pd.Series) -> np.ndarray:
        """Extract RSSI vector from reference point"""
        rssi_vector = []
        for bssid in self.all_bssids:
            value = ref_point.get(bssid, -100)
            # Handle NaN, None, or missing values
            if pd.isna(value) or value is None:
                rssi_vector.append(-100)  # Use -100 for missing APs
            else:
                try:
                    rssi_vector.append(float(value))
                except (ValueError, TypeError):
                    rssi_vector.append(-100)
        return np.array(rssi_vector)
    
    def calculate_distance(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate Euclidean distance between RSSI vectors"""
        # Double-check for NaN/Inf values
        if np.any(np.isnan(vec1)) or np.any(np.isnan(vec2)):
            raise ValueError("NaN values detected in RSSI vectors")
        if np.any(np.isinf(vec1)) or np.any(np.isinf(vec2)):
            raise ValueError("Inf values detected in RSSI vectors")
        return euclidean(vec1, vec2)
    
    def estimate_position(self, current_scan: Dict[str, int]) -> Dict:
        """Estimate position - to be implemented by subclasses"""
        raise NotImplementedError


class KNN(PositioningAlgorithm):
    """K-Nearest Neighbors positioning"""
    
    def __init__(self, reference_points: pd.DataFrame, all_bssids: List[str], k: int = 3):
        super().__init__(reference_points, all_bssids)
        self.k = k
        print(f"   Algorithm: KNN with k={k}")
    
    def estimate_position(self, current_scan: Dict[str, int]) -> Dict:
        """Estimate position using KNN"""
        
        # Prepare current scan vector
        current_vector = self.prepare_rssi_vector(current_scan)
        
        # Calculate distances to all reference points
        distances = []
        
        for idx, ref_point in self.reference_points.iterrows():
            ref_vector = self.get_reference_rssi_vector(ref_point)
            distance = self.calculate_distance(current_vector, ref_vector)
            
            distances.append({
                'index': idx,
                'distance': distance,
                'floor': ref_point['floor'],
                'section': ref_point['section'],
                'x': ref_point['x'],
                'y': ref_point['y']
            })
        
        # Sort by distance
        distances.sort(key=lambda x: x['distance'])
        
        # Get k nearest neighbors
        k_nearest = distances[:self.k]
        
        # Average position of k nearest neighbors
        avg_x = np.mean([n['x'] for n in k_nearest])
        avg_y = np.mean([n['y'] for n in k_nearest])
        
        # Floor determination - majority vote
        floors = [n['floor'] for n in k_nearest]
        floor = max(set(floors), key=floors.count)
        
        # Section determination - majority vote
        sections = [n['section'] for n in k_nearest]
        section = max(set(sections), key=sections.count)
        
        result = {
            'x': float(avg_x),
            'y': float(avg_y),
            'floor': int(floor),
            'section': section,
            'algorithm': 'KNN',
            'k': self.k,
            'confidence': self._calculate_confidence(k_nearest),
            'nearest_neighbors': k_nearest[:5]  # Return top 5 for debugging
        }
        
        return result
    
    def _calculate_confidence(self, k_nearest: List[Dict]) -> float:
        """Calculate confidence score based on distance spread"""
        distances = [n['distance'] for n in k_nearest]
        avg_distance = np.mean(distances)
        
        # Confidence inversely proportional to average distance
        # Typical RSSI distance range is 0-200
        if avg_distance == 0:
            return 100.0
        
        confidence = max(0, min(100, 100 * (1 - avg_distance / 200)))
        return float(confidence)


class WeightedKNN(PositioningAlgorithm):
    """Weighted K-Nearest Neighbors positioning"""
    
    def __init__(self, reference_points: pd.DataFrame, all_bssids: List[str], k: int = 4):
        super().__init__(reference_points, all_bssids)
        self.k = k
        print(f"   Algorithm: Weighted-KNN with k={k}")
    
    def estimate_position(self, current_scan: Dict[str, int]) -> Dict:
        """Estimate position using Weighted KNN"""
        
        # Prepare current scan vector
        current_vector = self.prepare_rssi_vector(current_scan)
        
        # Calculate distances to all reference points
        distances = []
        
        for idx, ref_point in self.reference_points.iterrows():
            ref_vector = self.get_reference_rssi_vector(ref_point)
            distance = self.calculate_distance(current_vector, ref_vector)
            
            distances.append({
                'index': idx,
                'distance': distance,
                'floor': ref_point['floor'],
                'section': ref_point['section'],
                'x': ref_point['x'],
                'y': ref_point['y']
            })
        
        # Sort by distance
        distances.sort(key=lambda x: x['distance'])
        
        # Get k nearest neighbors
        k_nearest = distances[:self.k]
        
        # Calculate weights (inverse of distance)
        # Add small epsilon to avoid division by zero
        epsilon = 0.1
        weights = [1.0 / (n['distance'] + epsilon) for n in k_nearest]
        total_weight = sum(weights)
        
        # Normalize weights
        normalized_weights = [w / total_weight for w in weights]
        
        # Weighted average position
        weighted_x = sum(n['x'] * w for n, w in zip(k_nearest, normalized_weights))
        weighted_y = sum(n['y'] * w for n, w in zip(k_nearest, normalized_weights))
        
        # Floor determination - weighted vote
        floor_votes = {}
        for n, w in zip(k_nearest, normalized_weights):
            floor = n['floor']
            floor_votes[floor] = floor_votes.get(floor, 0) + w
        
        floor = max(floor_votes, key=floor_votes.get)
        
        # Section determination - weighted vote
        section_votes = {}
        for n, w in zip(k_nearest, normalized_weights):
            section = n['section']
            section_votes[section] = section_votes.get(section, 0) + w
        
        section = max(section_votes, key=section_votes.get)
        
        result = {
            'x': float(weighted_x),
            'y': float(weighted_y),
            'floor': int(floor),
            'section': section,
            'algorithm': 'Weighted-KNN',
            'k': self.k,
            'confidence': self._calculate_confidence(k_nearest, normalized_weights),
            'nearest_neighbors': [
                {**n, 'weight': f"{w:.3f}"} for n, w in zip(k_nearest[:5], normalized_weights[:5])
            ]
        }
        
        return result
    
    def _calculate_confidence(self, k_nearest: List[Dict], weights: List[float]) -> float:
        """Calculate confidence score based on weighted distances"""
        weighted_distance = sum(n['distance'] * w for n, w in zip(k_nearest, weights))
        
        # Confidence inversely proportional to weighted distance
        confidence = max(0, min(100, 100 * (1 - weighted_distance / 150)))
        return float(confidence)


class RandomForestPositioning(PositioningAlgorithm):
    """Random Forest positioning (requires scikit-learn)"""
    
    def __init__(self, reference_points: pd.DataFrame, all_bssids: List[str]):
        super().__init__(reference_points, all_bssids)
        self.model_x = None
        self.model_y = None
        self.model_floor = None
        self.model_section = None
        print(f"   Algorithm: Random Forest")
    
    def train(self):
        """Train Random Forest models"""
        try:
            from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
        except ImportError:
            print("❌ scikit-learn not installed. Install with: pip install scikit-learn")
            return False
        
        print("\n🌲 Training Random Forest models...")
        
        # Prepare training data
        X = []
        y_x = []
        y_y = []
        y_floor = []
        y_section = []
        
        for idx, ref_point in self.reference_points.iterrows():
            rssi_vector = self.get_reference_rssi_vector(ref_point)
            X.append(rssi_vector)
            y_x.append(ref_point['x'])
            y_y.append(ref_point['y'])
            y_floor.append(ref_point['floor'])
            y_section.append(ref_point['section'])
        
        X = np.array(X)
        y_x = np.array(y_x)
        y_y = np.array(y_y)
        y_floor = np.array(y_floor)
        y_section = np.array(y_section)
        
        # Train models
        self.model_x = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        self.model_y = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        self.model_floor = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        self.model_section = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        
        print("   Training X coordinate model...")
        self.model_x.fit(X, y_x)
        
        print("   Training Y coordinate model...")
        self.model_y.fit(X, y_y)
        
        print("   Training Floor model...")
        self.model_floor.fit(X, y_floor)
        
        print("   Training Section model...")
        self.model_section.fit(X, y_section)
        
        print("✅ Random Forest models trained successfully!")
        return True
    
    def estimate_position(self, current_scan: Dict[str, int]) -> Dict:
        """Estimate position using Random Forest"""
        
        if self.model_x is None:
            raise Exception("Models not trained. Call train() first.")
        
        # Prepare current scan vector
        current_vector = self.prepare_rssi_vector(current_scan).reshape(1, -1)
        
        # Predict
        x = self.model_x.predict(current_vector)[0]
        y = self.model_y.predict(current_vector)[0]
        floor = self.model_floor.predict(current_vector)[0]
        section = self.model_section.predict(current_vector)[0]
        
        # Get confidence from probability
        floor_proba = self.model_floor.predict_proba(current_vector)[0]
        section_proba = self.model_section.predict_proba(current_vector)[0]
        
        confidence = (max(floor_proba) + max(section_proba)) / 2 * 100
        
        result = {
            'x': float(x),
            'y': float(y),
            'floor': int(floor),
            'section': str(section),
            'algorithm': 'Random-Forest',
            'confidence': float(confidence),
            'floor_confidence': float(max(floor_proba) * 100),
            'section_confidence': float(max(section_proba) * 100)
        }
        
        return result


# Test the algorithms
if __name__ == "__main__":
    from preprocessing import FingerprintDatabase
    import random
    
    print("\n" + "="*70)
    print("🧪 TESTING POSITIONING ALGORITHMS")
    print("="*70)
    
    # Load database
    db = FingerprintDatabase(data_dir='data')
    db.load_all_floors()
    db.create_reference_points()
    
    print("\n" + "="*70)
    print("📍 ALGORITHM TESTING")
    print("="*70)
    
    # Get a random sample from the database for testing
    random_idx = random.randint(0, len(db.df) - 1)
    sample = db.df.iloc[random_idx]
    
    # Extract current scan from sample
    current_scan = {}
    for bssid in db.all_bssids:
        if bssid in sample and pd.notna(sample[bssid]):
            current_scan[bssid] = int(sample[bssid])
    
    actual_floor = sample['floor']
    actual_section = sample['section']
    actual_x = sample['x']
    actual_y = sample['y']
    
    print(f"\n🎯 Test Sample (Ground Truth):")
    print(f"   Location: Floor {actual_floor}, Section '{actual_section}', ({actual_x}, {actual_y})")
    print(f"   Detected APs: {len(current_scan)}")
    
    # Test KNN
    print("\n" + "-"*70)
    print("1️⃣  K-NEAREST NEIGHBORS (KNN)")
    print("-"*70)
    
    knn = KNN(db.reference_points, db.all_bssids, k=3)
    result_knn = knn.estimate_position(current_scan)
    
    error_x = abs(result_knn['x'] - actual_x)
    error_y = abs(result_knn['y'] - actual_y)
    error_distance = np.sqrt(error_x**2 + error_y**2)
    
    print(f"\n📊 Results:")
    print(f"   Estimated: Floor {result_knn['floor']}, Section '{result_knn['section']}', "
          f"({result_knn['x']:.2f}, {result_knn['y']:.2f})")
    print(f"   Confidence: {result_knn['confidence']:.1f}%")
    print(f"\n📏 Error:")
    print(f"   Floor:    {'✅ Correct' if result_knn['floor'] == actual_floor else '❌ Wrong'}")
    print(f"   Section:  {'✅ Correct' if result_knn['section'] == actual_section else '❌ Wrong'}")
    print(f"   X error:  {error_x:.2f} grid units")
    print(f"   Y error:  {error_y:.2f} grid units")
    print(f"   Distance: {error_distance:.2f} grid units")
    
    print(f"\n🔍 Top 3 Nearest Neighbors:")
    for i, neighbor in enumerate(result_knn['nearest_neighbors'][:3], 1):
        print(f"   {i}. Floor {neighbor['floor']}, ({neighbor['x']}, {neighbor['y']}) "
              f"- Distance: {neighbor['distance']:.2f}")
    
    # Test Weighted KNN
    print("\n" + "-"*70)
    print("2️⃣  WEIGHTED K-NEAREST NEIGHBORS (WKNN)")
    print("-"*70)
    
    wknn = WeightedKNN(db.reference_points, db.all_bssids, k=4)
    result_wknn = wknn.estimate_position(current_scan)
    
    error_x = abs(result_wknn['x'] - actual_x)
    error_y = abs(result_wknn['y'] - actual_y)
    error_distance = np.sqrt(error_x**2 + error_y**2)
    
    print(f"\n📊 Results:")
    print(f"   Estimated: Floor {result_wknn['floor']}, Section '{result_wknn['section']}', "
          f"({result_wknn['x']:.2f}, {result_wknn['y']:.2f})")
    print(f"   Confidence: {result_wknn['confidence']:.1f}%")
    print(f"\n📏 Error:")
    print(f"   Floor:    {'✅ Correct' if result_wknn['floor'] == actual_floor else '❌ Wrong'}")
    print(f"   Section:  {'✅ Correct' if result_wknn['section'] == actual_section else '❌ Wrong'}")
    print(f"   X error:  {error_x:.2f} grid units")
    print(f"   Y error:  {error_y:.2f} grid units")
    print(f"   Distance: {error_distance:.2f} grid units")
    
    print(f"\n🔍 Top 4 Nearest Neighbors (with weights):")
    for i, neighbor in enumerate(result_wknn['nearest_neighbors'][:4], 1):
        print(f"   {i}. Floor {neighbor['floor']}, ({neighbor['x']}, {neighbor['y']}) "
              f"- Weight: {neighbor['weight']}")
    
    # Test Random Forest (optional)
    print("\n" + "-"*70)
    print("3️⃣  RANDOM FOREST")
    print("-"*70)
    
    try:
        rf = RandomForestPositioning(db.reference_points, db.all_bssids)
        if rf.train():
            result_rf = rf.estimate_position(current_scan)
            
            error_x = abs(result_rf['x'] - actual_x)
            error_y = abs(result_rf['y'] - actual_y)
            error_distance = np.sqrt(error_x**2 + error_y**2)
            
            print(f"\n📊 Results:")
            print(f"   Estimated: Floor {result_rf['floor']}, Section '{result_rf['section']}', "
                  f"({result_rf['x']:.2f}, {result_rf['y']:.2f})")
            print(f"   Overall Confidence: {result_rf['confidence']:.1f}%")
            print(f"   Floor Confidence: {result_rf['floor_confidence']:.1f}%")
            print(f"   Section Confidence: {result_rf['section_confidence']:.1f}%")
            print(f"\n📏 Error:")
            print(f"   Floor:    {'✅ Correct' if result_rf['floor'] == actual_floor else '❌ Wrong'}")
            print(f"   Section:  {'✅ Correct' if result_rf['section'] == actual_section else '❌ Wrong'}")
            print(f"   X error:  {error_x:.2f} grid units")
            print(f"   Y error:  {error_y:.2f} grid units")
            print(f"   Distance: {error_distance:.2f} grid units")
    except ImportError:
        print("\n⚠️ Scikit-learn not installed. Skipping Random Forest test.")
        print("   Install with: pip install scikit-learn")
    
    print("\n" + "="*70)
    print("✅ Algorithm testing complete!")
    print("="*70)