console.log('Dashboard JS loaded');
const video = document.getElementById('video');
const canvas = document.getElementById('overlay');
const ctx = canvas.getContext('2d');
const startBtn = document.getElementById('startBtn');
const placeholder = document.getElementById('placeholder');
const cameraStatus = document.getElementById('cameraStatus');

const scoreEl = document.getElementById('wellnessScore');
const blinkEl = document.getElementById('blinkRate');
const browEl = document.getElementById('browTension');
const exprEl = document.getElementById('expression');
const scoreFill = document.getElementById('scoreFill');
const tipText = document.getElementById('tipText');
const fpsEl = document.getElementById('fps');
const sessionLog = document.getElementById('sessionLog');

let ws;
let isRunning = false;
let lastFrameTime = 0;
let frameCount = 0;
let fps = 0;
let chart = null;
let lastSessionUpdate = 0;
let lastChartData = { score: 100, blink: 0 };

function initChart() {
    try {
        const chartCtx = document.getElementById('wellnessChart').getContext('2d');
        chart = new Chart(chartCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Wellness Score',
                    data: [],
                    borderColor: '#00ff88',
                    backgroundColor: 'rgba(0, 255, 136, 0.1)',
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 2
                }, {
                    label: 'Blink Rate',
                    data: [],
                    borderColor: '#00b4d8',
                    backgroundColor: 'rgba(0, 180, 216, 0.1)',
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 2.5,
                animation: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: 'rgba(0, 180, 216, 0.15)' },
                        ticks: { color: '#7a9aba', font: { size: 11 } }
                    },
                    x: {
                        grid: { color: 'rgba(0, 180, 216, 0.1)' },
                        ticks: { color: '#7a9aba', font: { size: 10 }, maxTicksLimit: 6 }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
        console.log('Chart initialized');
    } catch (e) {
        console.error('Chart init error:', e);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initChart);
} else {
    initChart();
}

function connectWebSocket() {
    ws = new WebSocket(`ws://${window.location.host}/ws/wellness/`);
    
    ws.onmessage = function(e) {
        const data = JSON.parse(e.data);
        updateMetrics(data);
    };
    
    ws.onclose = function(e) {
        console.log('WebSocket closed');
    };
}

function updateMetrics(data) {
    scoreEl.textContent = data.wellness_score;
    blinkEl.textContent = data.blink_rate;
    browEl.textContent = data.brow_tension;
    exprEl.textContent = data.expression;
    scoreFill.style.width = data.wellness_score + '%';
    tipText.textContent = data.tip;
    
    // Throttle session log updates to every 3 seconds
    const now = Date.now();
    if (now - lastSessionUpdate > 3000) {
        addSessionEntry(data);
        lastSessionUpdate = now;
    }
    
    // Update chart every 2 seconds
    if (chart && (now - lastChartData.updateTime > 2000 || !lastChartData.updateTime)) {
        const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        chart.data.labels.push(time);
        chart.data.datasets[0].data.push(data.wellness_score);
        chart.data.datasets[1].data.push(Math.min(100, data.blink_rate * 3));
        
        if (chart.data.labels.length > 20) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
            chart.data.datasets[1].data.shift();
        }
        
        chart.update('none');
        lastChartData.updateTime = now;
    }
}

function addSessionEntry(data) {
    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    const expression = data.expression.charAt(0).toUpperCase() + data.expression.slice(1);
    const exprClass = expression.toLowerCase();
    const badgeClass = exprClass === 'focused' ? 'focused' : exprClass === 'stressed' ? 'stressed' : 'neutral';
    
    const row = document.createElement('tr');
    row.innerHTML = `
        <td>${time}</td>
        <td>${data.wellness_score}</td>
        <td>${data.blink_rate}/min</td>
        <td><span class="expr-badge ${badgeClass}">${expression}</span></td>
    `;
    
    sessionLog.insertBefore(row, sessionLog.firstChild);
    
    // Keep only last 15 entries
    while (sessionLog.children.length > 15) {
        sessionLog.removeChild(sessionLog.lastChild);
    }
}

async function startCamera() {
    console.log('Start camera clicked');
    startBtn.disabled = true;
    startBtn.textContent = 'Starting...';
    cameraStatus.textContent = 'Requesting camera access...';
    cameraStatus.className = 'camera-status';
    
    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('Camera API not supported in this browser');
        }
        
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 640, height: 480, facingMode: 'user' } 
        });
        
        video.srcObject = stream;
        video.style.display = 'block';
        placeholder.style.display = 'none';
        startBtn.textContent = 'Stop camera';
        startBtn.disabled = false;
        isRunning = true;
        cameraStatus.textContent = 'Camera active - Detecting face...';
        cameraStatus.className = 'camera-status active';
        connectWebSocket();
        detectFace();
    } catch (err) {
        console.error('Camera error:', err);
        startBtn.textContent = 'Start camera';
        startBtn.disabled = false;
        cameraStatus.className = 'camera-status error';
        
        if (err.name === 'NotAllowedError') {
            cameraStatus.textContent = 'Camera permission denied';
        } else if (err.name === 'NotFoundError') {
            cameraStatus.textContent = 'No camera found';
        } else if (err.name === 'NotReadableError') {
            cameraStatus.textContent = 'Camera in use';
        } else {
            cameraStatus.textContent = 'Error: ' + err.message;
        }
    }
}

function stopCamera() {
    const stream = video.srcObject;
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    video.srcObject = null;
    placeholder.style.display = 'flex';
    startBtn.textContent = 'Start camera';
    isRunning = false;
    if (ws) ws.close();
}

async function detectFace() {
    if (!isRunning) return;
    
    const currentTime = performance.now();
    frameCount++;
    
    if (currentTime - lastFrameTime >= 1000) {
        fps = frameCount;
        frameCount = 0;
        lastFrameTime = currentTime;
        if (fpsEl) fpsEl.textContent = fps;
    }
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = 320;
    tempCanvas.height = 240;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.drawImage(video, 0, 0, 320, 240);
    const imageData = tempCanvas.toDataURL('image/jpeg', 0.6);
    
    try {
        const response = await fetch('/api/analyze/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ image: imageData })
        });
        
        const result = await response.json();
        
        if (result.face_detected && result.overlay) {
            cameraStatus.textContent = 'Face detected - Tracking...';
            cameraStatus.className = 'camera-status active';
            
            const img = new Image();
            img.onload = function() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            };
            img.src = result.overlay;
            
            if (result.wellness) {
                updateMetrics(result.wellness);
                
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify(result.wellness));
                }
            }
        } else {
            cameraStatus.textContent = 'Searching for face...';
            cameraStatus.className = 'camera-status';
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    } catch (err) {
        console.error('Analysis error:', err);
    }
    
    requestAnimationFrame(detectFace);
}

document.addEventListener('DOMContentLoaded', function() {
    const btn = document.getElementById('startBtn');
    
    btn.addEventListener('click', function() {
        if (isRunning) {
            stopCamera();
        } else {
            startCamera();
        }
    });
});

video.addEventListener('loadedmetadata', function() {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
});
