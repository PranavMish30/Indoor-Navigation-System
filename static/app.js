let currentFloor = 0;
let referencePointsByFloor = {};
let availableFloors = [0];
let showRefPoints = true;
let currentPosition = null;
let destinations = [];
let navigationPath = [];
let sessionId = 'user_' + Math.random().toString(36).substr(2, 9); // Unique session ID for Kalman filtering

// Auto-tracking state
let isTracking = false;
let trackingInterval = null;
let positionHistory = []; // Store last N positions for trail visualization
const MAX_HISTORY = 20;
const TRACKING_INTERVAL_MS = 2500; // Scan every 2.5 seconds

let canvas, ctx;
const SCALE = 100; // 100 pixels per grid unit
const LEFT_PADDING = 150; // Padding on left side for icons

document.addEventListener('DOMContentLoaded', async function() {
    canvas = document.getElementById('floorPlan');
    ctx = canvas.getContext('2d');

    document.getElementById('scanBtn').addEventListener('click', scanAndLocate);
    document.getElementById('autoTrackBtn').addEventListener('click', toggleAutoTracking);
    document.getElementById('showRefPoints').addEventListener('click', toggleRefPoints);
    document.getElementById('floorSelect').addEventListener('change', event => {
        currentFloor = parseInt(event.target.value, 10);
        document.getElementById('currentFloor').textContent = currentFloor;
        drawFloorPlan();
    });

    await loadSystemStats();
    await loadReferencePoints();
    populateFloorDropdown();
    await loadDestinations();
    document.getElementById('navigateBtn').addEventListener('click', doNavigation);
    drawFloorPlan();
});

function populateFloorDropdown() {
    let floorSel = document.getElementById('floorSelect');
    floorSel.innerHTML = '';
    availableFloors.forEach(floorNum => {
        let opt = document.createElement('option');
        opt.value = floorNum;
        opt.text = `Floor ${floorNum}`;
        floorSel.appendChild(opt);
    });
    floorSel.value = currentFloor;
}

async function loadSystemStats() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        document.getElementById('refPointsCount').textContent = data.total_reference_points;
        document.getElementById('totalAPs').textContent = data.total_bssids;
        document.getElementById('systemStatus').innerHTML = '<span class="status-dot"></span> Online';
        document.getElementById('systemStatus').style.color = '#4CAF50';
    } catch (error) {
        document.getElementById('systemStatus').innerHTML = '<span class="status-dot" style="background: #f44336;"></span> Offline';
        document.getElementById('systemStatus').style.color = '#f44336';
    }
}

async function loadReferencePoints() {
    const stats = await fetch('/api/stats').then(res=>res.json());
    availableFloors = stats.floors;
    referencePointsByFloor = {};
    for (const floorNum of availableFloors) {
        const response = await fetch(`/api/reference-points?floor=${floorNum}`);
        referencePointsByFloor[floorNum] = await response.json();
    }
}

async function loadDestinations() {
    const sel = document.getElementById('destinationSelect');
    sel.innerHTML = '';
    try {
        const data = await fetch('/api/destinations').then(r => r.json());
        destinations = data;
        data.forEach((dest) => {
            let label = dest.label; // Name from backend
            let opt = document.createElement('option');
            opt.value = label;
            opt.textContent = label +
                (dest.type ? ` (${dest.type})` : '') +
                ` (Floor ${dest.floor})`;
            sel.appendChild(opt);
        });
    } catch (e) {
        document.getElementById('navStatus').textContent = 'Could not load destinations.';
    }
}

async function scanAndLocate() {
    const scanBtn = document.getElementById('scanBtn');
    const statusDiv = document.getElementById('scanStatus');
    const algorithm = document.getElementById('algorithm').value;

    // Don't allow manual scan during auto-tracking
    if (isTracking) {
        statusDiv.className = 'status info';
        statusDiv.textContent = '⚠️ Stop real-time tracking first to perform manual scan';
        statusDiv.classList.remove('hidden');
        return;
    }

    scanBtn.disabled = true;
    scanBtn.textContent = '⏳ Scanning...';

    statusDiv.className = 'status info';
    statusDiv.textContent = '📡 Scanning WiFi networks...';
    statusDiv.classList.remove('hidden');

    try {
        const scanResponse = await fetch('/api/scan');
        const scanData = await scanResponse.json();

        if (scanData.error) throw new Error(scanData.error);
        displayNetworks(scanData.aps);

        if (scanData.count === 0) {
            statusDiv.className = 'status error';
            statusDiv.textContent = '❌ No BMSIT networks detected. Make sure you are on campus.';
            return;
        }

        statusDiv.textContent = `🔍 Calculating position using ${algorithm.toUpperCase()}...`;
        
        const enableKalman = document.getElementById('enableKalman').checked;
        
        const locateResponse = await fetch('/api/locate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                scan: scanData.aps,
                algorithm: algorithm,
                session_id: sessionId,
                use_kalman: enableKalman && !algorithm.includes('kalman') // Don't double-apply Kalman
            })
        });

        const position = await locateResponse.json();
        if (position.error) throw new Error(position.error);

        currentPosition = position;
        currentPosition.num_aps = scanData.count;
        currentFloor = Number(position.floor);

        displayPosition(position);
        if (position.nearest_neighbors) {
            displayNearestNeighbors(position.nearest_neighbors);
        }
        document.getElementById('currentFloor').textContent = currentFloor;
        document.getElementById('floorSelect').value = currentFloor;
        drawFloorPlan();

        statusDiv.className = 'status success';
        statusDiv.textContent = `✅ Position located! Floor ${position.floor}, Section: ${position.section}`;
        
        // Add to position history for trail visualization
        if (isTracking && position) {
            positionHistory.push({
                x: position.x,
                y: position.y,
                floor: position.floor,
                timestamp: Date.now()
            });
            if (positionHistory.length > MAX_HISTORY) {
                positionHistory.shift(); // Remove oldest
            }
        }
    } catch (error) {
        statusDiv.className = 'status error';
        statusDiv.textContent = `❌ Error: ${error.message}`;
        currentPosition = null;
        drawFloorPlan();
        document.getElementById('floorValue').textContent = "-";
        document.getElementById('sectionValue').textContent = "-";
        document.getElementById('coordValue').textContent = "-";
        document.getElementById('confidenceValue').textContent = "-";
        document.getElementById('apsValue').textContent = "-";
        document.getElementById('nearestNeighbors').innerHTML = '<p class="placeholder">Scan to see nearest reference points</p>';
    } finally {
        scanBtn.disabled = false;
        scanBtn.textContent = '🔍 Scan & Locate';
    }
}

function toggleAutoTracking() {
    const btn = document.getElementById('autoTrackBtn');
    const scanBtn = document.getElementById('scanBtn');
    const statusDiv = document.getElementById('scanStatus');
    
    if (!isTracking) {
        // Start tracking
        isTracking = true;
        btn.textContent = '⏹️ Stop Tracking';
        btn.classList.remove('btn-accent');
        btn.classList.add('btn-danger');
        scanBtn.disabled = true;
        
        statusDiv.className = 'status info';
        statusDiv.textContent = '🎯 Real-time tracking active - Auto-scanning every 2.5 seconds...';
        statusDiv.classList.remove('hidden');
        
        // Clear history and perform first scan immediately
        positionHistory = [];
        performAutoScan();
        
        // Set up interval for continuous scanning
        trackingInterval = setInterval(performAutoScan, TRACKING_INTERVAL_MS);
    } else {
        // Stop tracking
        stopTracking();
    }
}

function stopTracking() {
    isTracking = false;
    if (trackingInterval) {
        clearInterval(trackingInterval);
        trackingInterval = null;
    }
    
    const btn = document.getElementById('autoTrackBtn');
    const scanBtn = document.getElementById('scanBtn');
    const statusDiv = document.getElementById('scanStatus');
    
    btn.textContent = '🎯 Start Real-Time Tracking';
    btn.classList.remove('btn-danger');
    btn.classList.add('btn-accent');
    scanBtn.disabled = false;
    
    statusDiv.className = 'status info';
    statusDiv.textContent = '⏸️ Real-time tracking stopped';
}

async function performAutoScan() {
    const statusDiv = document.getElementById('scanStatus');
    const algorithm = document.getElementById('algorithm').value;
    
    try {
        const scanResponse = await fetch('/api/scan');
        const scanData = await scanResponse.json();

        if (scanData.error) {
            console.error('Scan error:', scanData.error);
            return;
        }
        
        displayNetworks(scanData.aps);

        if (scanData.count === 0) {
            statusDiv.className = 'status error';
            statusDiv.textContent = '❌ No BMSIT networks detected. Retrying...';
            return;
        }

        const enableKalman = document.getElementById('enableKalman').checked;
        
        const locateResponse = await fetch('/api/locate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                scan: scanData.aps,
                algorithm: algorithm,
                session_id: sessionId,
                use_kalman: enableKalman && !algorithm.includes('kalman')
            })
        });

        const position = await locateResponse.json();
        if (position.error) {
            console.error('Locate error:', position.error);
            return;
        }

        currentPosition = position;
        currentPosition.num_aps = scanData.count;
        currentFloor = Number(position.floor);

        displayPosition(position);
        if (position.nearest_neighbors) {
            displayNearestNeighbors(position.nearest_neighbors);
        }
        document.getElementById('currentFloor').textContent = currentFloor;
        document.getElementById('floorSelect').value = currentFloor;
        
        // Add to position history
        positionHistory.push({
            x: position.x,
            y: position.y,
            floor: position.floor,
            timestamp: Date.now()
        });
        if (positionHistory.length > MAX_HISTORY) {
            positionHistory.shift();
        }
        
        drawFloorPlan();

        statusDiv.className = 'status success';
        const scanCount = positionHistory.length;
        statusDiv.textContent = `✅ Tracking active (${scanCount} scans) - Floor ${position.floor}, Section: ${position.section}`;
    } catch (error) {
        console.error('Auto-scan error:', error);
        statusDiv.className = 'status error';
        statusDiv.textContent = `⚠️ Scan error: ${error.message}. Retrying...`;
    }
}

function displayNetworks(aps) {
    const networkList = document.getElementById('networkList');
    if (!aps || Object.keys(aps).length === 0) {
        networkList.innerHTML = '<p class="placeholder">No networks detected</p>';
        return;
    }
    const sorted = Object.entries(aps).sort((a, b) => b[1] - a[1]);
    let html = '';
    sorted.forEach(([bssid, rssi]) => {
        const [mac, ssid] = bssid.split('|');
        let rssiClass = 'rssi-poor';
        if (rssi > -60) rssiClass = 'rssi-excellent';
        else if (rssi > -70) rssiClass = 'rssi-good';
        else if (rssi > -80) rssiClass = 'rssi-fair';
        html += `
            <div class="network-item">
                <div class="network-name">${ssid}</div>
                <div class="network-rssi ${rssiClass}">${rssi} dBm</div>
            </div>
        `;
    });
    networkList.innerHTML = html;
    document.getElementById('apsValue').textContent = Object.keys(aps).length;
}

function displayPosition(position) {
    document.getElementById('floorValue').textContent = `Floor ${position.floor}`;
    document.getElementById('sectionValue').textContent = position.section;
    
    // Show raw vs filtered coordinates if Kalman was applied
    let coordText = `(${position.x.toFixed(2)}, ${position.y.toFixed(2)})`;
    if (position.x_raw !== undefined && position.y_raw !== undefined) {
        coordText += ` [raw: (${position.x_raw.toFixed(2)}, ${position.y_raw.toFixed(2)})]`;
    }
    document.getElementById('coordValue').textContent = coordText;
    
    const confidence = position.confidence.toFixed(1);
    const confidenceElem = document.getElementById('confidenceValue');
    confidenceElem.textContent = `${confidence}%`;

    if (typeof position.floor_confidence !== "undefined" && typeof position.section_confidence !== "undefined") {
        let info = `Floor conf: ${position.floor_confidence.toFixed(1)}%, Section conf: ${position.section_confidence.toFixed(1)}%`;
        confidenceElem.title = info;
    }

    if (confidence >= 90) {
        confidenceElem.style.color = '#4CAF50';
    } else if (confidence >= 70) {
        confidenceElem.style.color = '#FF9800';
    } else {
        confidenceElem.style.color = '#f44336';
    }
    
    // Display algorithm and Kalman status
    document.getElementById('algorithmValue').textContent = position.algorithm || 'N/A';
    document.getElementById('kalmanValue').textContent = position.kalman_enabled ? '✅ Active' : '❌ Disabled';
    document.getElementById('kalmanValue').style.color = position.kalman_enabled ? '#4CAF50' : '#999';
}

function displayNearestNeighbors(neighbors) {
    const neighborsList = document.getElementById('nearestNeighbors');
    if (!neighbors || neighbors.length === 0) {
        neighborsList.innerHTML = '<p class="placeholder">No neighbors data</p>';
        return;
    }
    let html = '';
    neighbors.slice(0, 5).forEach((neighbor, index) => {
        const weight = neighbor.weight ? ` (Weight: ${neighbor.weight})` : '';
        html += `
            <div class="neighbor-item">
                <div class="neighbor-info">
                    <span class="neighbor-location">
                        ${index + 1}. (${neighbor.x}, ${neighbor.y}) - ${neighbor.section}
                    </span>
                    <span class="neighbor-distance">${neighbor.distance ? neighbor.distance.toFixed(2) : '-'} units</span>
                </div>
                ${weight ? `<div class="neighbor-weight">${weight}</div>` : ''}
            </div>
        `;
    });
    neighborsList.innerHTML = html;
}

function toggleRefPoints() {
    showRefPoints = !showRefPoints;
    const btn = document.getElementById('showRefPoints');
    btn.textContent = showRefPoints ? '👁️ Hide Reference Points' : '👁️ Show Reference Points';
    drawFloorPlan();
}

async function doNavigation() {
    if (!currentPosition) {
        document.getElementById('navStatus').textContent = 'Locate your position first!';
        return;
    }
    const sel = document.getElementById('destinationSelect');
    const destLabel = sel.value;
    if (!destLabel) return;
    const response = await fetch('/api/navigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            current: {floor: currentPosition.floor, x: currentPosition.x, y: currentPosition.y},
            destination_label: destLabel
        })
    });
    const nav = await response.json();
    if (nav.error) {
        document.getElementById('navStatus').textContent = nav.error;
        navigationPath = [];
    } else {
        document.getElementById('navStatus').textContent = "Path found!";
        navigationPath = nav.path || [];
    }
    drawFloorPlan();
}

function drawFloorPlan() {
    if (!canvas || !ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw white background
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw floor layout
    drawFloorLayout();
    
    // Draw POIs as rooms
    drawPOIs();

    // Draw navigation path
    if (navigationPath.length > 1) {
        drawNavigationPath();
    }

    // Draw reference points
    if (showRefPoints && referencePointsByFloor[currentFloor]) {
        drawReferencePoints(referencePointsByFloor[currentFloor]);
    }

    // Draw nearest neighbors and current position
    if (currentPosition && Number(currentPosition.floor) === Number(currentFloor)) {
        if (currentPosition.nearest_neighbors) {
            drawNearestNeighbors(currentPosition.nearest_neighbors);
        }
        drawCurrentPosition();
    }
}

// Coordinate conversion: grid (0,0) is at CENTER of bottom-left cell
function gridToCanvas(gridX, gridY) {
    const canvasX = LEFT_PADDING + (gridX + 0.5) * SCALE;
    const canvasY = canvas.height - (gridY + 0.5) * SCALE; // Flip Y axis
    return { x: canvasX, y: canvasY };
}

function drawFloorLayout() {
    ctx.save();
    
    // Draw Left Section - 3x4 grid (no inner borders)
    for (let gridX = 0; gridX < 3; gridX++) {
        for (let gridY = 0; gridY < 4; gridY++) {
            const x = LEFT_PADDING + gridX * SCALE;
            const y = canvas.height - (gridY + 1) * SCALE; // Flip Y
            
            ctx.fillStyle = 'rgba(232, 245, 233, 0.15)';
            ctx.fillRect(x, y, SCALE, SCALE);
        }
    }
    
    // Draw outer border for left section
    ctx.strokeStyle = '#4CAF50';
    ctx.lineWidth = 3;
    ctx.strokeRect(LEFT_PADDING, canvas.height - 4 * SCALE, 3 * SCALE, 4 * SCALE);
    
    // Left label
    ctx.fillStyle = '#2E7D32';
    ctx.globalAlpha = 0.25;
    ctx.font = 'bold 28px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('LEFT SECTION', LEFT_PADDING + 1.5 * SCALE, canvas.height - 2 * SCALE);
    ctx.globalAlpha = 1.0;
    
    // Draw Corridor - spans from y=2 to y=3 (canvas units 2.5 to 3.5)
    for (let gridX = 3; gridX < 20; gridX++) {
        const x = LEFT_PADDING + gridX * SCALE;
        // In canvas coordinates: top at y=3.5, bottom at y=2.5
        const y = canvas.height - 3.5 * SCALE; // Top edge
        const height = SCALE; // Height of 1 grid unit (from 2.5 to 3.5)
        
        ctx.fillStyle = 'rgba(243, 229, 245, 0.15)';
        ctx.fillRect(x, y, SCALE, height);
    }
    
    // Draw outer border for corridor
    ctx.strokeStyle = '#9C27B0';
    ctx.lineWidth = 3;
    ctx.strokeRect(LEFT_PADDING + 3 * SCALE, canvas.height - 3.5 * SCALE, 17 * SCALE, SCALE);
    
    // Corridor label
    ctx.fillStyle = '#6A1B9A';
    ctx.globalAlpha = 0.3;
    ctx.font = 'bold 32px Arial';
    ctx.fillText('CORRIDOR', LEFT_PADDING + 11.5 * SCALE, canvas.height - 2.35 * SCALE);
    ctx.globalAlpha = 1.0;
    
    // Draw Right Section - 3x4 grid (no inner borders)
    for (let gridX = 20; gridX < 23; gridX++) {
        for (let gridY = 0; gridY < 4; gridY++) {
            const x = LEFT_PADDING + gridX * SCALE;
            const y = canvas.height - (gridY + 1) * SCALE; // Flip Y
            
            ctx.fillStyle = 'rgba(227, 242, 253, 0.15)';
            ctx.fillRect(x, y, SCALE, SCALE);
        }
    }
    
    // Draw outer border for right section
    ctx.strokeStyle = '#2196F3';
    ctx.lineWidth = 3;
    ctx.strokeRect(LEFT_PADDING + 20 * SCALE, canvas.height - 4 * SCALE, 3 * SCALE, 4 * SCALE);
    
    // Right label
    ctx.fillStyle = '#1565C0';
    ctx.globalAlpha = 0.25;
    ctx.font = 'bold 28px Arial';
    ctx.fillText('RIGHT SECTION', LEFT_PADDING + 21.5 * SCALE, canvas.height - 2 * SCALE);
    ctx.globalAlpha = 1.0;
    
    ctx.restore();
}

function drawNavigationPath() {
    const pathPoints = navigationPath.filter(pt => pt.floor === currentFloor);
    if (pathPoints.length < 2) return;
    
    ctx.save();
    ctx.shadowColor = 'rgba(255, 0, 102, 0.3)';
    ctx.shadowBlur = 10;
    
    // Draw path line
    ctx.strokeStyle = '#FF0066';
    ctx.lineWidth = 8;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.setLineDash([15, 10]);
    
    ctx.beginPath();
    pathPoints.forEach((pt, i) => {
        const pos = gridToCanvas(pt.x, pt.y);
        if (i === 0) {
            ctx.moveTo(pos.x, pos.y);
        } else {
            ctx.lineTo(pos.x, pos.y);
        }
    });
    ctx.stroke();
    ctx.setLineDash([]);
    
    // Draw waypoint circles
    pathPoints.forEach((pt, i) => {
        const pos = gridToCanvas(pt.x, pt.y);
        
        ctx.fillStyle = '#FF0066';
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 12, 0, 2 * Math.PI);
        ctx.fill();
        
        ctx.strokeStyle = '#FFF';
        ctx.lineWidth = 3;
        ctx.stroke();
        
        // Add step numbers
        if (i > 0 && i < pathPoints.length - 1) {
            ctx.fillStyle = '#FFF';
            ctx.font = 'bold 16px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(i.toString(), pos.x, pos.y);
        }
    });
    
    ctx.restore();
}

function drawPOIs() {
    destinations.forEach(dest => {
        if (dest.floor != currentFloor) return;
        const entrancePos = gridToCanvas(dest.x, dest.y);
        
        ctx.save();
        
        // Determine room position based on entrance location and side property
        let roomX = entrancePos.x;
        let roomY = entrancePos.y;
        let iconSize = 40;
        
        // Use explicit side property from POI data
        if (dest.side === 'left') {
            roomX = entrancePos.x - 150; // Extend left, outside grid
        } else if (dest.side === 'right') {
            roomX = entrancePos.x + 150; // Extend right, outside grid
        } else if (dest.side === 'top') {
            roomY = entrancePos.y - 120; // Top = lower canvas Y (visually above)
        } else if (dest.side === 'bottom') {
            roomY = entrancePos.y + 120; // Bottom = higher canvas Y (visually below)
        }
        
        // Draw entrance marker
        ctx.fillStyle = '#FF5722';
        ctx.strokeStyle = '#FFF';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(entrancePos.x, entrancePos.y, 6, 0, 2 * Math.PI);
        ctx.fill();
        ctx.stroke();
        
        // Draw different types
        ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
        ctx.shadowBlur = 8;
        ctx.shadowOffsetX = 2;
        ctx.shadowOffsetY = 2;
        
        if (dest.type === 'stairs') {
            // Connection line
            ctx.setLineDash([5, 3]);
            ctx.strokeStyle = '#D2691E';
            ctx.lineWidth = 2;
            ctx.globalAlpha = 0.5;
            ctx.beginPath();
            ctx.moveTo(entrancePos.x, entrancePos.y);
            ctx.lineTo(roomX, roomY);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.globalAlpha = 1;
            
            // Circle
            ctx.fillStyle = '#D2691E';
            ctx.strokeStyle = '#8B4513';
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.arc(roomX, roomY, 35, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
            
            // Icon
            ctx.shadowColor = 'transparent';
            ctx.fillStyle = '#FFF';
            ctx.font = 'bold 32px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('↑', roomX, roomY);
        } else if (dest.type === 'lift') {
            // Connection line
            ctx.setLineDash([5, 3]);
            ctx.strokeStyle = '#7B68EE';
            ctx.lineWidth = 2;
            ctx.globalAlpha = 0.5;
            ctx.beginPath();
            ctx.moveTo(entrancePos.x, entrancePos.y);
            ctx.lineTo(roomX, roomY);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.globalAlpha = 1;
            
            // Rectangle
            ctx.fillStyle = '#7B68EE';
            ctx.strokeStyle = '#4B0082';
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.roundRect(roomX - 35, roomY - 35, 70, 70, 8);
            ctx.fill();
            ctx.stroke();
            
            // Icon
            ctx.shadowColor = 'transparent';
            ctx.fillStyle = '#FFF';
            ctx.font = 'bold 32px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('L', roomX, roomY);
        } else if (dest.type === 'entrance') {
            // Entrance - simple arrow icon
            ctx.fillStyle = '#FFD700';
            ctx.strokeStyle = '#FF8C00';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(roomX, roomY, iconSize, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
            
            ctx.shadowColor = 'transparent';
            ctx.fillStyle = '#333';
            ctx.font = 'bold 40px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('🚪', roomX, roomY);
        } else if (dest.type === 'lab') {
            // Lab icon - simpler beaker
            ctx.setLineDash([5, 3]);
            ctx.strokeStyle = '#00ACC1';
            ctx.lineWidth = 2;
            ctx.globalAlpha = 0.4;
            ctx.beginPath();
            ctx.moveTo(entrancePos.x, entrancePos.y);
            ctx.lineTo(roomX, roomY);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.globalAlpha = 1;
            
            ctx.fillStyle = '#00ACC1';
            ctx.strokeStyle = '#006064';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(roomX, roomY, iconSize, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
            
            ctx.shadowColor = 'transparent';
            ctx.fillStyle = '#FFF';
            ctx.font = 'bold 40px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('🔬', roomX, roomY);
        } else if (dest.type === 'classroom') {
            // Classroom icon - simpler book
            ctx.setLineDash([5, 3]);
            ctx.strokeStyle = '#66BB6A';
            ctx.lineWidth = 2;
            ctx.globalAlpha = 0.4;
            ctx.beginPath();
            ctx.moveTo(entrancePos.x, entrancePos.y);
            ctx.lineTo(roomX, roomY);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.globalAlpha = 1;
            
            ctx.fillStyle = '#66BB6A';
            ctx.strokeStyle = '#2E7D32';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(roomX, roomY, iconSize, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
            
            ctx.shadowColor = 'transparent';
            ctx.fillStyle = '#FFF';
            ctx.font = 'bold 40px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('📖', roomX, roomY);
        } else {
            // Misc rooms - use specific icons based on label
            ctx.setLineDash([5, 3]);
            ctx.strokeStyle = '#AB47BC';
            ctx.lineWidth = 2;
            ctx.globalAlpha = 0.4;
            ctx.beginPath();
            ctx.moveTo(entrancePos.x, entrancePos.y);
            ctx.lineTo(roomX, roomY);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.globalAlpha = 1;
            
            ctx.fillStyle = '#AB47BC';
            ctx.strokeStyle = '#6A1B9A';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(roomX, roomY, iconSize, 0, 2 * Math.PI);
            ctx.fill();
            ctx.stroke();
            
            ctx.shadowColor = 'transparent';
            ctx.fillStyle = '#FFF';
            ctx.font = 'bold 40px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            
            // Choose icon based on room name
            let icon = '🏢';
            if (dest.label && dest.label.toLowerCase().includes('food')) {
                icon = '🍴';
            } else if (dest.label && dest.label.toLowerCase().includes('bake')) {
                icon = '🍞';
            } else if (dest.label && dest.label.toLowerCase().includes('badminton')) {
                icon = '🏸';
            }
            ctx.fillText(icon, roomX, roomY);
        }
        
        // Label
        if (dest.label) {
            ctx.shadowColor = 'transparent';
            const maxLength = 20;
            const displayLabel = dest.label.length > maxLength ? dest.label.substring(0, maxLength) + '...' : dest.label;
            
            ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
            ctx.strokeStyle = '#333';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.roundRect(roomX - 75, roomY - 55, 150, 30, 5);
            ctx.fill();
            ctx.stroke();
            
            ctx.fillStyle = '#333';
            ctx.font = 'bold 15px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(displayLabel, roomX, roomY - 40);
        }
        
        ctx.restore();
    });
}

function drawReferencePoints(points) {
    ctx.save();
    
    points.forEach(point => {
        const pos = gridToCanvas(point.x, point.y);
        
        ctx.fillStyle = '#2196F3';
        ctx.strokeStyle = '#FFF';
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.7;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 8, 0, 2 * Math.PI);
        ctx.fill();
        ctx.stroke();
        
        // Show coordinates for integer points
        if (point.x % 1 === 0 && point.y % 1 === 0) {
            ctx.globalAlpha = 1;
            ctx.fillStyle = '#666';
            ctx.font = 'bold 14px Arial';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'bottom';
            ctx.fillText(`(${point.x},${point.y})`, pos.x + 12, pos.y - 12);
        }
    });
    
    ctx.restore();
}

function drawNearestNeighbors(neighbors) {
    ctx.save();
    
    neighbors.slice(0, 5).forEach((neighbor, index) => {
        const pos = gridToCanvas(neighbor.x, neighbor.y);
        
        // Draw connecting line
        if (currentPosition) {
            const currentPos = gridToCanvas(currentPosition.x, currentPosition.y);
            ctx.strokeStyle = '#FF9800';
            ctx.lineWidth = 3;
            ctx.globalAlpha = 0.3;
            ctx.setLineDash([8, 8]);
            ctx.beginPath();
            ctx.moveTo(pos.x, pos.y);
            ctx.lineTo(currentPos.x, currentPos.y);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.globalAlpha = 1;
        }
        
        // Draw neighbor circle
        ctx.shadowColor = 'rgba(255, 152, 0, 0.5)';
        ctx.shadowBlur = 8;
        ctx.fillStyle = '#FF9800';
        ctx.strokeStyle = '#FFF';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 15, 0, 2 * Math.PI);
        ctx.fill();
        ctx.stroke();
        
        // Rank number
        ctx.shadowColor = 'transparent';
        ctx.fillStyle = '#FFF';
        ctx.font = 'bold 16px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText((index + 1).toString(), pos.x, pos.y);
    });
    
    ctx.restore();
}

function drawPositionTrail() {
    // Filter history for current floor
    const floorHistory = positionHistory.filter(p => p.floor === currentFloor);
    
    if (floorHistory.length < 2) return;
    
    ctx.save();
    
    // Draw trail line
    ctx.strokeStyle = '#FF9800';
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.globalAlpha = 0.6;
    
    ctx.beginPath();
    floorHistory.forEach((pos, index) => {
        const canvasPos = gridToCanvas(pos.x, pos.y);
        if (index === 0) {
            ctx.moveTo(canvasPos.x, canvasPos.y);
        } else {
            ctx.lineTo(canvasPos.x, canvasPos.y);
        }
    });
    ctx.stroke();
    
    // Draw trail points (older = more transparent)
    floorHistory.forEach((pos, index) => {
        const canvasPos = gridToCanvas(pos.x, pos.y);
        const age = (floorHistory.length - index) / floorHistory.length;
        const alpha = 0.3 + (1 - age) * 0.5; // Fade from 0.3 to 0.8
        const radius = 4 + (1 - age) * 4; // Grow from 4 to 8
        
        ctx.globalAlpha = alpha;
        ctx.fillStyle = '#FF9800';
        ctx.beginPath();
        ctx.arc(canvasPos.x, canvasPos.y, radius, 0, 2 * Math.PI);
        ctx.fill();
        
        // Add white center to older points
        if (age > 0.5) {
            ctx.fillStyle = '#FFF';
            ctx.beginPath();
            ctx.arc(canvasPos.x, canvasPos.y, radius * 0.4, 0, 2 * Math.PI);
            ctx.fill();
        }
    });
    
    ctx.restore();
}

function drawCurrentPosition() {
    // Draw position history trail if tracking
    if (isTracking && positionHistory.length > 1) {
        drawPositionTrail();
    }
    
    const pos = gridToCanvas(currentPosition.x, currentPosition.y);
    ctx.save();
    
    // Pulsing outer circle (animated for tracking mode)
    ctx.strokeStyle = isTracking ? '#FF9800' : '#4CAF50';
    ctx.lineWidth = 4;
    ctx.globalAlpha = 0.4;
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, 35, 0, 2 * Math.PI);
    ctx.stroke();
    
    // Static outer ring
    ctx.globalAlpha = 1;
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, 28, 0, 2 * Math.PI);
    ctx.stroke();
    
    // Main position circle
    ctx.shadowColor = isTracking ? 'rgba(255, 152, 0, 0.5)' : 'rgba(76, 175, 80, 0.5)';
    ctx.shadowBlur = 10;
    ctx.fillStyle = isTracking ? '#FF9800' : '#4CAF50';
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, 20, 0, 2 * Math.PI);
    ctx.fill();
    
    // Center dot
    ctx.shadowColor = 'transparent';
    ctx.fillStyle = '#FFF';
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, 6, 0, 2 * Math.PI);
    ctx.fill();
    
    // Label background
    ctx.shadowColor = isTracking ? 'rgba(255, 152, 0, 0.5)' : 'rgba(76, 175, 80, 0.5)';
    ctx.shadowBlur = 8;
    ctx.fillStyle = isTracking ? '#FF9800' : '#4CAF50';
    ctx.beginPath();
    const labelText = isTracking ? 'TRACKING...' : 'YOU ARE HERE';
    const labelWidth = isTracking ? 130 : 160;
    ctx.roundRect(pos.x - labelWidth/2, pos.y - 70, labelWidth, 35, 8);
    ctx.fill();
    
    // Label text
    ctx.shadowColor = 'transparent';
    ctx.fillStyle = '#FFF';
    ctx.font = 'bold 20px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(labelText, pos.x, pos.y - 52);
    
    // Coordinates
    ctx.fillStyle = '#333';
    ctx.font = 'bold 16px Arial';
    ctx.fillText(`(${currentPosition.x.toFixed(2)}, ${currentPosition.y.toFixed(2)})`, pos.x, pos.y + 60);
    
    ctx.restore();
}