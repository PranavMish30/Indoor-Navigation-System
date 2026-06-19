let currentFloor = 0;
let referencePointsByFloor = {};
let availableFloors = [0];
let showRefPoints = true;
let currentPosition = null;
let destinations = [];
let navigationPath = [];
let sessionId = 'user_' + Math.random().toString(36).substr(2, 9);

// Auto-tracking state
let isTracking = false;
let trackingInterval = null;
let positionHistory = [];
const MAX_HISTORY = 20;
const TRACKING_INTERVAL_MS = 2500;

let svg, svgNS;
const SCALE = 100;
const LEFT_PADDING = 150;
const SVG_WIDTH = 2450;
const SVG_HEIGHT = 500;

// Bottom sheet state
let bottomSheet;
let startY = 0;
let currentY = 0;
let isDragging = false;
const MIN_HEIGHT = 80;
const DEFAULT_HEIGHT = 360;
const MAX_HEIGHT_PERCENT = 0.8;

// SVG pan and zoom state
let viewBox = { x: 0, y: 0, width: SVG_WIDTH, height: SVG_HEIGHT };
let isPanning = false;
let panStartPoint = { x: 0, y: 0 };
let scale = 1;

// Cached DOM elements for performance
let cachedElements = {};
let drawDebounceTimer = null;
const DRAW_DEBOUNCE_MS = 16; // ~60fps

// Haptic feedback helper
function hapticFeedback() {
    if (navigator.vibrate) {
        navigator.vibrate(10);
    }
}

document.addEventListener('DOMContentLoaded', async function() {
    svg = document.getElementById('floorPlan');
    svgNS = svg.namespaceURI;
    bottomSheet = document.getElementById('bottomSheet');
    
    // Cache DOM elements for performance
    cachedElements = {
        sections: document.getElementById('sections'),
        poiIcons: document.getElementById('poiIcons'),
        refPoints: document.getElementById('refPoints'),
        navPath: document.getElementById('navPath'),
        positionTrail: document.getElementById('positionTrail'),
        nearestNeighbors: document.getElementById('nearestNeighbors'),
        currentPos: document.getElementById('currentPos'),
        floorDisplay: document.getElementById('currentFloorDisplay'),
        scanStatus: document.getElementById('scanStatus')
    };

    // Button event listeners
    document.getElementById('getCurrentLocationBtn').addEventListener('click', () => {
        hapticFeedback();
        getCurrentLocation();
    });
    document.getElementById('startTrackingBtn').addEventListener('click', () => {
        hapticFeedback();
        toggleAutoTracking();
    });
    
    // Floor selector buttons
    document.getElementById('floorUpBtn').addEventListener('click', () => changeFloor(1));
    document.getElementById('floorDownBtn').addEventListener('click', () => changeFloor(-1));
    
    // Bottom sheet drag handlers
    const handle = document.querySelector('.bottom-sheet-handle');
    handle.addEventListener('touchstart', handleTouchStart, { passive: false });
    handle.addEventListener('touchmove', handleTouchMove, { passive: false });
    handle.addEventListener('touchend', handleTouchEnd, { passive: false });
    
    // Mouse events for testing on desktop
    handle.addEventListener('mousedown', handleMouseDown);

    // SVG pan/zoom
    setupSVGGestures();

    await loadReferencePoints();
    await loadDestinations();
    document.getElementById('navigateBtn').addEventListener('click', doNavigation);
    
    drawFloorPlan();
    
    // Set initial bottom sheet height (fully collapsed)
    bottomSheet.style.transform = `translateY(calc(100% - ${MIN_HEIGHT}px))`;
    
    // Hide loading screen and show map
    setTimeout(() => {
        const loadingScreen = document.getElementById('loadingScreen');
        const mapContainer = document.getElementById('mapContainer');
        if (loadingScreen) {
            loadingScreen.style.opacity = '0';
            setTimeout(() => {
                loadingScreen.classList.add('hidden');
                if (mapContainer) {
                    mapContainer.style.opacity = '1';
                }
            }, 300);
        }
    }, 500);
});

// Debounced draw function for performance
function debouncedDraw() {
    if (drawDebounceTimer) {
        cancelAnimationFrame(drawDebounceTimer);
    }
    drawDebounceTimer = requestAnimationFrame(() => {
        drawFloorPlan();
        drawDebounceTimer = null;
    });
}

// Floor selector functions
function changeFloor(direction) {
    const currentIndex = availableFloors.indexOf(currentFloor);
    const newIndex = currentIndex + direction;
    
    if (newIndex >= 0 && newIndex < availableFloors.length) {
        currentFloor = availableFloors[newIndex];
        cachedElements.floorDisplay.textContent = `F${currentFloor}`;
        debouncedDraw();
    }
}

// Bottom sheet drag handlers (Touch)
function handleTouchStart(e) {
    startY = e.touches[0].clientY;
    isDragging = true;
    bottomSheet.style.transition = 'none';
}

function handleTouchMove(e) {
    if (!isDragging) return;
    e.preventDefault();
    
    currentY = e.touches[0].clientY;
    const deltaY = currentY - startY;
    const maxHeight = window.innerHeight * MAX_HEIGHT_PERCENT;
    const currentTransform = bottomSheet.style.transform;
    const currentOffset = parseInt(currentTransform.match(/translateY\(calc\(100% - (\d+)px\)\)/)?.[1] || MIN_HEIGHT);
    
    let newHeight = currentOffset - deltaY;
    newHeight = Math.max(MIN_HEIGHT, Math.min(maxHeight, newHeight));
    
    bottomSheet.style.transform = `translateY(calc(100% - ${newHeight}px))`;
}

function handleTouchEnd(e) {
    if (!isDragging) return;
    isDragging = false;
    bottomSheet.style.transition = 'transform 0.3s ease';
    
    const deltaY = currentY - startY;
    const maxHeight = window.innerHeight * MAX_HEIGHT_PERCENT;
    const currentTransform = bottomSheet.style.transform;
    const currentHeight = parseInt(currentTransform.match(/translateY\(calc\(100% - (\d+)px\)\)/)?.[1] || MIN_HEIGHT);
    
    if (deltaY < -50) {
        if (currentHeight < DEFAULT_HEIGHT - 50) {
            bottomSheet.style.transform = `translateY(calc(100% - ${DEFAULT_HEIGHT}px))`;
        } else {
            bottomSheet.style.transform = `translateY(calc(100% - ${maxHeight}px))`;
        }
    } else if (deltaY > 50) {
        if (currentHeight > DEFAULT_HEIGHT + 50) {
            bottomSheet.style.transform = `translateY(calc(100% - ${DEFAULT_HEIGHT}px))`;
        } else {
            bottomSheet.style.transform = `translateY(calc(100% - ${MIN_HEIGHT}px))`;
        }
    } else {
        if (currentHeight < (MIN_HEIGHT + DEFAULT_HEIGHT) / 2) {
            bottomSheet.style.transform = `translateY(calc(100% - ${MIN_HEIGHT}px))`;
        } else if (currentHeight < (DEFAULT_HEIGHT + maxHeight) / 2) {
            bottomSheet.style.transform = `translateY(calc(100% - ${DEFAULT_HEIGHT}px))`;
        } else {
            bottomSheet.style.transform = `translateY(calc(100% - ${maxHeight}px))`;
        }
    }
}

// Mouse handlers for desktop testing
function handleMouseDown(e) {
    startY = e.clientY;
    isDragging = true;
    bottomSheet.style.transition = 'none';
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
}

function handleMouseMove(e) {
    if (!isDragging) return;
    
    currentY = e.clientY;
    const deltaY = currentY - startY;
    const maxHeight = window.innerHeight * MAX_HEIGHT_PERCENT;
    const currentTransform = bottomSheet.style.transform;
    const currentOffset = parseInt(currentTransform.match(/translateY\(calc\(100% - (\d+)px\)\)/)?.[1] || MIN_HEIGHT);
    
    let newHeight = currentOffset - deltaY;
    newHeight = Math.max(MIN_HEIGHT, Math.min(maxHeight, newHeight));
    
    bottomSheet.style.transform = `translateY(calc(100% - ${newHeight}px))`;
}

function handleMouseUp(e) {
    if (!isDragging) return;
    isDragging = false;
    bottomSheet.style.transition = 'transform 0.3s ease';
    
    const deltaY = currentY - startY;
    const maxHeight = window.innerHeight * MAX_HEIGHT_PERCENT;
    const currentTransform = bottomSheet.style.transform;
    const currentHeight = parseInt(currentTransform.match(/translateY\(calc\(100% - (\d+)px\)\)/)?.[1] || MIN_HEIGHT);
    
    if (deltaY < -50) {
        if (currentHeight < DEFAULT_HEIGHT - 50) {
            bottomSheet.style.transform = `translateY(calc(100% - ${DEFAULT_HEIGHT}px))`;
        } else {
            bottomSheet.style.transform = `translateY(calc(100% - ${maxHeight}px))`;
        }
    } else if (deltaY > 50) {
        if (currentHeight > DEFAULT_HEIGHT + 50) {
            bottomSheet.style.transform = `translateY(calc(100% - ${DEFAULT_HEIGHT}px))`;
        } else {
            bottomSheet.style.transform = `translateY(calc(100% - ${MIN_HEIGHT}px))`;
        }
    } else {
        if (currentHeight < (MIN_HEIGHT + DEFAULT_HEIGHT) / 2) {
            bottomSheet.style.transform = `translateY(calc(100% - ${MIN_HEIGHT}px))`;
        } else if (currentHeight < (DEFAULT_HEIGHT + maxHeight) / 2) {
            bottomSheet.style.transform = `translateY(calc(100% - ${DEFAULT_HEIGHT}px))`;
        } else {
            bottomSheet.style.transform = `translateY(calc(100% - ${maxHeight}px))`;
        }
    }
    
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
}

// SVG pan and zoom
function setupSVGGestures() {
    let startDistance = 0;
    let startScale = 1;
    let startViewBox = null;
    
    svg.addEventListener('touchstart', (e) => {
        if (e.touches.length === 2) {
            // Pinch zoom
            isPanning = false;
            startDistance = getTouchDistance(e.touches[0], e.touches[1]);
            startScale = scale;
            startViewBox = { ...viewBox };
        } else if (e.touches.length === 1) {
            // Single finger pan
            isPanning = true;
            panStartPoint = { 
                x: e.touches[0].clientX, 
                y: e.touches[0].clientY 
            };
        }
    }, { passive: false });
    
    svg.addEventListener('touchmove', (e) => {
        e.preventDefault();
        
        if (e.touches.length === 2) {
            // Pinch zoom
            const distance = getTouchDistance(e.touches[0], e.touches[1]);
            const newScale = startScale * (distance / startDistance);
            scale = Math.max(0.5, Math.min(3, newScale));
            updateViewBox();
        } else if (e.touches.length === 1 && isPanning) {
            // Pan with momentum
            const touch = e.touches[0];
            const dx = (panStartPoint.x - touch.clientX) * (viewBox.width / SVG_WIDTH);
            const dy = (panStartPoint.y - touch.clientY) * (viewBox.height / SVG_HEIGHT);
            
            viewBox.x += dx;
            viewBox.y += dy;
            
            // Use transform for smoother rendering
            requestAnimationFrame(() => {
                svg.setAttribute('viewBox', `${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`);
            });
            
            panStartPoint = { x: touch.clientX, y: touch.clientY };
        }
    }, { passive: false });
    
    svg.addEventListener('touchend', () => {
        isPanning = false;
    }, { passive: true });
    
    // Mouse wheel zoom
    svg.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        scale *= delta;
        scale = Math.max(0.5, Math.min(3, scale));
        updateViewBox();
    }, { passive: false });
    
    // Mouse drag
    svg.addEventListener('mousedown', (e) => {
        isPanning = true;
        panStartPoint = { x: e.clientX, y: e.clientY };
        svg.style.cursor = 'grabbing';
    });
    
    svg.addEventListener('mousemove', (e) => {
        if (!isPanning) return;
        
        const dx = (panStartPoint.x - e.clientX) * (viewBox.width / SVG_WIDTH);
        const dy = (panStartPoint.y - e.clientY) * (viewBox.height / SVG_HEIGHT);
        
        viewBox.x += dx;
        viewBox.y += dy;
        
        requestAnimationFrame(() => {
            svg.setAttribute('viewBox', `${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`);
        });
        
        panStartPoint = { x: e.clientX, y: e.clientY };
    });
    
    svg.addEventListener('mouseup', () => {
        isPanning = false;
        svg.style.cursor = 'grab';
    });
    
    svg.addEventListener('mouseleave', () => {
        isPanning = false;
        svg.style.cursor = 'grab';
    });
    
    // Double tap/click to reset
    svg.addEventListener('dblclick', resetView);
    
    // Set initial cursor
    svg.style.cursor = 'grab';
}

function getSVGPoint(event) {
    const CTM = svg.getScreenCTM();
    return {
        x: (event.clientX - CTM.e) / CTM.a,
        y: (event.clientY - CTM.f) / CTM.d
    };
}

function getTouchDistance(touch1, touch2) {
    const dx = touch1.clientX - touch2.clientX;
    const dy = touch1.clientY - touch2.clientY;
    return Math.sqrt(dx * dx + dy * dy);
}

function updateViewBox() {
    const newWidth = SVG_WIDTH / scale;
    const newHeight = SVG_HEIGHT / scale;
    const centerX = viewBox.x + viewBox.width / 2;
    const centerY = viewBox.y + viewBox.height / 2;
    
    viewBox = {
        x: centerX - newWidth / 2,
        y: centerY - newHeight / 2,
        width: newWidth,
        height: newHeight
    };
    
    svg.setAttribute('viewBox', `${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`);
}

function resetView() {
    scale = 1;
    viewBox = { x: 0, y: 0, width: SVG_WIDTH, height: SVG_HEIGHT };
    svg.setAttribute('viewBox', `0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`);
    hapticFeedback();
}

async function loadReferencePoints() {
    try {
        const response = await fetch('/api/reference-points');
        const data = await response.json();
        
        for (const point of data) {
            const floor = point.floor;
            if (!referencePointsByFloor[floor]) {
                referencePointsByFloor[floor] = [];
            }
            referencePointsByFloor[floor].push(point);
        }
        
        availableFloors = Object.keys(referencePointsByFloor)
            .map(f => parseInt(f, 10))
            .sort((a, b) => a - b);
        
        if (availableFloors.length > 0) {
            currentFloor = availableFloors[0];
            document.getElementById('currentFloorDisplay').textContent = `F${currentFloor}`;
        }
        
        console.log('Reference points loaded:', data.length);
    } catch (error) {
        console.error('Error loading reference points:', error);
        showStatus('Failed to load reference points', 'error');
    }
}

async function loadDestinations() {
    try {
        const response = await fetch('/api/destinations');
        const data = await response.json();
        destinations = data;
        
        const select = document.getElementById('destinationSelect');
        select.innerHTML = '<option value="">Select destination...</option>';
        
        destinations.forEach(dest => {
            const option = document.createElement('option');
            option.value = dest.label;
            option.textContent = `${dest.label} (Floor ${dest.floor})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading destinations:', error);
    }
}

async function getCurrentLocation() {
    const btn = document.getElementById('getCurrentLocationBtn');
    btn.disabled = true;
    btn.style.opacity = '0.6';
    
    showStatus('Scanning WiFi networks...', 'info');
    
    try {
        const scanResponse = await fetch('/api/scan');
        const scanData = await scanResponse.json();
        
        if (scanData.error) {
            showStatus(scanData.error, 'error');
            btn.disabled = false;
            btn.style.opacity = '1';
            return;
        }
        
        if (scanData.count === 0) {
            showStatus('No BMSIT networks detected', 'error');
            btn.disabled = false;
            btn.style.opacity = '1';
            return;
        }
        
        showStatus(`Found ${scanData.count} APs, calculating position...`, 'info');
        
        const response = await fetch('/api/locate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                scan: scanData.aps,
                algorithm: 'hybrid',
                session_id: sessionId,
                use_kalman: false
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            showStatus(data.error, 'error');
            return;
        }
        
        currentPosition = {
            x: data.x,
            y: data.y,
            floor: data.floor,
            section: data.section || 'Unknown',
            confidence: data.confidence,
            detected_aps: data.detected_aps || 0,
            algorithm: 'Hybrid',
            nearest: data.nearest || []
        };
        
        if (data.floor !== currentFloor) {
            currentFloor = data.floor;
            document.getElementById('currentFloorDisplay').textContent = `F${currentFloor}`;
        }
        
        updatePositionDisplay();
        drawFloorPlan();
        showStatus('Location found!', 'success');
        
    } catch (error) {
        console.error('Error getting location:', error);
        showStatus('Failed to get location', 'error');
    } finally {
        btn.disabled = false;
        btn.style.opacity = '1';
    }
}

async function toggleAutoTracking() {
    const btn = document.getElementById('startTrackingBtn');
    
    if (isTracking) {
        isTracking = false;
        if (trackingInterval) {
            clearInterval(trackingInterval);
            trackingInterval = null;
        }
        btn.classList.remove('active');
        positionHistory = [];
        showStatus('Tracking stopped', 'info');
    } else {
        isTracking = true;
        btn.classList.add('active');
        showStatus('Tracking started...', 'success');
        
        await performAutoScan();
        trackingInterval = setInterval(performAutoScan, TRACKING_INTERVAL_MS);
    }
    
    drawFloorPlan();
}

async function performAutoScan() {
    if (!isTracking) return;
    
    try {
        const scanResponse = await fetch('/api/scan');
        const scanData = await scanResponse.json();
        
        if (scanData.error || scanData.count === 0) {
            console.error('Scan error:', scanData.error || 'No networks found');
            return;
        }
        
        const response = await fetch('/api/locate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                scan: scanData.aps,
                algorithm: 'ensemble-kalman',
                session_id: sessionId,
                use_kalman: true
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            console.error('Tracking error:', data.error);
            return;
        }
        
        positionHistory.push({
            x: data.x,
            y: data.y,
            timestamp: Date.now()
        });
        
        if (positionHistory.length > MAX_HISTORY) {
            positionHistory.shift();
        }
        
        currentPosition = {
            x: data.x,
            y: data.y,
            floor: data.floor,
            section: data.section || 'Unknown',
            confidence: data.confidence,
            detected_aps: data.detected_aps || 0,
            algorithm: 'Ensemble + Kalman',
            nearest: data.nearest || []
        };
        
        if (data.floor !== currentFloor) {
            currentFloor = data.floor;
            document.getElementById('currentFloorDisplay').textContent = `F${currentFloor}`;
        }
        
        updatePositionDisplay();
        drawFloorPlan();
        
    } catch (error) {
        console.error('Auto-scan error:', error);
    }
}

function updatePositionDisplay() {
    if (!currentPosition) return;
    
    document.getElementById('floorValue').textContent = currentPosition.floor;
    document.getElementById('sectionValue').textContent = currentPosition.section;
    document.getElementById('coordValue').textContent = `(${currentPosition.x.toFixed(1)}, ${currentPosition.y.toFixed(1)})`;
    document.getElementById('confidenceValue').textContent = `${(currentPosition.confidence * 100).toFixed(0)}%`;
    document.getElementById('apsValue').textContent = currentPosition.detected_aps;
    document.getElementById('algorithmValue').textContent = currentPosition.algorithm;
    
    const neighborsContainer = document.getElementById('nearestNeighbors');
    if (currentPosition.nearest && currentPosition.nearest.length > 0) {
        neighborsContainer.innerHTML = currentPosition.nearest.map((n, idx) => `
            <div class="neighbor-item">
                <div class="neighbor-info">
                    <span class="neighbor-label">#${idx + 1} Reference Point</span>
                    <span class="neighbor-coords">(${n.x}, ${n.y})</span>
                </div>
                <span class="neighbor-distance">${n.distance.toFixed(1)}m</span>
            </div>
        `).join('');
    } else {
        neighborsContainer.innerHTML = '<p class="placeholder">No nearby points</p>';
    }
}

async function doNavigation() {
    const select = document.getElementById('destinationSelect');
    const destLabel = select.value;
    
    if (!destLabel) {
        showNavStatus('Please select a destination');
        return;
    }
    
    if (!currentPosition) {
        showNavStatus('Get your location first');
        return;
    }
    
    const dest = destinations.find(d => d.label === destLabel);
    if (!dest) return;
    
    try {
        const response = await fetch('/api/navigate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start_x: currentPosition.x,
                start_y: currentPosition.y,
                start_floor: currentPosition.floor,
                end_x: dest.x,
                end_y: dest.y,
                end_floor: dest.floor
            })
        });
        
        const data = await response.json();
        
        if (data.path) {
            navigationPath = data.path.map(p => ({ x: p[0], y: p[1] }));
            drawFloorPlan();
            showNavStatus(`Route found: ${data.distance.toFixed(1)}m`);
        } else {
            showNavStatus('No path found');
        }
    } catch (error) {
        console.error('Navigation error:', error);
        showNavStatus('Navigation failed');
    }
}

function showStatus(message, type) {
    const status = document.getElementById('scanStatus');
    status.textContent = message;
    status.className = `status ${type}`;
    status.classList.remove('hidden');
    
    if (type === 'success') {
        setTimeout(() => {
            status.classList.add('hidden');
        }, 3000);
    } else if (type === 'error') {
        setTimeout(() => {
            status.classList.add('hidden');
        }, 5000);
    }
}

function showNavStatus(message) {
    const status = document.getElementById('navStatus');
    status.textContent = message;
}

function drawFloorPlan() {
    // Clear all groups
    document.getElementById('sections').innerHTML = '';
    document.getElementById('refPoints').innerHTML = '';
    document.getElementById('navPath').innerHTML = '';
    document.getElementById('positionTrail').innerHTML = '';
    document.getElementById('nearestNeighbors').innerHTML = '';
    document.getElementById('currentPos').innerHTML = '';
    
    const points = referencePointsByFloor[currentFloor] || [];
    
    if (points.length === 0) {
        const text = document.createElementNS(svgNS, 'text');
        text.setAttribute('x', '1300');
        text.setAttribute('y', '300');
        text.setAttribute('fill', '#94a3b8');
        text.setAttribute('font-size', '24');
        text.setAttribute('text-anchor', 'middle');
        text.textContent = 'No reference points for this floor';
        document.getElementById('sections').appendChild(text);
        return;
    }
    
    // Draw floor sections
    drawFloorSections();
    
    // Draw POI icons
    drawPOIIcons();
    
    // Draw reference points
    if (showRefPoints) {
        points.forEach(point => {
            // Use same conversion as desktop: grid (0,0) is center of bottom-left cell
            const x = LEFT_PADDING + (point.x + 0.5) * SCALE;
            const y = SVG_HEIGHT - (point.y + 0.5) * SCALE;
            
            const circle = document.createElementNS(svgNS, 'circle');
            circle.setAttribute('cx', x);
            circle.setAttribute('cy', y);
            circle.setAttribute('r', '6');
            circle.setAttribute('fill', '#06b6d4');
            circle.setAttribute('filter', 'drop-shadow(0 0 8px rgba(6, 182, 212, 0.8))');
            
            document.getElementById('refPoints').appendChild(circle);
        });
    }
    
    // Draw navigation path
    if (navigationPath.length > 0) {
        const pathData = navigationPath.map((p, idx) => {
            const x = LEFT_PADDING + (p.x + 0.5) * SCALE;
            const y = SVG_HEIGHT - (p.y + 0.5) * SCALE;
            return `${idx === 0 ? 'M' : 'L'} ${x} ${y}`;
        }).join(' ');
        
        const path = document.createElementNS(svgNS, 'path');
        path.setAttribute('d', pathData);
        path.setAttribute('stroke', '#ec4899');
        path.setAttribute('stroke-width', '4');
        path.setAttribute('fill', 'none');
        path.setAttribute('filter', 'drop-shadow(0 0 10px rgba(236, 72, 153, 0.6))');
        
        document.getElementById('navPath').appendChild(path);
    }
    
    // Draw position history trail
    if (positionHistory.length > 1) {
        const trailData = positionHistory.map((pos, idx) => {
            const x = LEFT_PADDING + (pos.x + 0.5) * SCALE;
            const y = SVG_HEIGHT - (pos.y + 0.5) * SCALE;
            return `${idx === 0 ? 'M' : 'L'} ${x} ${y}`;
        }).join(' ');
        
        const trail = document.createElementNS(svgNS, 'path');
        trail.setAttribute('d', trailData);
        trail.setAttribute('stroke', 'rgba(16, 185, 129, 0.4)');
        trail.setAttribute('stroke-width', '3');
        trail.setAttribute('fill', 'none');
        trail.setAttribute('stroke-linecap', 'round');
        
        document.getElementById('positionTrail').appendChild(trail);
    }
    
    // Draw current position
    if (currentPosition && currentPosition.floor === currentFloor) {
        const x = LEFT_PADDING + (currentPosition.x + 0.5) * SCALE;
        const y = SVG_HEIGHT - (currentPosition.y + 0.5) * SCALE;
        
        // Draw nearest neighbors
        if (currentPosition.nearest) {
            currentPosition.nearest.forEach(n => {
                const nx = LEFT_PADDING + (n.x + 0.5) * SCALE;
                const ny = SVG_HEIGHT - (n.y + 0.5) * SCALE;
                
                const line = document.createElementNS(svgNS, 'line');
                line.setAttribute('x1', x);
                line.setAttribute('y1', y);
                line.setAttribute('x2', nx);
                line.setAttribute('y2', ny);
                line.setAttribute('stroke', 'rgba(16, 185, 129, 0.3)');
                line.setAttribute('stroke-width', '2');
                
                document.getElementById('nearestNeighbors').appendChild(line);
                
                const nCircle = document.createElementNS(svgNS, 'circle');
                nCircle.setAttribute('cx', nx);
                nCircle.setAttribute('cy', ny);
                nCircle.setAttribute('r', '6');
                nCircle.setAttribute('fill', '#10b981');
                nCircle.setAttribute('filter', 'drop-shadow(0 0 6px rgba(16, 185, 129, 0.6))');
                
                document.getElementById('nearestNeighbors').appendChild(nCircle);
            });
        }
        
        // Draw current position marker
        const color = isTracking ? '#10b981' : '#06b6d4';
        
        const outerCircle = document.createElementNS(svgNS, 'circle');
        outerCircle.setAttribute('cx', x);
        outerCircle.setAttribute('cy', y);
        outerCircle.setAttribute('r', '15');
        outerCircle.setAttribute('fill', color);
        outerCircle.setAttribute('filter', 'drop-shadow(0 0 12px ' + color + ')');
        
        const innerCircle = document.createElementNS(svgNS, 'circle');
        innerCircle.setAttribute('cx', x);
        innerCircle.setAttribute('cy', y);
        innerCircle.setAttribute('r', '6');
        innerCircle.setAttribute('fill', '#ffffff');
        
        document.getElementById('currentPos').appendChild(outerCircle);
        document.getElementById('currentPos').appendChild(innerCircle);
    }
}

function drawFloorSections() {
    // Left Section: 3x4 grid (gridX: 0-2, gridY: 0-3)
    const leftGradient = createLinearGradient('#06b6d4', '#0e7490');
    for (let gridX = 0; gridX < 3; gridX++) {
        for (let gridY = 0; gridY < 4; gridY++) {
            const x = LEFT_PADDING + gridX * SCALE;
            const y = SVG_HEIGHT - (gridY + 1) * SCALE;
            const rect = document.createElementNS(svgNS, 'rect');
            rect.setAttribute('x', x);
            rect.setAttribute('y', y);
            rect.setAttribute('width', SCALE);
            rect.setAttribute('height', SCALE);
            rect.setAttribute('fill', leftGradient);
            rect.setAttribute('fill-opacity', '0.15');
            document.getElementById('sections').appendChild(rect);
        }
    }
    // Left border
    const leftBorder = document.createElementNS(svgNS, 'rect');
    leftBorder.setAttribute('x', LEFT_PADDING);
    leftBorder.setAttribute('y', SVG_HEIGHT - 4 * SCALE);
    leftBorder.setAttribute('width', 3 * SCALE);
    leftBorder.setAttribute('height', 4 * SCALE);
    leftBorder.setAttribute('fill', 'none');
    leftBorder.setAttribute('stroke', '#06b6d4');
    leftBorder.setAttribute('stroke-width', '4');
    leftBorder.setAttribute('filter', 'drop-shadow(0 0 10px rgba(6, 182, 212, 0.5))');
    document.getElementById('sections').appendChild(leftBorder);
    // Left label
    const leftText = document.createElementNS(svgNS, 'text');
    leftText.setAttribute('x', LEFT_PADDING + 1.5 * SCALE);
    leftText.setAttribute('y', SVG_HEIGHT - 2 * SCALE);
    leftText.setAttribute('fill', '#06b6d4');
    leftText.setAttribute('fill-opacity', '0.4');
    leftText.setAttribute('font-size', '32');
    leftText.setAttribute('font-weight', 'bold');
    leftText.setAttribute('text-anchor', 'middle');
    leftText.textContent = 'LEFT';
    document.getElementById('sections').appendChild(leftText);
    
    // Corridor: horizontal strip (gridX: 3-19, gridY: 2.5-3.5)
    const corridorGradient = createLinearGradient('#10b981', '#059669');
    for (let gridX = 3; gridX < 20; gridX++) {
        const x = LEFT_PADDING + gridX * SCALE;
        const y = SVG_HEIGHT - 3.5 * SCALE;
        const rect = document.createElementNS(svgNS, 'rect');
        rect.setAttribute('x', x);
        rect.setAttribute('y', y);
        rect.setAttribute('width', SCALE);
        rect.setAttribute('height', SCALE);
        rect.setAttribute('fill', corridorGradient);
        rect.setAttribute('fill-opacity', '0.15');
        document.getElementById('sections').appendChild(rect);
    }
    // Corridor border
    const corridorBorder = document.createElementNS(svgNS, 'rect');
    corridorBorder.setAttribute('x', LEFT_PADDING + 3 * SCALE);
    corridorBorder.setAttribute('y', SVG_HEIGHT - 3.5 * SCALE);
    corridorBorder.setAttribute('width', 17 * SCALE);
    corridorBorder.setAttribute('height', SCALE);
    corridorBorder.setAttribute('fill', 'none');
    corridorBorder.setAttribute('stroke', '#10b981');
    corridorBorder.setAttribute('stroke-width', '4');
    corridorBorder.setAttribute('filter', 'drop-shadow(0 0 10px rgba(16, 185, 129, 0.5))');
    document.getElementById('sections').appendChild(corridorBorder);
    // Corridor label
    const corridorText = document.createElementNS(svgNS, 'text');
    corridorText.setAttribute('x', LEFT_PADDING + 11.5 * SCALE);
    corridorText.setAttribute('y', SVG_HEIGHT - 2.35 * SCALE);
    corridorText.setAttribute('fill', '#10b981');
    corridorText.setAttribute('fill-opacity', '0.45');
    corridorText.setAttribute('font-size', '36');
    corridorText.setAttribute('font-weight', 'bold');
    corridorText.setAttribute('text-anchor', 'middle');
    corridorText.textContent = 'CORRIDOR';
    document.getElementById('sections').appendChild(corridorText);
    
    // Right Section: 3x4 grid (gridX: 20-22, gridY: 0-3)
    const rightGradient = createLinearGradient('#0891b2', '#0e7490');
    for (let gridX = 20; gridX < 23; gridX++) {
        for (let gridY = 0; gridY < 4; gridY++) {
            const x = LEFT_PADDING + gridX * SCALE;
            const y = SVG_HEIGHT - (gridY + 1) * SCALE;
            const rect = document.createElementNS(svgNS, 'rect');
            rect.setAttribute('x', x);
            rect.setAttribute('y', y);
            rect.setAttribute('width', SCALE);
            rect.setAttribute('height', SCALE);
            rect.setAttribute('fill', rightGradient);
            rect.setAttribute('fill-opacity', '0.15');
            document.getElementById('sections').appendChild(rect);
        }
    }
    // Right border
    const rightBorder = document.createElementNS(svgNS, 'rect');
    rightBorder.setAttribute('x', LEFT_PADDING + 20 * SCALE);
    rightBorder.setAttribute('y', SVG_HEIGHT - 4 * SCALE);
    rightBorder.setAttribute('width', 3 * SCALE);
    rightBorder.setAttribute('height', 4 * SCALE);
    rightBorder.setAttribute('fill', 'none');
    rightBorder.setAttribute('stroke', '#0891b2');
    rightBorder.setAttribute('stroke-width', '4');
    rightBorder.setAttribute('filter', 'drop-shadow(0 0 10px rgba(8, 145, 178, 0.5))');
    document.getElementById('sections').appendChild(rightBorder);
    // Right label
    const rightText = document.createElementNS(svgNS, 'text');
    rightText.setAttribute('x', LEFT_PADDING + 21.5 * SCALE);
    rightText.setAttribute('y', SVG_HEIGHT - 2 * SCALE);
    rightText.setAttribute('fill', '#0891b2');
    rightText.setAttribute('fill-opacity', '0.4');
    rightText.setAttribute('font-size', '32');
    rightText.setAttribute('font-weight', 'bold');
    rightText.setAttribute('text-anchor', 'middle');
    rightText.textContent = 'RIGHT';
    document.getElementById('sections').appendChild(rightText);
}

function createLinearGradient(color1, color2) {
    return color1; // SVG gradients need proper defs, using solid color for now
}

function drawPOIIcons() {
    if (!destinations || destinations.length === 0) {
        console.log('No destinations to draw');
        return;
    }
    
    const poiGroup = document.getElementById('poiIcons');
    if (!poiGroup) {
        console.error('POI icons group not found!');
        return;
    }
    
    // Clear existing POI icons
    while (poiGroup.firstChild) {
        poiGroup.removeChild(poiGroup.firstChild);
    }
    
    console.log(`Drawing ${destinations.length} destinations for floor ${currentFloor}`);
    
    destinations.forEach(dest => {
        if (dest.floor !== currentFloor) return;
        
        // Calculate entrance/corridor position
        const entranceX = LEFT_PADDING + (dest.x + 0.5) * SCALE;
        const entranceY = SVG_HEIGHT - (dest.y + 0.5) * SCALE;
        
        // Determine room position based on side property
        let roomX = entranceX;
        let roomY = entranceY;
        const iconSize = 16;
        
        // Position POI outside corridor based on side
        if (dest.side === 'left') {
            roomX = entranceX - 150; // Left of corridor
        } else if (dest.side === 'right') {
            roomX = entranceX + 150; // Right of corridor
        } else if (dest.side === 'top') {
            roomY = entranceY - 120; // Above corridor (lower Y)
        } else if (dest.side === 'bottom') {
            roomY = entranceY + 120; // Below corridor (higher Y)
        }
        
        const x = roomX;
        const y = roomY;
        
        // Determine icon and color based on type
        let icon = '🏢';
        let color = '#AB47BC';
        let strokeColor = '#6A1B9A';
        
        if (dest.type === 'lab') {
            icon = '🔬';
            color = '#42A5F5';
            strokeColor = '#1976D2';
        } else if (dest.type === 'classroom') {
            icon = '📖';
            color = '#66BB6A';
            strokeColor = '#2E7D32';
        } else if (dest.label) {
            if (dest.label.toLowerCase().includes('food')) {
                icon = '🍴';
            } else if (dest.label.toLowerCase().includes('bake')) {
                icon = '🍞';
            } else if (dest.label.toLowerCase().includes('badminton')) {
                icon = '🏸';
            }
        }
        
        // Draw entrance marker (red dot on corridor)
        const entranceCircle = document.createElementNS(svgNS, 'circle');
        entranceCircle.setAttribute('cx', entranceX);
        entranceCircle.setAttribute('cy', entranceY);
        entranceCircle.setAttribute('r', '6');
        entranceCircle.setAttribute('fill', '#FF5722');
        entranceCircle.setAttribute('stroke', '#FFF');
        entranceCircle.setAttribute('stroke-width', '2');
        poiGroup.appendChild(entranceCircle);
        
        // Draw connecting line from room to entrance
        const line = document.createElementNS(svgNS, 'line');
        line.setAttribute('x1', x);
        line.setAttribute('y1', y);
        line.setAttribute('x2', entranceX);
        line.setAttribute('y2', entranceY);
        line.setAttribute('stroke', color);
        line.setAttribute('stroke-width', '2');
        line.setAttribute('stroke-dasharray', '5,3');
        line.setAttribute('opacity', '0.5');
        poiGroup.appendChild(line);
        
        // Draw circle background
        const circle = document.createElementNS(svgNS, 'circle');
        circle.setAttribute('cx', x);
        circle.setAttribute('cy', y);
        circle.setAttribute('r', iconSize);
        circle.setAttribute('fill', color);
        circle.setAttribute('stroke', strokeColor);
        circle.setAttribute('stroke-width', '3');
        circle.setAttribute('filter', 'drop-shadow(0 0 8px rgba(0, 0, 0, 0.4))');
        poiGroup.appendChild(circle);
        
        // Draw icon text
        const text = document.createElementNS(svgNS, 'text');
        text.setAttribute('x', x);
        text.setAttribute('y', y);
        text.setAttribute('font-size', '24');
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('dominant-baseline', 'central');
        text.textContent = icon;
        poiGroup.appendChild(text);
        
        // Draw top label (name) background
        if (dest.label) {
            const labelWidth = dest.label.length * 8 + 20;
            const labelRect = document.createElementNS(svgNS, 'rect');
            labelRect.setAttribute('x', x - labelWidth / 2);
            labelRect.setAttribute('y', y - iconSize - 30);
            labelRect.setAttribute('width', labelWidth);
            labelRect.setAttribute('height', '22');
            labelRect.setAttribute('rx', '5');
            labelRect.setAttribute('fill', 'rgba(255, 255, 255, 0.95)');
            labelRect.setAttribute('stroke', '#333');
            labelRect.setAttribute('stroke-width', '1.5');
            poiGroup.appendChild(labelRect);
            
            // Draw top label text
            const labelText = document.createElementNS(svgNS, 'text');
            labelText.setAttribute('x', x);
            labelText.setAttribute('y', y - iconSize - 19);
            labelText.setAttribute('font-size', '12');
            labelText.setAttribute('font-weight', 'bold');
            labelText.setAttribute('fill', '#333');
            labelText.setAttribute('text-anchor', 'middle');
            labelText.setAttribute('dominant-baseline', 'middle');
            const displayLabel = dest.label.length > 20 ? dest.label.substring(0, 20) + '...' : dest.label;
            labelText.textContent = displayLabel;
            poiGroup.appendChild(labelText);
        }
        
        // Draw bottom label (coordinates)
        const coordText = `(${dest.x}, ${dest.y})`;
        const coordWidth = coordText.length * 7 + 16;
        const coordRect = document.createElementNS(svgNS, 'rect');
        coordRect.setAttribute('x', x - coordWidth / 2);
        coordRect.setAttribute('y', y + iconSize + 8);
        coordRect.setAttribute('width', coordWidth);
        coordRect.setAttribute('height', '20');
        coordRect.setAttribute('rx', '4');
        coordRect.setAttribute('fill', 'rgba(0, 0, 0, 0.8)');
        coordRect.setAttribute('stroke', color);
        coordRect.setAttribute('stroke-width', '1');
        poiGroup.appendChild(coordRect);
        
        // Draw bottom label text
        const coordTextEl = document.createElementNS(svgNS, 'text');
        coordTextEl.setAttribute('x', x);
        coordTextEl.setAttribute('y', y + iconSize + 18);
        coordTextEl.setAttribute('font-size', '11');
        coordTextEl.setAttribute('font-weight', '600');
        coordTextEl.setAttribute('fill', '#FFF');
        coordTextEl.setAttribute('text-anchor', 'middle');
        coordTextEl.setAttribute('dominant-baseline', 'middle');
        coordTextEl.textContent = coordText;
        poiGroup.appendChild(coordTextEl);
    });
}
