import numpy as np
import pandas as pd
from typing import Dict, List
from scipy.spatial.distance import euclidean

class PositioningAlgorithm:
    """Base class for positioning algorithms"""
    def __init__(self, reference_points: pd.DataFrame, all_bssids: List[str]):
        self.reference_points = reference_points
        self.all_bssids = all_bssids

    def prepare_rssi_vector(self, current_scan: Dict[str, int]) -> np.ndarray:
        rssi_vector = []
        for bssid in self.all_bssids:
            value = current_scan.get(bssid, -100)
            if pd.isna(value) or value is None:
                rssi_vector.append(-100)
            else:
                try:
                    rssi_vector.append(float(value))
                except (ValueError, TypeError):
                    rssi_vector.append(-100)
        return np.array(rssi_vector)

    def get_reference_rssi_vector(self, ref_point: pd.Series) -> np.ndarray:
        rssi_vector = []
        for bssid in self.all_bssids:
            value = ref_point.get(bssid, -100)
            if pd.isna(value) or value is None:
                rssi_vector.append(-100)
            else:
                try:
                    rssi_vector.append(float(value))
                except (ValueError, TypeError):
                    rssi_vector.append(-100)
        return np.array(rssi_vector)

    def calculate_distance(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        return euclidean(vec1, vec2)

    def estimate_position(self, current_scan: Dict[str, int]) -> Dict:
        raise NotImplementedError

class KNN(PositioningAlgorithm):
    """K-Nearest Neighbors positioning"""
    def __init__(self, reference_points: pd.DataFrame, all_bssids: List[str], k: int = 3):
        super().__init__(reference_points, all_bssids)
        self.k = k

    def estimate_position(self, current_scan: Dict[str, int]) -> Dict:
        current_vector = self.prepare_rssi_vector(current_scan)
        distances = []
        for idx, ref_point in self.reference_points.iterrows():
            ref_vector = self.get_reference_rssi_vector(ref_point)
            distance = self.calculate_distance(current_vector, ref_vector)
            distances.append({
                'index': idx,
                'distance': float(distance),
                'floor': int(ref_point['floor']),
                'section': str(ref_point['section']),
                'x': float(ref_point['x']),
                'y': float(ref_point['y'])
            })
        distances.sort(key=lambda x: x['distance'])
        k_nearest = distances[:self.k]
        avg_x = np.mean([n['x'] for n in k_nearest])
        avg_y = np.mean([n['y'] for n in k_nearest])
        floors = [n['floor'] for n in k_nearest]
        floor = max(set(floors), key=floors.count)
        sections = [n['section'] for n in k_nearest]
        section = max(set(sections), key=sections.count)
        result = {
            'x': float(avg_x),
            'y': float(avg_y),
            'floor': int(floor),
            'section': str(section),
            'algorithm': 'KNN',
            'k': self.k,
            'confidence': self._calculate_confidence(k_nearest),
            'nearest_neighbors': k_nearest[:5]
        }
        return result

    def _calculate_confidence(self, k_nearest: List[Dict]) -> float:
        distances = [n['distance'] for n in k_nearest]
        avg_distance = np.mean(distances)
        if avg_distance == 0:
            return 100.0
        confidence = max(0, min(100, 100 * (1 - avg_distance / 200)))
        return float(confidence)

class WeightedKNN(PositioningAlgorithm):
    """Weighted KNN positioning"""
    def __init__(self, reference_points: pd.DataFrame, all_bssids: List[str], k: int = 4):
        super().__init__(reference_points, all_bssids)
        self.k = k

    def estimate_position(self, current_scan: Dict[str, int]) -> Dict:
        current_vector = self.prepare_rssi_vector(current_scan)
        distances = []
        for idx, ref_point in self.reference_points.iterrows():
            ref_vector = self.get_reference_rssi_vector(ref_point)
            distance = self.calculate_distance(current_vector, ref_vector)
            distances.append({
                'index': idx,
                'distance': float(distance),
                'floor': int(ref_point['floor']),
                'section': str(ref_point['section']),
                'x': float(ref_point['x']),
                'y': float(ref_point['y'])
            })
        distances.sort(key=lambda x: x['distance'])
        k_nearest = distances[:self.k]
        epsilon = 0.1
        weights = [1.0 / (n['distance'] + epsilon) for n in k_nearest]
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        weighted_x = sum(n['x'] * w for n, w in zip(k_nearest, normalized_weights))
        weighted_y = sum(n['y'] * w for n, w in zip(k_nearest, normalized_weights))
        floor_votes = {}
        for n, w in zip(k_nearest, normalized_weights):
            floor = n['floor']
            floor_votes[floor] = floor_votes.get(floor, 0) + w
        floor = max(floor_votes, key=floor_votes.get)
        section_votes = {}
        for n, w in zip(k_nearest, normalized_weights):
            section = n['section']
            section_votes[section] = section_votes.get(section, 0) + w
        section = max(section_votes, key=section_votes.get)
        nn_output = []
        for n, w in zip(k_nearest[:5], normalized_weights[:5]):
            neighbor = n.copy()
            neighbor['weight'] = f"{w:.3f}"
            nn_output.append(neighbor)
        result = {
            'x': float(weighted_x),
            'y': float(weighted_y),
            'floor': int(floor),
            'section': str(section),
            'algorithm': 'Weighted-KNN',
            'k': self.k,
            'confidence': self._calculate_confidence(k_nearest, normalized_weights),
            'nearest_neighbors': nn_output
        }
        return result

    def _calculate_confidence(self, k_nearest: List[Dict], weights: List[float]) -> float:
        weighted_distance = sum(n['distance'] * w for n, w in zip(k_nearest, weights))
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
        self.train()

    def estimate_position(self, current_scan: Dict[str, int]) -> Dict:
        current_vector = self.prepare_rssi_vector(current_scan).reshape(1, -1)
        x = float(self.model_x.predict(current_vector)[0])
        y = float(self.model_y.predict(current_vector)[0])
        floor = int(self.model_floor.predict(current_vector)[0])
        section = str(self.model_section.predict(current_vector)[0])
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

    def train(self):
        from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
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
        self.model_x = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        self.model_y = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        self.model_floor = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        self.model_section = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        self.model_x.fit(X, y_x)
        self.model_y.fit(X, y_y)
        self.model_floor.fit(X, y_floor)
        self.model_section.fit(X, y_section)

class HybridWKNNRF(PositioningAlgorithm):
    """
    Hybrid model:
    - Uses Random Forest for floor and section classification.
    - Uses Weighted-KNN for x, y localization on predicted floor+section ref points.
    """
    def __init__(self, reference_points: pd.DataFrame, all_bssids: List[str], k: int = 4):
        super().__init__(reference_points, all_bssids)
        from sklearn.ensemble import RandomForestClassifier
        self.k = k
        X = []
        y_floor = []
        y_section = []
        for idx, ref_point in self.reference_points.iterrows():
            rssi_vect = self.get_reference_rssi_vector(ref_point)
            X.append(rssi_vect)
            y_floor.append(ref_point['floor'])
            y_section.append(ref_point['section'])
        X = np.array(X)
        self.rf_floor = RandomForestClassifier(n_estimators=100, random_state=42)
        self.rf_section = RandomForestClassifier(n_estimators=100, random_state=42)
        self.rf_floor.fit(X, y_floor)
        self.rf_section.fit(X, y_section)

    def estimate_position(self, current_scan: Dict[str, int]) -> Dict:
        current_vector = self.prepare_rssi_vector(current_scan).reshape(1, -1)
        floor_pred = self.rf_floor.predict(current_vector)[0]
        section_pred = self.rf_section.predict(current_vector)[0]
        floor_probs = self.rf_floor.predict_proba(current_vector)[0]
        section_probs = self.rf_section.predict_proba(current_vector)[0]
        floor_conf = float(np.max(floor_probs)) * 100
        section_conf = float(np.max(section_probs)) * 100

        sub_ref = self.reference_points[
            (self.reference_points['floor'] == floor_pred) &
            (self.reference_points['section'] == section_pred)
        ]

        if len(sub_ref) < self.k:
            sub_ref = self.reference_points[self.reference_points['floor'] == floor_pred]
        if len(sub_ref) < self.k:
            sub_ref = self.reference_points

        custom_wknn = WeightedKNN(sub_ref, self.all_bssids, k=min(self.k, len(sub_ref)))
        wknn_result = custom_wknn.estimate_position(current_scan)

        result = {
            'x': float(wknn_result['x']),
            'y': float(wknn_result['y']),
            'floor': int(floor_pred),
            'section': str(section_pred),
            'algorithm': 'Hybrid-RF-WKNN',
            'confidence': float((wknn_result['confidence'] + floor_conf + section_conf) / 3),
            'nearest_neighbors': wknn_result.get('nearest_neighbors', []),
            'floor_confidence': float(floor_conf),
            'section_confidence': float(section_conf)
        }
        return result