import networkx as nx

def build_graph(reference_points, neighbor_radius=1.8, pois=None):
    """
    Builds a graph where each reference point (floor, x, y) is a node.
    Connects nodes on the same floor within neighbor_radius.
    Adds virtual edges between stairs/lifts on different floors for cross-floor navigation.
    
    Args:
        reference_points: DataFrame with floor, x, y, section columns
        neighbor_radius: Maximum distance to connect nodes on same floor
        pois: Dictionary of POIs with their locations and types (for cross-floor edges)
    """
    G = nx.Graph()
    for idx, row in reference_points.iterrows():
        node = (int(row['floor']), float(row['x']), float(row['y']))
        G.add_node(node, section=row['section'])

    nodes = list(G.nodes)
    
    # Connect nodes on the same floor within neighbor_radius
    for i, node1 in enumerate(nodes):
        for j, node2 in enumerate(nodes):
            if i >= j: continue
            if node1[0] != node2[0]: continue  # same floor
            dist = ((node1[1] - node2[1]) ** 2 + (node1[2] - node2[2]) ** 2) ** 0.5
            if dist <= neighbor_radius:
                G.add_edge(node1, node2, weight=dist)
    
    # Add virtual edges between stairs and lifts on different floors
    if pois:
        # Group POIs by type and location (x, y)
        stairs_and_lifts = {}
        for name, info in pois.items():
            poi_type = info.get('type', '')
            if poi_type in ['stairs', 'lift']:
                floor = info['floor']
                x = info['x']
                y = info['y']
                key = (poi_type, x, y)  # Same type and location
                if key not in stairs_and_lifts:
                    stairs_and_lifts[key] = []
                stairs_and_lifts[key].append((name, floor, x, y))
        
        # For each group of stairs/lifts at same location, connect across floors
        for (poi_type, x, y), locations in stairs_and_lifts.items():
            if len(locations) > 1:
                # Find closest nodes to each POI on their respective floors
                poi_nodes = []
                for name, floor, px, py in locations:
                    closest_node = find_closest_node(G, floor, px, py)
                    if closest_node:
                        poi_nodes.append((floor, closest_node))
                
                # Connect all pairs of nodes across different floors
                for i in range(len(poi_nodes)):
                    for j in range(i + 1, len(poi_nodes)):
                        floor1, node1 = poi_nodes[i]
                        floor2, node2 = poi_nodes[j]
                        if floor1 != floor2:
                            # Add virtual edge with small weight (representing stair/lift transition)
                            # Weight of 2.0 represents the "cost" of changing floors
                            G.add_edge(node1, node2, weight=2.0)
    
    return G

def find_closest_node(G, floor, x, y):
    best_node = None
    best_dist = float('inf')
    for node in G.nodes:
        if node[0] == floor:
            dist = ((node[1] - x) ** 2 + (node[2] - y) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_node = node
    return best_node

def shortest_path(G, start_node, goal_node):
    if start_node is None or goal_node is None:
        return []
    try:
        return nx.shortest_path(G, start_node, goal_node, weight='weight')
    except Exception:  # e.g. no path found
        return []