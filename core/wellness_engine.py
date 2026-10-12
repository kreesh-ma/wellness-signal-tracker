import logging
import random
import time
from collections import deque

import numpy as np

log = logging.getLogger(__name__)


class WellnessEngine:
    # --- calibration ---
    CALIBRATION_SECONDS = 4.0   # seed phase before the first usable baseline
    MIN_CAL_SAMPLES = 15

    # --- adaptive baseline ---
    # Baseline EAR = running median over the last BASELINE_WINDOW_SECONDS of
    # frontal frames. Frames are skipped while a drowsiness alert is active
    # and whenever the eye is deep-closed (EAR < DEEP_RATIO x baseline - a
    # closure carries no open-eye information and would poison the median),
    # so thresholds track the user's real open-eye level instead of freezing
    # a single 4 s startup snapshot (an inflated one made squinting look like
    # a closure; a depressed one made natural blinks invisible). The seed
    # phase only provides the first thresholds; the window starts empty at
    # the end of calibration and takes over within BASELINE_MIN_SAMPLES.
    BASELINE_WINDOW_SECONDS = 10.0
    BASELINE_MIN_SAMPLES = 5   # ~0.5 s at 10 FPS: outruns the 1.5 s alert timer
    BASELINE_CLIP = (0.18, 0.40)  # sanity bounds against garbage landmarks

    # --- blink detection (ratios of the adaptive open-eye EAR baseline) ---
    CLOSE_RATIO = 0.75        # EAR < 0.75 x baseline = eye closing (enter threshold)
    OPEN_RATIO = 0.85         # EAR > 0.85 x baseline = eye reopened (hysteresis exit)
    DEEP_RATIO = 0.60         # deeper than this = closed eye: excluded from baseline
    MIN_BELOW_FRAMES = 1      # at ~10 FPS a natural blink is often only 1-3 frames
    MAX_BELOW_FRAMES = 5      # 1-5 frames (and <= MAX_BLINK_SECONDS) then reopen = blink
    MIN_BLINK_INTERVAL = 0.15
    MAX_BLINK_SECONDS = 0.4   # <=0.4s blink | 0.4-1.5s slow closure | >=1.5s alert

    # --- blink rate ---
    WINDOW_SECONDS = 60.0     # rolling window; count x (60 / observed seconds)
    WARMUP_SECONDS = 15.0     # don't penalise blink rate until we have enough data

    # --- face tracking (camera-shake rejection) ---
    SHAKE_WIDTH_RATIO = 0.5   # face box jumping >50% of its own width in one frame = shake
    FACE_LOST_RESET_SECONDS = 0.7  # brief detector flicker is tolerated; only a
                                   # longer loss resets the closure timer

    # --- head-pose gate (neck rolls / looking away) ---
    # Beyond these limits the eye landmarks are too distorted for a reliable
    # EAR, so drowsiness tracking resets instead of raising false alerts.
    # Normal frontal faces sit well inside both limits; blink/score thresholds
    # above are unchanged.
    POSE_MAX_YAW = 30.0       # deg, abs; head turned left/right
    POSE_MAX_PITCH = 25.0     # deg, abs; looking down/up

    # --- brow tension ---
    # Input is brow HEIGHT (lower = brows pulled down). Tension = % drop from the
    # user's neutral height, times this gain. Tune it while frowning on camera.
    BROW_GAIN = 3.0

    # --- drowsiness (built on the same EAR hysteresis as blink detection) ---
    DROWSY_CLOSED_SECONDS = 1.5      # eyes held below close_thr this long = drowsy
    DROWSY_CLEAR_SECONDS = 4.0       # banner hides 4 s after the eyes reopen
    SUSPICIOUS_CLOSURE_SECONDS = 0.4 # slow closure: 0.4-1.5 s counts toward the pattern
    PATTERN_WINDOW_SECONDS = 30.0    # window for the repeated-closure pattern
    PATTERN_MIN_CLOSURES = 3         # slow closures in that window = drowsy
    DROWSY_MIN_EVENT_GAP = 10.0      # min spacing between counted drowsiness events
    FACE_GAP_SECONDS = 5.0           # safety net only; face loss is reported explicitly

    # --- wellness tips ---
    TIP_INTERVAL_SECONDS = 60.0      # show a new tip at most once per minute
    LONG_SESSION_SECONDS = 20 * 60.0 # after 20 min, break tips are allowed at any score

    def __init__(self):
        self.blink_history = deque(maxlen=300)
        self.brow_history = deque(maxlen=300)
        self.last_tip = ""
        self.last_ear = None
        self.recalibrate()

    def recalibrate(self):
        """Call this to restart calibration (e.g. user changed seat or lighting)."""
        self.calibrated = False
        self.cal_start = None
        self.cal_ears = []
        self.cal_brows = []
        self.baseline_samples = deque()   # (t, ear) frontal open-eye frames, last 10 s
        self.ear_baseline = None
        self.brow_baseline = 0.0
        self.close_thr = self.open_thr = self.deep_thr = None
        self.track_start = None

        self.below_frames = 0
        self.min_ear = 1.0
        self.dip_start = None
        self.last_blink_time = 0.0
        self.blink_timestamps = deque()
        self.blink_count = 0
        self.blink_rate = 0
        self.warming_up = True

        # Drowsiness state (see DROWSY_* constants above).
        self.drowsy = False
        self.drowsy_rule = None        # 'sustained' or 'pattern' while drowsy
        self.drowsiness_events = 0
        self.open_since = None
        self.was_closed = False
        self.last_closure = 0.0
        self.last_event_time = 0.0
        self.closure_history = deque(maxlen=12)
        self.last_tick = None
        self.closure_blink_mark = 0   # blink_count when the current closure began
        self.prev_center = None       # last face-box center, for shake rejection
        self.last_tip_time = 0.0      # when the current tip was first shown
        self.face_lost_pending = False  # detector reported no face since last reading
        self.face_lost_since = None   # when the current face-loss streak began
        self.closed_drowsy_seconds = 0.0  # time actually eyes-closed while drowsy

    def reset_drowsiness(self):
        """Start a fresh monitoring session: drop counters and alert state."""
        self.drowsy = False
        self.drowsy_rule = None
        self.drowsiness_events = 0
        self.open_since = None
        self.was_closed = False
        self.last_closure = 0.0
        self.last_event_time = 0.0
        self.closure_history.clear()
        self.last_tick = None
        self.closure_blink_mark = 0
        self.prev_center = None
        self.face_lost_pending = False
        self.face_lost_since = None
        self.closed_drowsy_seconds = 0.0

    def note_face_lost(self, now=None):
        """Called by the view when the detector found no face in the frame.
        A flicker shorter than FACE_LOST_RESET_SECONDS does NOT reset the
        closure timer (detector confidence dips for a frame or two are common
        while the eyes are held closed); only a longer loss resets it."""
        if self.face_lost_since is None:
            self.face_lost_since = now if now is not None else time.time()
        self.face_lost_pending = True

    def _consume_face_lost(self, now):
        """Reset the half-finished closure left behind while the face was away.
        Must run BEFORE update_blink sees the next frame, otherwise a stale
        dip_start from before the face loss would fake a long closure.
        Face loss <= FACE_LOST_RESET_SECONDS is treated as a flicker and
        keeps the closure timer running."""
        if not self.face_lost_pending:
            return
        self.face_lost_pending = False
        lost_for = (now - self.face_lost_since) if self.face_lost_since is not None else 0.0
        self.face_lost_since = None
        if lost_for > self.FACE_LOST_RESET_SECONDS:
            self._reset_eye_tracking(
                now, 'face lost %.2fs > %.2fs' % (lost_for, self.FACE_LOST_RESET_SECONDS))

    def _reset_eye_tracking(self, now, reason=''):
        """Forget any half-finished closure AND the slow-closure pattern
        progress on an unreliable frame: face lost too long, face box jumped,
        or head turned/tilted beyond the pose limits (neck roll)."""
        self._break_dip()
        self.was_closed = False
        self.last_closure = 0.0
        self.closure_history.clear()
        self.open_since = now
        if reason:
            print('[eye-tracking reset] ' + reason, flush=True)

    # ------------------------------------------------------------------
    # Calibration + adaptive baseline
    # ------------------------------------------------------------------
    def _apply_baseline(self, base):
        """Clip a candidate baseline and derive the hysteresis thresholds."""
        base = float(np.clip(base, *self.BASELINE_CLIP))
        if base <= 0:
            return False
        self.ear_baseline = base
        self.close_thr = base * self.CLOSE_RATIO
        self.open_thr = base * self.OPEN_RATIO
        self.deep_thr = base * self.DEEP_RATIO
        return True

    def _prune_baseline(self, now):
        while (self.baseline_samples
               and now - self.baseline_samples[0][0] > self.BASELINE_WINDOW_SECONDS):
            self.baseline_samples.popleft()

    def _calibrate(self, ear, brow, now):
        if self.cal_start is None:
            self.cal_start = now
        self.cal_ears.append(ear)
        if brow is not None:
            self.cal_brows.append(brow)

        enough_time = now - self.cal_start >= self.CALIBRATION_SECONDS
        if enough_time and len(self.cal_ears) >= self.MIN_CAL_SAMPLES:
            # seed only: the running-median window starts empty after this, so
            # a wide/narrow calibration moment stops mattering after ~0.5 s.
            # median: blinks during calibration are brief outliers and barely
            # move it (unlike a mean, but without a percentile's upward bias)
            if self._apply_baseline(float(np.median(self.cal_ears))):
                self.brow_baseline = float(np.median(self.cal_brows)) if self.cal_brows else 0.0
                self.calibrated = True
                self.track_start = now
                log.info("Calibrated: ear_baseline=%.3f brow_baseline=%.1f close_thr=%.3f open_thr=%.3f",
                         self.ear_baseline, self.brow_baseline, self.close_thr, self.open_thr)

    def _update_baseline(self, ear, now):
        """Advance the running-median baseline with one frontal frame.
        Closed/blink frames and alert-active frames are ignored: only the
        user's open-eye level defines the baseline."""
        if self.drowsy or ear < self.DEEP_RATIO * self.ear_baseline:
            return
        self.baseline_samples.append((now, ear))
        self._prune_baseline(now)
        if len(self.baseline_samples) < self.BASELINE_MIN_SAMPLES:
            return
        if self._apply_baseline(float(np.median([e for _, e in self.baseline_samples]))):
            log.debug("baseline=%.3f close_thr=%.3f open_thr=%.3f n=%d",
                      self.ear_baseline, self.close_thr, self.open_thr,
                      len(self.baseline_samples))

    # ------------------------------------------------------------------
    # Blink detection (EAR with hysteresis, no motion / brightness)
    # ------------------------------------------------------------------
    def _break_dip(self):
        self.below_frames = 0
        self.min_ear = 1.0
        self.dip_start = None

    def update_blink(self, ear, now=None):
        now = now or time.time()

        # No face / bad landmarks: drop any half-finished blink so we never
        # count a false blink when the face comes back.
        if ear is None or ear <= 0 or not self.calibrated:
            self._break_dip()
            return

        if ear < self.close_thr:
            if self.below_frames == 0:
                self.dip_start = now
            self.below_frames += 1
            self.min_ear = min(self.min_ear, ear)

        elif ear > self.open_thr:
            if self.below_frames > 0:
                duration = now - (self.dip_start or now)
                # a blink is a short below-threshold run (1-5 frames, <=0.4 s)
                # followed by recovery; longer runs are slow closures/alerts
                in_frame_range = (self.MIN_BELOW_FRAMES
                                  <= self.below_frames <= self.MAX_BELOW_FRAMES)
                is_blink = (in_frame_range
                            and duration <= self.MAX_BLINK_SECONDS
                            and now - self.last_blink_time > self.MIN_BLINK_INTERVAL)
                if is_blink:
                    self.blink_count += 1
                    self.blink_timestamps.append(now)
                    self.last_blink_time = now
                    log.debug("blink #%d frames_below=%d dur=%.2f min_ear=%.3f",
                              self.blink_count, self.below_frames, duration, self.min_ear)
            self._break_dip()
        # between close_thr and open_thr: hold state (this is the hysteresis zone)

    def _check_continuity(self, now):
        """Safety net for gaps the view could not report (e.g. server error):
        a very long gap between readings is treated like face loss. Normal
        face loss is signalled explicitly by note_face_lost()."""
        if self.last_tick is not None and now - self.last_tick > self.FACE_GAP_SECONDS:
            self._break_dip()
            self.was_closed = False
            self.last_closure = 0.0
            self.open_since = now   # clear timer runs from the face return
        self.last_tick = now

    def _enter_drowsy(self, now, rule='', reason=''):
        self.drowsy = True
        self.drowsy_rule = rule
        if now - self.last_event_time >= self.DROWSY_MIN_EVENT_GAP:
            self.drowsiness_events += 1
            self.last_event_time = now
            log.info("Drowsiness event #%d (%s)", self.drowsiness_events, reason)

    def update_drowsiness(self, valid, ear, now):
        """Sustained-closure / repeated-closure drowsiness flag.

        'Closed' means EAR strictly below close_thr - the same definition the
        thresholds are built from. The blink hysteresis (below_frames) still
        runs blink classification, but it can never hold the alert timer
        hostage: if a threshold mismatch parks the EAR in the hysteresis band
        (0.75-0.85 x baseline), no closure is running and no alert can fire;
        the adaptive baseline re-absorbs the mismatch within ~0.5 s anyway.
        Returns (drowsy, seconds_eyes_currently_closed)."""
        closed = bool(valid and ear is not None and self.close_thr
                      and ear < self.close_thr)
        closure = (now - self.dip_start) if (closed and self.dip_start) else 0.0

        if closed:
            if not self.was_closed:
                self.closure_blink_mark = self.blink_count
            # a real closure (> MAX_BLINK_SECONDS) interrupts the ~4 s clear
            # window; a normal blink does NOT restart it, so the alert hides
            # ~4 s after the eyes reopen even if the user keeps blinking.
            if closure > self.MAX_BLINK_SECONDS:
                self.open_since = None
            if not self.drowsy and closure >= self.DROWSY_CLOSED_SECONDS:
                self._enter_drowsy(now, 'sustained',
                                   'sustained closure %.2fs >= %.2fs'
                                   % (closure, self.DROWSY_CLOSED_SECONDS))
            self.was_closed = True
            self.last_closure = closure
            return self.drowsy, closure

        # Eyes open (or face lost): a closure may have just ended.
        if not valid:
            # Face lost mid-closure - forget the half-finished closure, never
            # count it as a suspicious one.
            self.was_closed = False
            self.last_closure = 0.0
            self.open_since = now
            return self.drowsy, 0.0

        if self.was_closed:
            # Slow closures are the middle band: too long to be a blink
            # (<= MAX_BLINK_SECONDS) and shorter than the sustained alert
            # (>= DROWSY_CLOSED_SECONDS). Only those count toward the pattern.
            was_blink = self.blink_count > self.closure_blink_mark
            if (not was_blink
                    and self.SUSPICIOUS_CLOSURE_SECONDS <= self.last_closure
                    < self.DROWSY_CLOSED_SECONDS):
                self.closure_history.append(now)
                recent = [t for t in self.closure_history
                          if now - t <= self.PATTERN_WINDOW_SECONDS]
                if len(recent) >= self.PATTERN_MIN_CLOSURES:
                    self._enter_drowsy(
                        now, 'pattern',
                        'pattern: %d slow closures (%.1f-%.0fs) in %.0fs, last=%.2fs'
                        % (len(recent), self.SUSPICIOUS_CLOSURE_SECONDS,
                           self.DROWSY_CLOSED_SECONDS, self.PATTERN_WINDOW_SECONDS,
                           self.last_closure))
            self.last_closure = 0.0
        self.was_closed = False

        if self.open_since is None:
            self.open_since = now
        elif self.drowsy and now - self.open_since >= self.DROWSY_CLEAR_SECONDS:
            self.drowsy = False
            self.drowsy_rule = None
        return self.drowsy, 0.0

    def _update_rate(self, now):
        while self.blink_timestamps and now - self.blink_timestamps[0] > self.WINDOW_SECONDS:
            self.blink_timestamps.popleft()

        elapsed = now - self.track_start
        self.warming_up = elapsed < self.WARMUP_SECONDS

        # Blinks in the last 60 s IS the per-minute rate once the session is a
        # minute old. Younger than that, scale by the time actually observed
        # (min(60, elapsed)) so the first seconds show a running rate instead
        # of counting against an empty window.
        window = min(self.WINDOW_SECONDS, max(elapsed, 1.0))
        self.blink_rate = int(round(len(self.blink_timestamps) / window * 60))
        self.blink_history.append(self.blink_rate)

    # ------------------------------------------------------------------
    # Expression + score
    # ------------------------------------------------------------------
    def _ear_ratio(self, ear):
        if not ear or not self.ear_baseline:
            return 1.0
        return ear / self.ear_baseline

    def classify_expression(self, brow_tension, ear):
        ratio = self._ear_ratio(ear)
        if brow_tension > 25 and ratio < 0.85:
            return 'stressed'
        elif brow_tension > 12:
            return 'focused'
        return 'neutral'

    def calculate_wellness_score(self, blink_rate, brow_tension, expression, ear):
        score = 100

        if not self.warming_up:
            if blink_rate > 25:
                score -= 25
            elif blink_rate > 20:
                score -= 15
            elif blink_rate < 8:
                score -= 20      # barely blinking = screen staring (previously 0 got no penalty)
            elif blink_rate < 10:
                score -= 15
            elif blink_rate < 12:
                score -= 5

        score -= brow_tension * 0.4

        if expression == 'stressed':
            score -= 20
        elif expression == 'focused':
            score -= 8

        if self._ear_ratio(ear) < 0.85:   # squinting / heavy eyelids
            score -= 5

        return max(0, min(100, round(score)))

    def get_wellness_tip(self, score, expression, brow_tension):
        """Pick a tip that matches the current state. A tip stays on screen for at
        least TIP_INTERVAL_SECONDS. Break tips only appear after a 20 min
        session or 3+ counted drowsiness events; positive tips only when the
        score is high."""
        now = time.time()
        if self.last_tip and now - self.last_tip_time < self.TIP_INTERVAL_SECONDS:
            return self.last_tip

        long_session = (self.track_start is not None
                        and now - self.track_start >= self.LONG_SESSION_SECONDS)
        break_allowed = long_session or self.drowsiness_events >= 3

        break_tips = [
            "Try the 20-20-20 rule: Look 20ft away for 20 sec.",
            "You've been at it a while. Take a short walk.",
            "Rest your eyes for a minute. Look away from the screen.",
            "Splash some cold water on your face.",
        ]
        recovery_tips = [
            "Take a deep breath. Roll your shoulders back.",
            "Stand up and stretch for 30 seconds.",
            "Close your eyes and relax your jaw.",
            "Unclench your teeth and relax your forehead.",
        ]
        maintenance_tips = [
            "Good posture check - sit up straight!",
            "Hydration check! Drink some water.",
            "Keep blinking! Your eyes are doing great.",
            "Roll your neck slowly in circles.",
        ]
        positive_tips = [
            "You're doing great! Keep the momentum going.",
            "Feeling good? Keep it up!",
            "Great focus - your eyes look relaxed.",
        ]

        if score < 50:
            pool = list(recovery_tips)
            if break_allowed:
                pool += break_tips
        elif score < 70:
            pool = list(maintenance_tips)
            if break_allowed:
                pool += break_tips
        elif score < 85:
            pool = list(maintenance_tips)
            if break_allowed:
                pool += break_tips
        else:
            pool = positive_tips

        new_tip = random.choice(pool)
        if new_tip == self.last_tip and len(pool) > 1:
            new_tip = random.choice(pool)
        self.last_tip = new_tip
        self.last_tip_time = now
        return new_tip

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def process_reading(self, ear, brow_tension, eye_region=None, face_rect=None,
                        head_pose=None):
        """brow_tension here is the raw brow height from FaceAnalyzer (lower = brows down).
        eye_region is accepted for compatibility but no longer used.
        face_rect (left/top/right/bottom) is used to reject camera-shake frames:
        a face box that jumps between frames is not a reliable EAR reading.
        head_pose {'yaw', 'pitch'} in degrees: a turned/tilted head (neck roll,
        looking away) distorts the eye landmarks and can fake a long closure,
        so those frames are skipped and the closure timers are reset."""
        now = time.time()
        valid = ear is not None and ear > 0

        # head-pose gate: yaw/pitch beyond the limits = unreliable EAR
        pose_bad = False
        yaw_deg = pitch_deg = 0.0
        if head_pose is not None:
            try:
                yaw_deg = abs(float(head_pose.get('yaw') or 0.0))
                pitch_deg = abs(float(head_pose.get('pitch') or 0.0))
                pose_bad = (yaw_deg > self.POSE_MAX_YAW
                            or pitch_deg > self.POSE_MAX_PITCH)
            except (AttributeError, TypeError, ValueError):
                pose_bad = False
        if pose_bad:
            valid = False

        # camera-shake gate: ignore frames where the face box moved a lot
        shaky = False
        jump_dist = jump_fw = 0.0
        if face_rect is not None:
            try:
                cx = (face_rect['left'] + face_rect['right']) / 2.0
                cy = (face_rect['top'] + face_rect['bottom']) / 2.0
                fw = max(1.0, face_rect['right'] - face_rect['left'])
            except (TypeError, KeyError, ValueError):
                cx = cy = None
            if cx is not None:
                if self.prev_center is not None:
                    dist = ((cx - self.prev_center[0]) ** 2
                            + (cy - self.prev_center[1]) ** 2) ** 0.5
                    if dist > fw * self.SHAKE_WIDTH_RATIO:
                        shaky = True
                        jump_dist, jump_fw = dist, fw
                        log.debug("shake_skip dist=%.0f face_w=%.0f", dist, fw)
                self.prev_center = (cx, cy)
        if shaky:
            valid = False

        # explicit face-loss reset (detector reported no face since last reading)
        prev_tick = self.last_tick
        self._consume_face_lost(now)

        # unreliable frames (turned head, box jump) forget any half-finished
        # closure and the slow-closure pattern progress - they can never
        # raise (or extend) a drowsiness alert
        if pose_bad:
            self._reset_eye_tracking(
                now, 'head pose yaw=%.1f pitch=%.1f (limits %.0f/%.0f)'
                % (yaw_deg, pitch_deg, self.POSE_MAX_YAW, self.POSE_MAX_PITCH))
        if shaky:
            self._reset_eye_tracking(
                now, 'face box jump %.0fpx vs face width %.0fpx'
                % (jump_dist, jump_fw))

        if valid:
            self.last_ear = ear
        brow = None if brow_tension is None else float(brow_tension)
        self._check_continuity(now)

        if not self.calibrated:
            if valid:
                self._calibrate(ear, brow, now)
            return {
                'blink_rate': 0,
                'brow_tension': 0,
                'expression': 'neutral',
                'wellness_score': 100,
                'tip': "Calibrating - look at the screen naturally for a few seconds.",
                'calibrating': True,
                'drowsy': False,
                'drowsy_rule': None,
                'eye_closure_sec': 0.0,
                'closed_drowsy_sec': round(self.closed_drowsy_seconds, 2),
            }

        self.update_blink(ear if valid else None, now)
        if valid:
            self._update_baseline(ear, now)
        self._update_rate(now)
        drowsy, eye_closure_sec = self.update_drowsiness(valid, ear if valid else None, now)
        ear_now = ear if valid else self.last_ear

        # accumulate time the eyes were ACTUALLY closed while drowsy (alert
        # episodes) - used for the drowsiness-free %, not banner visibility
        if self.drowsy and eye_closure_sec > 0 and prev_tick is not None:
            self.closed_drowsy_seconds += min(now - prev_tick, 0.5)

        # brow tension = how far brows have dropped below this user's neutral height
        if brow is not None and self.brow_baseline > 0:
            drop_pct = max(0.0, self.brow_baseline - brow) / self.brow_baseline * 100.0
            self.brow_history.append(min(100.0, drop_pct * self.BROW_GAIN))
        avg_brow = (sum(self.brow_history) / len(self.brow_history)) if self.brow_history else 0.0

        expression = self.classify_expression(avg_brow, ear_now)
        score = self.calculate_wellness_score(self.blink_rate, avg_brow, expression, ear_now)
        tip = self.get_wellness_tip(score, expression, avg_brow)

        log.debug("ear=%s thr=%.3f below=%d blinks=%d rate=%d brow=%.1f",
                  ear, self.close_thr, self.below_frames, self.blink_count,
                  self.blink_rate, avg_brow)

        return {
            'blink_rate': self.blink_rate,
            'brow_tension': round(avg_brow, 1),
            'expression': expression,
            'wellness_score': score,
            'tip': tip,
            'calibrating': False,
            'drowsy': drowsy,
            'drowsy_rule': self.drowsy_rule if drowsy else None,
            'eye_closure_sec': round(eye_closure_sec, 2),
            'closed_drowsy_sec': round(self.closed_drowsy_seconds, 2),
        }
