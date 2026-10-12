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
let lastSessionEntryTime = 0;
let lastChartTime = 0;

let lowScoreStartTime = null;
let breakCooldownUntil = 0;
const LOW_SCORE_THRESHOLD = 50;
const LOW_SCORE_DURATION_MS = 10000;
const BREAK_COOLDOWN_MS = 120000;

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
                    yAxisID: 'y'
                }, {
                    label: 'Blink Rate',
                    data: [],
                    borderColor: '#00b4d8',
                    backgroundColor: 'rgba(0, 180, 216, 0.1)',
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    y: {
                        type: 'linear',
                        position: 'left',
                        beginAtZero: true,
                        max: 100,
                        grid: { color: 'rgba(0, 180, 216, 0.08)' },
                        ticks: { color: '#00ff88', font: { size: 11 } },
                        title: { display: false }
                    },
                    y1: {
                        type: 'linear',
                        position: 'right',
                        beginAtZero: true,
                        max: 50,
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#00b4d8', font: { size: 11 } },
                        title: { display: false }
                    },
                    x: {
                        grid: { color: 'rgba(0, 180, 216, 0.08)' },
                        ticks: { color: '#5a7a9a', font: { size: 11 }, maxTicksLimit: 8 }
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
    document.addEventListener('DOMContentLoaded', function() {
        if (typeof Chart === 'undefined') {
            console.error('Chart.js not loaded - chart will not work');
        } else {
            initChart();
        }
    });
} else {
    if (typeof Chart === 'undefined') {
        console.error('Chart.js not loaded - chart will not work');
    } else {
        initChart();
    }
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/wellness/`);
    
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
    if (data.tip) tipText.textContent = data.tip;
    
    checkBreakReminder(data.wellness_score);
    updateDrowsinessMonitor(data);
    collectSessionStats(data);

    const now = Date.now();
    if (now - lastSessionEntryTime >= 2000) {
        addSessionEntry(data);
        lastSessionEntryTime = now;
    }
    
    if (chart && now - lastChartTime >= 1000) {
        lastChartTime = now;
        const time = new Date().toLocaleTimeString();
        chart.data.labels.push(time);
        chart.data.datasets[0].data.push(data.wellness_score);
        chart.data.datasets[1].data.push(data.blink_rate);
        
        if (chart.data.labels.length > 30) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
            chart.data.datasets[1].data.shift();
        }
        
        chart.update('none');
    }
}

function checkBreakReminder(score) {
    const now = Date.now();
    
    if (now < breakCooldownUntil) {
        return;
    }
    
    if (score < LOW_SCORE_THRESHOLD) {
        if (lowScoreStartTime === null) {
            lowScoreStartTime = now;
        } else if (now - lowScoreStartTime >= LOW_SCORE_DURATION_MS) {
            showBreakReminder();
            lowScoreStartTime = null;
            breakCooldownUntil = now + BREAK_COOLDOWN_MS;
        }
    } else {
        lowScoreStartTime = null;
    }
}

function showBreakReminder() {
    const message = 'Take a 20-20-20 break: look at something 20 feet away for 20 seconds.';
    
    if (Notification.permission === 'granted') {
        new Notification('Wellness Break', {
            body: message,
            icon: '/static/favicon.ico',
            tag: 'break-reminder'
        });
    } else {
        showToast(message);
    }
}

function showToast(message) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    
    container.appendChild(toast);
    
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });
    
    setTimeout(() => {
        toast.classList.remove('show');
        toast.addEventListener('transitionend', () => toast.remove());
    }, 6000);
}

function requestNotificationPermission() {
    if (Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

function addSessionEntry(data) {
    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    const exprClass = data.expression.toLowerCase();
    
    const row = document.createElement('tr');
    row.innerHTML = `
        <td>${time}</td>
        <td>${data.wellness_score}</td>
        <td>${data.blink_rate}/min</td>
        <td><span class="expr-badge ${exprClass}">${data.expression}</span></td>
    `;
    
    sessionLog.insertBefore(row, sessionLog.firstChild);
    
    if (sessionLog.children.length > 10) {
        sessionLog.removeChild(sessionLog.lastChild);
    }
}

async function startCamera() {
    console.log('Start camera clicked');
    startBtn.disabled = true;
    startBtn.textContent = 'Starting...';
    cameraStatus.textContent = 'Requesting camera access...';
    cameraStatus.className = 'camera-status';
    
    lowScoreStartTime = null;
    breakCooldownUntil = 0;
    requestNotificationPermission();
    
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
        sessionResetPending = true;
        startSessionTracking();
        cameraStatus.textContent = 'Camera active - Detecting face...';
        cameraStatus.className = 'camera-status active';
        if (fpsEl) fpsEl.textContent = '0';
        const trackStatus = document.querySelector('.tracking-status');
        if (trackStatus) trackStatus.classList.remove('idle');
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
    finishSessionReport();
    const stream = video.srcObject;
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    video.srcObject = null;
    placeholder.style.display = 'flex';
    startBtn.textContent = 'Start camera';
    isRunning = false;
    lowScoreStartTime = null;
    breakCooldownUntil = 0;
    if (ws) ws.close();

    // Reset live status so nothing stale stays on screen after stop.
    cameraStatus.textContent = 'Camera stopped';
    cameraStatus.className = 'camera-status';
    if (fpsEl) fpsEl.textContent = '0';
    const trackStatus = document.querySelector('.tracking-status');
    if (trackStatus) trackStatus.classList.add('idle');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

async function detectFace() {
    if (!isRunning) return;
    
    if (video.videoWidth === 0 || video.videoHeight === 0) {
        requestAnimationFrame(detectFace);
        return;
    }
    
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
    tempCanvas.width = 640;
    tempCanvas.height = 480;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.drawImage(video, 0, 0, 640, 480);
    const imageData = tempCanvas.toDataURL('image/jpeg', 0.6);
    
    try {
        const response = await fetch('/api/analyze/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ image: imageData, reset_session: sessionResetPending })
        });
        
        const result = await response.json();

        // Camera was stopped while this request was in flight: don't touch the UI.
        if (!isRunning) return;

        if (result.face_detected) {
            sessionResetPending = false;
        }
        
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
            }
        } else {
            cameraStatus.textContent = 'No face detected';
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

document.addEventListener('keydown', function(e) {
    if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        if (isRunning) {
            stopCamera();
        } else {
            startCamera();
        }
    }
});

/* ================================================================
   Feature 1: Smart drowsiness alert (sound + visual)
   ================================================================ */
const drowsyAlertEl = document.getElementById('drowsyAlert');
const drowsySubEl = document.getElementById('drowsyAlertSub');
const soundToggleEl = document.getElementById('soundToggle');
const soundIconEl = document.getElementById('soundIcon');

// Banner subtitle shows the real closed duration: live while the eyes are
// closed, frozen at the triggering closure after they reopen (never 0.0).
let lastClosureSeen = 0;
let alertClosure = 0;
function setDrowsySub(text) {
    if (drowsySubEl && drowsySubEl.textContent !== text) drowsySubEl.textContent = text;
}
function drowsySubForClosure(sec) {
    return sec > 0
        ? 'Eyes closed ' + sec.toFixed(1) + 's - Look away and stretch for a minute'
        : 'Take a short break - Look away and stretch for a minute';
}
// pattern-rule alerts show the closure count, never a duration
function drowsySubFor(rule, closureSec) {
    return rule === 'pattern'
        ? '3 slow eye closures in 30 s - Look away and stretch for a minute'
        : drowsySubForClosure(closureSec);
}

const SOUND_MUTED_KEY = 'wst_alert_muted';
let soundMuted = false;
try { soundMuted = localStorage.getItem(SOUND_MUTED_KEY) === '1'; } catch (e) {}

let alertActive = false;
let drowsyOnFrames = 0;
let drowsyOffFrames = 0;
let alertTimer = null;
let audioCtx = null;

function renderSoundToggle() {
    if (!soundToggleEl || !soundIconEl) return;
    soundIconEl.textContent = soundMuted ? '\u{1F507}' : '\u{1F50A}';
    soundToggleEl.classList.toggle('muted', soundMuted);
    soundToggleEl.title = soundMuted ? 'Unmute alert sound' : 'Mute alert sound';
    soundToggleEl.setAttribute('aria-label', soundToggleEl.title);
    soundToggleEl.setAttribute('aria-pressed', soundMuted ? 'true' : 'false');
}

function playAlertBeep() {
    if (soundMuted) return;
    try {
        if (!audioCtx) {
            const AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return;
            audioCtx = new AC();
        }
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const t0 = audioCtx.currentTime;
        [0, 0.26].forEach(function(offset) {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, t0 + offset);
            gain.gain.setValueAtTime(0.0001, t0 + offset);
            gain.gain.exponentialRampToValueAtTime(0.12, t0 + offset + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, t0 + offset + 0.2);
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start(t0 + offset);
            osc.stop(t0 + offset + 0.22);
        });
    } catch (e) { /* audio not available */ }
}

function showDrowsyAlert(closureSec, rule) {
    if (alertActive) return;
    alertActive = true;
    alertClosure = (rule === 'pattern') ? 0 : (closureSec || lastClosureSeen);
    if (drowsyAlertEl) {
        drowsyAlertEl.classList.add('active');
    }
    setDrowsySub(drowsySubFor(rule, alertClosure));
    if (sessionStats.active) sessionStats.drowsyEvents++;
    playAlertBeep();
    alertTimer = setInterval(playAlertBeep, 3000);
}

function hideDrowsyAlert() {
    if (!alertActive) return;
    alertActive = false;
    lastClosureSeen = 0;
    alertClosure = 0;
    if (drowsyAlertEl) drowsyAlertEl.classList.remove('active');
    if (alertTimer) {
        clearInterval(alertTimer);
        alertTimer = null;
    }
}

function updateDrowsinessMonitor(data) {
    const drowsy = !!data.drowsy && !data.calibrating;
    const closure = Number(data.eye_closure_sec) || 0;
    const rule = data.drowsy_rule || null;
    if (closure > 0) lastClosureSeen = closure;
    if (drowsy) {
        drowsyOnFrames++;
        drowsyOffFrames = 0;
        // Two consecutive drowsy readings: a single flicker never alerts.
        if (!alertActive && drowsyOnFrames >= 2) showDrowsyAlert(closure, rule);
    } else {
        drowsyOffFrames++;
        drowsyOnFrames = 0;
        // the engine only clears after 4 s of continuous open eyes, so the
        // banner hides 4 s after the eyes reopen - first cleared reading
        if (alertActive && drowsyOffFrames >= 1) hideDrowsyAlert();
    }
    if (alertActive) {
        if (rule === 'pattern') {
            setDrowsySub(drowsySubFor('pattern', 0));
        } else {
            // sustained: live duration while closed, frozen after reopen
            if (closure > alertClosure) alertClosure = closure;
            setDrowsySub(drowsySubFor('sustained', alertClosure));
        }
    }
}

if (soundToggleEl) {
    soundToggleEl.addEventListener('click', function() {
        soundMuted = !soundMuted;
        try { localStorage.setItem(SOUND_MUTED_KEY, soundMuted ? '1' : '0'); } catch (e) {}
        renderSoundToggle();
        if (!soundMuted && alertActive) playAlertBeep();
    });
}
renderSoundToggle();

/* ================================================================
   Feature 2: End-of-session AI report (real session data only)
   ================================================================ */
const sessionStats = {
    active: false,
    startedAt: 0,
    scoreSum: 0,
    scoreCount: 0,
    blinkSum: 0,
    blinkCount: 0,
    samples: [],
    drowsyEvents: 0,
    drowsySeconds: 0
};
let lastStatTick = 0;
let sessionResetPending = false;

const reportModal = document.getElementById('reportModal');

function startSessionTracking() {
    hideReportModal();
    sessionStats.active = true;
    sessionStats.startedAt = Date.now();
    sessionStats.scoreSum = 0;
    sessionStats.scoreCount = 0;
    sessionStats.blinkSum = 0;
    sessionStats.blinkCount = 0;
    sessionStats.samples = [];
    sessionStats.drowsyEvents = 0;
    sessionStats.drowsySeconds = 0;
    lastStatTick = 0;
    drowsyOnFrames = 0;
    drowsyOffFrames = 0;
    hideDrowsyAlert();
}

function stopSessionTracking() {
    sessionStats.active = false;
    sessionStats.startedAt = 0;
    sessionStats.samples = [];
    lastStatTick = 0;
}

function collectSessionStats(data) {
    if (!sessionStats.active) return;
    const now = Date.now();
    if (now - lastStatTick < 1000) return;   // one sample per second
    lastStatTick = now;
    if (data.calibrating) return;            // placeholder values are not real data


    const score = Number(data.wellness_score);
    if (!isNaN(score)) {
        sessionStats.scoreSum += score;
        sessionStats.scoreCount++;
        sessionStats.samples.push(score);
    }
    const blink = Number(data.blink_rate);
    if (!isNaN(blink)) {
        sessionStats.blinkSum += blink;
        sessionStats.blinkCount++;
    }
    // actual eyes-closed time during alert episodes (not banner visibility time)
    const closedSec = Number(data.closed_drowsy_sec);
    if (!isNaN(closedSec)) {
        sessionStats.drowsySeconds = Math.max(sessionStats.drowsySeconds, closedSec);
    }
}

function formatDuration(totalSeconds) {
    // single formatter for table, summary card, tip and compare badge:
    // <60s -> "42s"; >=60s -> "1 min 36 s" (seconds part omitted when 0)
    const sec = Math.max(0, Math.round(totalSeconds));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) return h + 'h ' + m + 'm';
    if (m > 0) return s > 0 ? m + ' min ' + s + ' s' : m + ' min';
    return s + 's';
}

function blinkRateLabel(rate) {
    if (rate < 10) return 'Low';
    if (rate > 20) return 'High';
    return 'Normal';
}

function buildRecommendation(focus, stability, blinkLabel, drowsyEvents, durationMin, durationLabel, breakMin) {
    // Priority: drowsiness alerts > low blink rate > low stability > positive.
    // "steady" is only claimed when stability >= 70; scores/thresholds unchanged.

    // 1. drowsiness alerts - wording unchanged
    if (drowsyEvents >= 1) {
        if (breakMin <= 0) {
            return drowsyEvents + ' drowsiness alert' + (drowsyEvents === 1 ? '' : 's') +
                ' during this session - a quick blink and posture check is all you need.';
        }
        if (drowsyEvents >= 2) {
            return drowsyEvents + ' drowsiness alerts during this session. Step away for ' + breakMin +
                ' minutes - a short walk and some water will reset your focus.';
        }
        return 'One drowsiness episode was detected. A ' + breakMin +
            '-minute break now will keep the rest of your session sharp.';
    }

    // 2. low blink rate - rest the eyes / blink more, even in short sessions
    if (blinkLabel === 'Low') {
        if (breakMin <= 0) {
            return 'You blinked rarely - look away from the screen for a minute and blink slowly.';
        }
        return 'Solid attention at ' + focus + '% focus, but you blinked less than usual. Rest your eyes for ' +
            breakMin + ' minutes away from the screen.';
    }

    // 3. uneven attention (stability < 50%)
    if (stability < 50) {
        if (breakMin <= 0) {
            return 'Your attention moved around a lot - try a quieter setup.';
        }
        return 'Your attention moved around a lot - try a quieter setup and take a ' +
            breakMin + '-minute break.';
    }

    // 4. low focus (only in break-length sessions)
    if (breakMin > 0 && focus < 55) {
        return 'Focus dropped to ' + focus + '% in this session. Take a ' + breakMin +
            '-minute break, stretch, then return with a single task in mind.';
    }

    // positive / general messages - "steady" only when stability >= 70
    if (focus >= 85 && stability >= 75) {
        if (breakMin > 0) {
            return 'Excellent session: ' + focus + '% focus with ' + stability +
                '% attention stability. A quick ' + breakMin + '-minute break will keep the momentum going.';
        }
        return 'Excellent session: ' + focus + '% focus with ' + stability +
            '% attention stability. Keep it up!';
    }
    if (breakMin > 0 && durationMin >= 30) {
        return 'You stayed on task for ' + durationLabel + ' straight. Take a ' + breakMin +
            '-minute break before your next block of work.';
    }
    const pace = stability >= 70 ? 'A steady ' + durationLabel : 'A ' + durationLabel;
    if (breakMin <= 0) {
        return pace + ' session at ' + focus + '% focus. Keep the rhythm going.';
    }
    return pace + ' session at ' + focus + '% focus. A short ' + breakMin +
        '-minute break will keep your attention stable next session.';
}

function computeSessionReport() {
    const durationSec = Math.max(1, Math.round((Date.now() - sessionStats.startedAt) / 1000));
    const focus = sessionStats.scoreCount
        ? Math.round(sessionStats.scoreSum / sessionStats.scoreCount) : 0;
    const samples = sessionStats.samples;
    const stability = samples.length
        ? Math.round(100 * samples.filter(function(s) { return s >= 70; }).length / samples.length) : 0;
    const avgBlink = sessionStats.blinkCount
        ? Math.round(sessionStats.blinkSum / sessionStats.blinkCount) : 0;
    const blinkLabel = blinkRateLabel(avgBlink);
    const drowsyFree = Math.max(0, Math.min(100,
        Math.round(100 * (1 - sessionStats.drowsySeconds / durationSec))));
    const drowsyEvents = sessionStats.drowsyEvents;
    // single duration basis: floor minutes for "N-minute" wording, one label
    // (formatDuration) for every display - card, tip and history all agree.
    const durationMin = Math.floor(durationSec / 60);
    const durationLabel = formatDuration(durationSec);

    // break rules: <5 min none; 5-20 min with 1-2 alerts 2-5 min;
    // >20 min or 3+ alerts 10 min.
    let breakMin;
    if (durationSec > 20 * 60 || drowsyEvents >= 3) breakMin = 10;
    else if (durationSec >= 5 * 60 && drowsyEvents >= 1) breakMin = drowsyEvents >= 2 ? 5 : 2;
    else breakMin = 0;

    return {
        timestamp: new Date().toISOString(),
        duration_seconds: durationSec,
        focus_score: focus,
        attention_stability: stability,
        blink_rate: avgBlink,
        blink_rate_label: blinkLabel,
        drowsiness_events: drowsyEvents,
        drowsy_free: drowsyFree,
        break_minutes: breakMin,
        recommendation: buildRecommendation(focus, stability, blinkLabel, drowsyEvents,
            durationMin, durationLabel, breakMin)
    };
}

const RING_CIRCUMFERENCE = 263.89;

function setRing(circleId, valueId, pct) {
    const bounded = Math.max(0, Math.min(100, pct));
    const circle = document.getElementById(circleId);
    if (circle) {
        circle.style.strokeDashoffset = String(RING_CIRCUMFERENCE * (1 - bounded / 100));
    }
    const label = document.getElementById(valueId);
    if (label) label.textContent = Math.round(bounded) + '%';
}

function showReportModal(report) {
    if (!reportModal) return;
    document.getElementById('reportDate').textContent =
        new Date(report.timestamp).toLocaleString(undefined, {
            weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
    document.getElementById('repBlink').textContent =
        report.blink_rate_label + ' (' + report.blink_rate + '/min)';
    document.getElementById('repDrowsy').textContent = String(report.drowsiness_events);
    document.getElementById('repDuration').textContent = formatDuration(report.duration_seconds);
    document.getElementById('repBreak').textContent =
        report.break_minutes > 0 ? report.break_minutes + ' min' : 'None';
    document.getElementById('repReco').textContent = report.recommendation;

    setRing('ringFocus', 'ringFocusValue', 0);
    setRing('ringStability', 'ringStabilityValue', 0);
    setRing('ringAlert', 'ringAlertValue', 0);

    reportModal.classList.add('open');
    reportModal.setAttribute('aria-hidden', 'false');

    setTimeout(function() {
        setRing('ringFocus', 'ringFocusValue', report.focus_score);
        setRing('ringStability', 'ringStabilityValue', report.attention_stability);
        setRing('ringAlert', 'ringAlertValue', report.drowsy_free);
    }, 80);
}

function hideReportModal() {
    if (!reportModal) return;
    reportModal.classList.remove('open');
    reportModal.setAttribute('aria-hidden', 'true');
}

function finishSessionReport() {
    hideDrowsyAlert();
    drowsyOnFrames = 0;
    drowsyOffFrames = 0;

    if (!sessionStats.active || sessionStats.scoreCount < 3) {
        const wasActive = sessionStats.active;
        stopSessionTracking();
        if (wasActive) showToast('Session too short to generate a report.');
        return;
    }

    const report = computeSessionReport();
    stopSessionTracking();
    showReportModal(report);
    persistSession(report);
}

if (reportModal) {
    document.getElementById('reportClose').addEventListener('click', hideReportModal);
    document.getElementById('reportCloseX').addEventListener('click', hideReportModal);
    document.getElementById('reportBackdrop').addEventListener('click', hideReportModal);
    document.getElementById('reportStartNew').addEventListener('click', function() {
        hideReportModal();
        if (!isRunning) startCamera();
    });
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') hideReportModal();
});

/* ================================================================
   Feature 3: Session history, trends & before/after comparison
   ================================================================ */
const HISTORY_FALLBACK_KEY = 'wst_session_history';
let sessionHistory = [];
let focusTrendChart = null;
let drowsyTrendChart = null;

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function(c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
}

function signed(n) {
    return (n > 0 ? '+' : '') + n;
}

function sessionLabel(session, index) {
    const d = new Date(session.timestamp);
    const date = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return '#' + (index + 1) + ' - ' + date + ', ' + time + ' - ' + formatDuration(session.duration_seconds);
}

function saveHistoryFallback() {
    try { localStorage.setItem(HISTORY_FALLBACK_KEY, JSON.stringify(sessionHistory)); } catch (e) {}
}

async function loadSessionHistory() {
    try {
        const res = await fetch('/api/sessions/');
        if (!res.ok) throw new Error('history request failed');
        const data = await res.json();
        sessionHistory = data.sessions || [];
        saveHistoryFallback();
    } catch (e) {
        try {
            sessionHistory = JSON.parse(localStorage.getItem(HISTORY_FALLBACK_KEY) || '[]');
        } catch (e2) {
            sessionHistory = [];
        }
    }
    renderHistory();
}

async function persistSession(report) {
    const payload = {
        duration_seconds: report.duration_seconds,
        focus_score: report.focus_score,
        attention_stability: report.attention_stability,
        blink_rate: report.blink_rate,
        blink_rate_label: report.blink_rate_label,
        drowsiness_events: report.drowsiness_events
    };
    try {
        const res = await fetch('/api/sessions/save/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('save failed');
        const data = await res.json();
        sessionHistory.push(data.session);
    } catch (e) {
        sessionHistory.push(Object.assign({ id: 'local-' + Date.now() }, payload, {
            timestamp: report.timestamp
        }));
        showToast('Saved locally - server history unavailable.');
    }
    saveHistoryFallback();
    renderHistory();
}

function historyChartOptions(yMax) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        elements: { line: { borderWidth: 2 } },
        scales: {
            y: {
                beginAtZero: true,
                max: yMax,
                grid: { color: 'rgba(0, 180, 216, 0.08)' },
                ticks: { color: '#5a7a9a', font: { size: 10 } }
            },
            x: {
                grid: { color: 'rgba(0, 180, 216, 0.08)' },
                ticks: { color: '#5a7a9a', font: { size: 10 }, maxTicksLimit: 8 }
            }
        },
        plugins: { legend: { display: false } }
    };
}

function initHistoryCharts() {
    if (typeof Chart === 'undefined') return;
    try {
        const focusCtx = document.getElementById('focusTrendChart');
        const drowsyCtx = document.getElementById('drowsyTrendChart');
        if (!focusCtx || !drowsyCtx) return;

        focusTrendChart = new Chart(focusCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Focus Score',
                    data: [],
                    borderColor: '#00ff88',
                    backgroundColor: 'rgba(0, 255, 136, 0.1)',
                    tension: 0,
                    fill: true,
                    pointRadius: 3,
                    pointBackgroundColor: '#00ff88',
                    yAxisID: 'y'
                }, {
                    label: 'Attention Stability',
                    data: [],
                    borderColor: '#48cae4',
                    backgroundColor: 'rgba(72, 202, 228, 0.08)',
                    tension: 0,
                    fill: true,
                    pointRadius: 3,
                    pointBackgroundColor: '#48cae4',
                    yAxisID: 'y'
                }]
            },
            options: historyChartOptions(100)
        });

        const drowsyOptions = historyChartOptions(undefined);
        drowsyOptions.scales.y.ticks.color = '#ff6b6b';
        drowsyOptions.scales.y.ticks.precision = 0;
        drowsyOptions.scales.y1 = {
            beginAtZero: true,
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: { color: '#00b4d8', font: { size: 10 } }
        };
        drowsyTrendChart = new Chart(drowsyCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Drowsiness Events',
                    data: [],
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255, 107, 107, 0.1)',
                    tension: 0,
                    fill: true,
                    pointRadius: 3,
                    pointBackgroundColor: '#ff6b6b',
                    yAxisID: 'y'
                }, {
                    label: 'Session Duration (min)',
                    data: [],
                    borderColor: '#00b4d8',
                    backgroundColor: 'rgba(0, 180, 216, 0.08)',
                    tension: 0,
                    fill: true,
                    pointRadius: 3,
                    pointBackgroundColor: '#00b4d8',
                    yAxisID: 'y1'
                }]
            },
            options: drowsyOptions
        });
    } catch (e) {
        console.error('History chart init error:', e);
    }
}

function updateHistoryCharts() {
    if (!focusTrendChart || !drowsyTrendChart) return;
    const labels = sessionHistory.map(function(s) {
        const d = new Date(s.timestamp);
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' +
            d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });

    focusTrendChart.data.labels = labels;
    focusTrendChart.data.datasets[0].data = sessionHistory.map(function(s) { return Math.round(s.focus_score); });
    focusTrendChart.data.datasets[1].data = sessionHistory.map(function(s) { return Math.round(s.attention_stability); });
    focusTrendChart.update('none');

    drowsyTrendChart.data.labels = labels;
    drowsyTrendChart.data.datasets[0].data = sessionHistory.map(function(s) { return s.drowsiness_events; });
    // one decimal minute (10s sessions show 0.2, not 0)
    drowsyTrendChart.data.datasets[1].data = sessionHistory.map(function(s) { return Math.round(s.duration_seconds / 6) / 10; });
    drowsyTrendChart.update('none');
}

function renderTrendSummary() {
    const el = document.getElementById('trendSummary');
    if (!el) return;
    const n = sessionHistory.length;
    if (n === 0) {
        el.textContent = 'Complete and stop a session to start tracking your trends.';
        return;
    }
    if (n === 1) {
        el.textContent = '1 session saved. Complete one more session to see your focus trend.';
        return;
    }
    // Trend verdict only counts when every session lasted at least 1 minute.
    if (sessionHistory.some(function(s) { return (s.duration_seconds || 0) < 60; })) {
        el.textContent = 'Sessions under 1 minute - complete longer sessions to see your focus trend.';
        return;
    }
    const first = sessionHistory[0];
    const last = sessionHistory[n - 1];
    const focusDelta = Math.round(last.focus_score - first.focus_score);
    const stabDelta = Math.round(last.attention_stability - first.attention_stability);
    const drowsyDelta = last.drowsiness_events - first.drowsiness_events;
    const cls = focusDelta > 2 ? 'trend-up' : (focusDelta < -2 ? 'trend-down' : 'trend-flat');
    const word = focusDelta > 2 ? 'improving' : (focusDelta < -2 ? 'decreasing' : 'holding steady');
    const drowsyText = drowsyDelta === 0 ? 'Drowsiness events: no change' : 'Drowsiness events ' + signed(drowsyDelta);
    el.innerHTML = 'Across <strong>' + n + '</strong> sessions your focus is <span class="' + cls + '">' +
        word + ' (' + signed(focusDelta) + ' pts, ' + Math.round(first.focus_score) + '% &rarr; ' +
        Math.round(last.focus_score) + '%)</span> &middot; Stability ' + signed(stabDelta) +
        ' pts &middot; ' + drowsyText + '.';
}

function renderHistoryTable() {
    const tbody = document.getElementById('historyTableBody');
    const empty = document.getElementById('historyEmpty');
    const wrap = document.querySelector('.history-table-wrap');
    if (!tbody || !empty || !wrap) return;

    if (!sessionHistory.length) {
        tbody.innerHTML = '';
        wrap.style.display = 'none';
        empty.style.display = 'block';
        return;
    }
    wrap.style.display = 'block';
    empty.style.display = 'none';

    const rows = sessionHistory.slice().reverse().map(function(s) {
        const d = new Date(s.timestamp);
        const date = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
        const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const drowsy = s.drowsiness_events;
        const badgeClass = drowsy >= 2 ? 'stressed' : (drowsy === 1 ? 'neutral' : 'focused');
        // blink rate is unreliable on very short sessions
        const blinkCell = (s.duration_seconds || 0) < 20
            ? '&ndash;'
            : escapeHtml(s.blink_rate_label) + ' (' + Math.round(s.blink_rate) + '/min)';
        return '<tr>' +
            '<td>' + escapeHtml(date) + ' &middot; ' + escapeHtml(time) + '</td>' +
            '<td>' + formatDuration(s.duration_seconds) + '</td>' +
            '<td>' + Math.round(s.focus_score) + '%</td>' +
            '<td>' + Math.round(s.attention_stability) + '%</td>' +
            '<td>' + blinkCell + '</td>' +
            '<td><span class="expr-badge ' + badgeClass + '">' + drowsy + '</span></td>' +
            '</tr>';
    });
    tbody.innerHTML = rows.join('');
}

const COMPARE_METRICS = [
    { key: 'focus_score', label: 'Focus Score', better: 'up',
      fmt: function(v) { return Math.round(v) + '%'; }, deltaUnit: '' },
    { key: 'attention_stability', label: 'Attention Stability', better: 'up',
      fmt: function(v) { return Math.round(v) + '%'; }, deltaUnit: '' },
    { key: 'drowsiness_events', label: 'Drowsiness Events', better: 'down',
      fmt: function(v) { return String(Math.round(v)); }, deltaUnit: '' },
    { key: 'duration_seconds', label: 'Session Duration', better: 'none',
      fmt: function(v) { return formatDuration(v); }, deltaUnit: 'm' }
];

function populateCompareSelects() {
    const selA = document.getElementById('compareA');
    const selB = document.getElementById('compareB');
    if (!selA || !selB) return;

    if (sessionHistory.length < 2) {
        const placeholder = '<option value="">Not enough sessions</option>';
        selA.innerHTML = placeholder;
        selB.innerHTML = placeholder;
        return;
    }

    const prevA = selA.value;
    const prevB = selB.value;
    const options = sessionHistory.map(function(s, i) {
        return '<option value="' + i + '">' + escapeHtml(sessionLabel(s, i)) + '</option>';
    }).join('');
    selA.innerHTML = options;
    selB.innerHTML = options;

    const defA = String(sessionHistory.length - 2);
    const defB = String(sessionHistory.length - 1);
    selA.value = (prevA !== '' && sessionHistory[Number(prevA)] !== undefined) ? prevA : defA;
    selB.value = (prevB !== '' && sessionHistory[Number(prevB)] !== undefined) ? prevB : defB;
    if (selA.value === selB.value) {
        const bIdx = Number(selB.value);
        selA.value = String(bIdx === 0 ? Math.min(1, sessionHistory.length - 1) : bIdx - 1);
    }
}

function renderComparison() {
    const grid = document.getElementById('compareGrid');
    const verdict = document.getElementById('compareVerdict');
    if (!grid || !verdict) return;

    const selA = document.getElementById('compareA');
    const selB = document.getElementById('compareB');
    const a = parseInt(selA.value, 10);
    const b = parseInt(selB.value, 10);
    const A = sessionHistory[a];
    const B = sessionHistory[b];

    if (!A || !B || a === b) {
        grid.innerHTML = '';
        verdict.textContent = sessionHistory.length >= 2
            ? 'Select two different sessions to compare.'
            : 'Save at least two sessions to compare them.';
        return;
    }

    grid.innerHTML = COMPARE_METRICS.map(function(m) {
        const va = Number(A[m.key]) || 0;
        const vb = Number(B[m.key]) || 0;
        const delta = vb - va;
        let chipClass = 'delta-neutral';
        let chipText;
        if (m.deltaUnit === 'm') {
            chipText = signed(Math.round(delta / 6) / 10) + 'm';
        } else {
            chipText = signed(Math.round(delta));
        }
        if (Math.abs(delta) >= 0.5) {
            if (m.better === 'up') chipClass = delta > 0 ? 'delta-good' : 'delta-bad';
            else if (m.better === 'down') chipClass = delta < 0 ? 'delta-good' : 'delta-bad';
        }
        return '<div class="compare-metric">' +
            '<div class="compare-metric-label">' + m.label + '</div>' +
            '<div class="compare-values">' + m.fmt(va) +
            '<span class="arrow">&rarr;</span>' + m.fmt(vb) +
            '<span class="delta-chip ' + chipClass + '">' + chipText + '</span>' +
            '</div></div>';
    }).join('');

    // Verdict wording only when both sessions lasted at least 1 minute.
    if ((A.duration_seconds || 0) < 60 || (B.duration_seconds || 0) < 60) {
        verdict.textContent = 'Sessions under 1 minute - complete longer sessions to see a trend.';
        return;
    }

    const focusDelta = Math.round(B.focus_score - A.focus_score);
    const stabDelta = Math.round(B.attention_stability - A.attention_stability);
    const drowsyDelta = B.drowsiness_events - A.drowsiness_events;
    const drowsyText = drowsyDelta === 0 ? 'drowsiness events: no change' : 'drowsiness events ' + signed(drowsyDelta);
    let text;
    if (focusDelta > 2) {
        text = 'Focus is <span class="trend-up">improving</span>: ' + Math.round(A.focus_score) + '% &rarr; ' +
            Math.round(B.focus_score) + '% (' + signed(focusDelta) + ' pts), stability ' + signed(stabDelta) +
            ' pts, ' + drowsyText + '.';
    } else if (focusDelta < -2) {
        text = 'Focus is <span class="trend-down">decreasing</span>: ' + Math.round(A.focus_score) + '% &rarr; ' +
            Math.round(B.focus_score) + '% (' + signed(focusDelta) + ' pts). Take a short break before your next session.';
    } else {
        text = 'Focus is <span class="trend-flat">holding steady</span> at around ' +
            Math.round(B.focus_score) + '% across these two sessions (stability ' + signed(stabDelta) +
            ' pts, ' + drowsyText + ').';
    }
    verdict.innerHTML = text;
}

function renderHistory() {
    renderHistoryTable();
    renderTrendSummary();
    updateHistoryCharts();
    populateCompareSelects();
    renderComparison();
}

async function clearSessionHistory() {
    if (!sessionHistory.length) {
        showToast('No session history to clear.');
        return;
    }
    if (!window.confirm('Clear all saved session history?')) return;
    try {
        await fetch('/api/sessions/clear/', { method: 'DELETE' });
    } catch (e) { /* keep local copy in sync anyway */ }
    sessionHistory = [];
    saveHistoryFallback();
    renderHistory();
    showToast('Session history cleared.');
}

function bootFeatureUI() {
    initHistoryCharts();
    const clearBtn = document.getElementById('clearHistoryBtn');
    if (clearBtn) clearBtn.addEventListener('click', clearSessionHistory);
    const selA = document.getElementById('compareA');
    const selB = document.getElementById('compareB');
    if (selA) selA.addEventListener('change', renderComparison);
    if (selB) selB.addEventListener('change', renderComparison);
    renderComparison();
    loadSessionHistory();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootFeatureUI);
} else {
    bootFeatureUI();
}
