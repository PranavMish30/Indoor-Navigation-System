// Canvas drawing functions for floor plan

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
        
        // Determine room position based on entrance location
        let roomX = entrancePos.x;
        let roomY = entrancePos.y;
        
        // If in LEFT section (x: 0-3), room extends to the LEFT
        if (dest.x >= 0 && dest.x < 3) {
            roomX = entrancePos.x - 80;
        }
        // If in corridor (x: 3-20, y: 2-3), rooms extend UP or DOWN
        else if (dest.x >= 3 && dest.x <= 20 && dest.y >= 2 && dest.y <= 3) {
            if (dest.y > 2.5) {
                roomY = entrancePos.y - 60;
            } else {
                roomY = entrancePos.y + 60;
            }
        }
        // If in RIGHT section (x: 20-23), room extends to the RIGHT
        else if (dest.x >= 20 && dest.x <= 23) {
            roomX = entrancePos.x + 80;
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
            // Triangle
            ctx.fillStyle = '#FFD700';
            ctx.strokeStyle = '#FF8C00';
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.moveTo(roomX, roomY - 40);
            ctx.lineTo(roomX - 35, roomY + 25);
            ctx.lineTo(roomX + 35, roomY + 25);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
            
            // Icon
            ctx.shadowColor = 'transparent';
            ctx.fillStyle = '#333';
            ctx.font = 'bold 28px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('⬆', roomX, roomY);
        } else {
            // Connection line
            ctx.setLineDash([5, 3]);
            ctx.strokeStyle = '#1976D2';
            ctx.lineWidth = 2;
            ctx.globalAlpha = 0.4;
            ctx.beginPath();
            ctx.moveTo(entrancePos.x, entrancePos.y);
            ctx.lineTo(roomX, roomY);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.globalAlpha = 1;
            
            // Room rectangle with gradient
            const gradient = ctx.createLinearGradient(roomX - 70, roomY - 45, roomX - 70, roomY + 45);
            gradient.addColorStop(0, '#e3f2fd');
            gradient.addColorStop(1, '#bbdefb');
            ctx.fillStyle = gradient;
            ctx.strokeStyle = '#1976D2';
            ctx.lineWidth = 3;
            ctx.globalAlpha = 0.9;
            ctx.beginPath();
            ctx.roundRect(roomX - 70, roomY - 45, 140, 90, 8);
            ctx.fill();
            ctx.stroke();
            ctx.globalAlpha = 1;
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

function drawCurrentPosition() {
    const pos = gridToCanvas(currentPosition.x, currentPosition.y);
    ctx.save();
    
    // Pulsing outer circle (static in canvas, would need animation frame for pulse)
    ctx.strokeStyle = '#4CAF50';
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
    ctx.shadowColor = 'rgba(76, 175, 80, 0.5)';
    ctx.shadowBlur = 10;
    ctx.fillStyle = '#4CAF50';
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
    ctx.shadowColor = 'rgba(76, 175, 80, 0.5)';
    ctx.shadowBlur = 8;
    ctx.fillStyle = '#4CAF50';
    ctx.beginPath();
    ctx.roundRect(pos.x - 80, pos.y - 70, 160, 35, 8);
    ctx.fill();
    
    // "YOU ARE HERE" label
    ctx.shadowColor = 'transparent';
    ctx.fillStyle = '#FFF';
    ctx.font = 'bold 20px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('YOU ARE HERE', pos.x, pos.y - 52);
    
    // Coordinates
    ctx.fillStyle = '#333';
    ctx.font = 'bold 16px Arial';
    ctx.fillText(`(${currentPosition.x.toFixed(2)}, ${currentPosition.y.toFixed(2)})`, pos.x, pos.y + 60);
    
    ctx.restore();
}
