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

let ws;
let isRunning = false;
let lastFrameTime = 0;
let frameCount = 0;
let fps = 0;
let chart = null;

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
                    tension: 0.4,
                    fill: false
                }, {
                    label: 'Blink Rate',
                    data: [],
                    borderColor: '#00d4ff',
                    tension: 0.4,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { color: '#888' }
                    },
                    x: {
                        grid: { color: 'rgba(255,255,255,0.1)' },
                        ticks: { color: '#888' }
                    }
                },
                plugins: {
                    legend: { labels: { color: '#fff' } }
                }
            }
        });
        console.log('Chart initialized');
    } catch (e) {
        console.error('Chart init error:', e);
    }
}

// Initialize when DOM is ready
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
    
    if (chart) {
        const time = new Date().toLocaleTimeString();
        chart.data.labels.push(time);
        chart.data.datasets[0].data.push(data.wellness_score);
        chart.data.datasets[1].data.push(data.blink_rate * 5);
        
        if (chart.data.labels.length > 30) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
            chart.data.datasets[1].data.shift();
        }
        
        chart.update('none');
    }
}

async function startCamera() {
    console.log('Start camera clicked');
    startBtn.disabled = true;
    startBtn.textContent = 'Starting...';
    cameraStatus.textContent = 'Requesting camera access...';
    cameraStatus.className = 'camera-status';
    
    try {
        console.log('Checking camera API...');
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('Camera API not supported in this browser');
        }
        console.log('Camera API available, requesting stream...');
        
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 640, height: 480, facingMode: 'user' } 
        });
        console.log('Camera stream obtained:', stream);
        
        video.srcObject = stream;
        video.style.display = 'block';
        placeholder.style.display = 'none';
        startBtn.textContent = 'Stop Camera';
        startBtn.disabled = false;
        isRunning = true;
        cameraStatus.textContent = 'Camera active - Detecting face...';
        cameraStatus.className = 'camera-status active';
        console.log('Connecting WebSocket...');
        connectWebSocket();
        console.log('Starting face detection...');
        detectFace();
    } catch (err) {
        console.error('Camera error:', err);
        startBtn.textContent = 'Start Camera';
        startBtn.disabled = false;
        cameraStatus.className = 'camera-status error';
        
        if (err.name === 'NotAllowedError') {
            cameraStatus.textContent = 'Camera permission denied';
            alert('Camera permission denied.\n\nTo fix:\n1. Click the lock/camera icon in address bar\n2. Select "Allow" for camera\n3. Refresh page');
        } else if (err.name === 'NotFoundError') {
            cameraStatus.textContent = 'No camera found';
            alert('No camera found.\n\nPlease connect a webcam and try again.');
        } else if (err.name === 'NotReadableError') {
            cameraStatus.textContent = 'Camera in use';
            alert('Camera is in use by another application.\n\nClose other apps using camera and try again.');
        } else {
            cameraStatus.textContent = 'Error: ' + err.message;
            alert('Camera error: ' + err.message);
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
    startBtn.textContent = 'Start Camera';
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
    
    // capture frame - smaller size for better performance
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = 320;
    tempCanvas.height = 240;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.drawImage(video, 0, 0, 320, 240);
    const imageData = tempCanvas.toDataURL('image/jpeg', 0.6);
    
    try {
        console.log('Sending frame to server...');
        const response = await fetch('/api/analyze/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ image: imageData })
        });
        
        console.log('Response received:', response.status);
        const result = await response.json();
        console.log('Analysis result:', result);
        
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
    console.log('DOM loaded, attaching event listener');
    const btn = document.getElementById('startBtn');
    console.log('Button found:', btn);
    
    btn.addEventListener('click', function() {
        console.log('=== BUTTON CLICKED ===');
        if (isRunning) {
            stopCamera();
        } else {
            startCamera();
        }
    });
    
    console.log('Event listener attached');
});

video.addEventListener('loadedmetadata', function() {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
});
