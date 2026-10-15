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
    # Only near-frontal frames update the baseline: a downward-tilted head
    # foreshortens EAR, and feeding that to the running median drags the
    # baseline (and the adaptive blink line) down until real blinks stop
    # crossing it (observed live: blink rate stuck at 0/min while looking
    # slightly down). 8 deg keeps normal webcam head bob in and slouch out.
    BASELINE_MAX_PITCH = 8.0    # deg past neutral pitch that still updates baseline

    # --- blink detection (EAR runs, classified by duration) ---
    # Blink runs use a line that tracks the user's own open-eye EAR:
    # blink_thr = BLINK_RATIO x baseline (baseline = running median of
    # open-eye frames). Real webcam blinks are brief 1-2 frame dips that may
    # only reach 0.63-0.80 x baseline (low camera geometry flattens the
    # closure), so the old 0.60 deep line missed them; open-eye noise sits
    # >= 0.83 x baseline on real cameras, so 0.75 cleanly separates the two.
    # The baseline itself is adaptive, so this line adapts per user.
    # A run ends at the first valid frame back at/above blink_thr and is then
    # classified by duration (and depth for the pattern rule):
    #   <= MAX_BLINK_SECONDS  -> blink
    #   0.4 s .. 1.5 s, min < deep_thr -> slow closure (feeds pattern rule)
    #   0.4 s .. 1.5 s, min >= deep_thr -> squint/noise, ignored
    #   >= 1.5 s              -> sustained (already alerted mid-run if deep)
    # Brief invalid frames (pose flicker, shake, dropped landmarks) HOLD the
    # run for up to INVALID_HOLD_SECONDS instead of destroying it.
    DEEP_RATIO = 0.60         # drowsiness closure line: EAR < 0.60 x baseline
    BLINK_RATIO = 0.75        # blink line: EAR < 0.75 x baseline (adaptive via baseline)
    CLOSE_RATIO = 0.75        # informational only (legacy display / debug)
    OPEN_RATIO = 0.85         # informational only (legacy display / debug)
    MAX_BLINK_SECONDS = 0.4   # <=0.4s run = blink; longer = slow/sustained
    MIN_BLINK_INTERVAL = 0.15
    CLOSE_END_CONFIRM = 2     # consecutive open frames that confirm a run ended
                              # (debounce: kills 1-frame EAR flicker splits that
                              # made one blink count twice at webcam fps)
    INVALID_HOLD_SECONDS = 0.3  # tolerate short invalid gaps inside a run

    # --- blink rate ---
    WINDOW_SECONDS = 60.0     # rolling window; count x (60 / observed seconds)
    WARMUP_SECONDS = 15.0     # don't penalise blink rate until we have enough data

    # --- face tracking (camera-shake rejection) ---
    SHAKE_WIDTH_RATIO = 0.5   # face box jumping >50% of its own width in one frame = shake
    FACE_LOST_RESET_SECONDS = 0.7  # brief detector flicker is tolerated; only a
                                   # longer loss resets the closure timer

    # --- head-pose gate (neck rolls / looking away) ---
    # Gate is RELATIVE to the user's calibrated neutral pose (median pitch /
    # yaw captured during calibration), not absolute: a webcam mounted below
    # face level puts neutral pitch at 26-30 deg, and an absolute 25 deg
    # limit gated 73% of frames in a live test, killing every blink. The
    # limits themselves are unchanged - looking down at a keyboard is still
    # +30-40 deg past neutral and still gated (sim S3 passes). During
    # calibration, before neutral is known, the absolute gate applies.
    POSE_MAX_YAW = 30.0       # deg, relative to neutral; head turned L/R
    POSE_MAX_PITCH = 25.0     # deg, relative to neutral; looking down/up
    # Sustained-closure alerts additionally require the head to be nearly
    # neutral in pitch: a glance down at the keyboard foreshortens the eyes
    # for seconds without being drowsy. Blink counting is NOT restricted by
    # this (blinks happen at any small head tilt).
    POSE_SUSTAINED_MAX_PITCH = 12.0

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
    # Posture tip: head pitched down (slouch) or turned too far vs neutral.
    # The raw per-frame delta flickers around one threshold and made the tip
    # flip-flop between "Good posture" and "Posture check" within seconds, so
    # the signal is EMA-smoothed and gated with HYSTERESIS (a wider enter band
    # than exit band) and the tip is held for a minimum time.
    POSTURE_TIP_PITCH = 10.0         # deg past neutral pitch = looking down / slouching
    POSTURE_TIP_YAW = 15.0           # deg past neutral yaw = head turned L/R
    POSTURE_SMOOTH_ALPHA = 0.25      # EMA weight for new pose samples (lower = smoother)
    POSTURE_ENTER_PITCH = 12.0       # enter "slouch" only clearly past neutral
    POSTURE_EXIT_PITCH = 7.0         # leave "slouch" only clearly back upright
    POSTURE_ENTER_YAW = 18.0
    POSTURE_EXIT_YAW = 12.0
    POSTURE_TIP_HOLD_SECONDS = 8.0   # keep a posture tip up at least this long

    # --- head-pose compensation for EAR and brow tension ---
    # Looking down foreshortens the eye aperture in dlib's landmark geometry
    # even when the eye is OPEN (~0.001-0.0035 EAR/deg on real traces), which
    # used to fake a sub-threshold EAR (false "Eyes closed" / drowsy) and to
    # hide real blinks (0/min). We add the drop back before thresholding.
    EAR_PITCH_SLOPE = 0.002          # EAR lost per deg of downward pitch
    EAR_PITCH_COMP_MAX = 30          # deg; beyond this, full compensation
    # Brow landmarks jitter when the head moves / tilts, spiking "tension"
    # (observed 2 -> 47 on a head move) and faking Focused/Stressed. Brow
    # tension is therefore only sampled on stable, near-neutral frames.
    POSE_TENSION_PITCH = 12.0        # deg past neutral pitch = too tilted to trust brows
    POSE_TENSION_YAW = 15.0          # deg past neutral yaw = head turned to trust brows

    def __init__(self):
        self.blink_history = deque(maxlen=300)
        self.brow_history = deque(maxlen=300)
        self.last_tip = ""
        self.last_ear = None
        self.last_pitch_delta = None  # head pose vs neutral, for the posture tip
        self.last_yaw_delta = None
        self.recalibrate()

    def recalibrate(self):
        """Call this to restart calibration (e.g. user changed seat or lighting)."""
        self.calibrated = False
        self.cal_start = None
        self.cal_ears = []
        self.cal_brows = []
        self.cal_pitches = []    # abs pitch of every landmark frame in cal
        self.cal_yaws = []
        self.neutral_pitch = None  # median cal pitch = the user's own "straight ahead"
        self.neutral_yaw = None
        self.baseline_samples = deque()   # (t, ear) frontal open-eye frames, last 10 s
        self.ear_baseline = None
        self.brow_baseline = 0.0
        self.blink_thr = None     # adaptive closure line (see BLINK_RATIO)
        self.close_thr = self.open_thr = self.deep_thr = None
        self.track_start = None

        self.close_active = False     # inside a blink-line run
        self.close_start = None       # when the current run began
        self.close_frames = 0         # valid frames in the current run
        self.close_min_ear = 1.0
        self.open_frames = 0          # consecutive open-eye frames seen (debounce)
        self.close_end_t = None       # first open frame's t = the run's true end
        self.deep_active = False       # inside a deep (< deep_thr) span
        self.deep_start = None         # when the current deep span began
        self.last_valid_t = None      # last valid (usable) EAR frame
        self.last_blink_time = 0.0
        self.blink_timestamps = deque()
        self.blink_count = 0
        self.blink_rate = 0
        self.blink_rate_reliable = False
        self.warming_up = True

        # Drowsiness state (see DROWSY_* constants above).
        self.drowsy = False
        self.drowsy_rule = None        # 'sustained' or 'pattern' while drowsy
        self.drowsiness_events = 0
        self.open_since = None
        self.last_closure = 0.0
        self.last_event_time = 0.0
        self.closure_history = deque(maxlen=12)
        self.last_tick = None
        self.prev_center = None       # last face-box center, for shake rejection
        self.last_tip_time = 0.0      # when the current tip was first shown
        self.face_lost_pending = False  # detector reported no face since last reading
        self.face_lost_since = None   # when the current face-loss streak began
        self.closed_drowsy_seconds = 0.0  # time actually eyes-closed while drowsy
        # Posture-tip smoothing + hysteresis state (see POSTURE_* constants).
        self.smooth_pitch_delta = None  # EMA of head pitch vs neutral
        self.smooth_yaw_delta = None    # EMA of head yaw vs neutral
        self.posture_slouching = False  # hysteretic slouch flag for the tip

    def reset_drowsiness(self):
        """Start a fresh monitoring session: drop counters and alert state."""
        self.drowsy = False
        self.drowsy_rule = None
        self.drowsiness_events = 0
        self.open_since = None
        self.last_closure = 0.0
        self.last_event_time = 0.0
        self.closure_history.clear()
        self.last_tick = None
        self.close_active = False
        self.close_start = None
        self.close_frames = 0
        self.open_frames = 0
        self.close_end_t = None
        self.deep_active = False
        self.deep_start = None
        self.last_valid_t = None
        self.prev_center = None
        self.face_lost_pending = False
        self.face_lost_since = None
        self.closed_drowsy_seconds = 0.0
        # Blink-rate session state. Without this a restarted camera reuses the
        # SAME cached engine (keyed by Django session_key) and the new session
        # started from the PREVIOUS session's rate/timestamps instead of 0.
        # Reset the counters and restart the warmup window so the rate rebuilds
        # from 0; calibration (baseline / neutral pose) is kept so the user is
        # not forced to re-calibrate on every camera start.
        self.blink_count = 0
        self.blink_rate = 0
        self.blink_timestamps.clear()
        self.last_blink_time = 0.0
        self.track_start = time.time()   # new session's duration/warmup starts now
        self.warming_up = True
        self.blink_rate_reliable = False

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
        Must run BEFORE update_closures sees the next frame, otherwise a stale
        close_start from before the face loss would fake a long closure.
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
        progress: the face was gone too long for the reading to be trusted."""
        self._forget_closure()
        self._forget_deep()
        self.last_closure = 0.0
        self.closure_history.clear()
        self.open_since = now
        if reason:
            print('[eye-tracking reset] ' + reason, flush=True)

    # ------------------------------------------------------------------
    # Calibration + adaptive baseline
    # ------------------------------------------------------------------
    def _apply_baseline(self, base):
        """Clip a candidate baseline and derive the thresholds (adaptive
        blink line + deep/close/open ratios of baseline)."""
        base = float(np.clip(base, *self.BASELINE_CLIP))
        if base <= 0:
            return False
        self.ear_baseline = base
        self.close_thr = base * self.CLOSE_RATIO
        self.open_thr = base * self.OPEN_RATIO
        self.deep_thr = base * self.DEEP_RATIO
        self.blink_thr = self._compute_blink_thr(base)
        return True

    def _compute_blink_thr(self, base):
        """Blink line: a fixed fraction of the user's own open-eye baseline.
        The baseline is already an adaptive running median, so this tracks
        each user without the lag/over-count of a per-sample sigma estimate."""
        return base * self.BLINK_RATIO

    def _prune_baseline(self, now):
        while (self.baseline_samples
               and now - self.baseline_samples[0][0] > self.BASELINE_WINDOW_SECONDS):
            self.baseline_samples.popleft()

    def _calibrate(self, ear, brow, now, pitch=None, yaw=None):
        if self.cal_start is None:
            self.cal_start = now
        self.cal_ears.append(ear)
        if brow is not None:
            self.cal_brows.append(brow)
        if pitch is not None:
            self.cal_pitches.append(float(pitch))
        if yaw is not None:
            self.cal_yaws.append(float(yaw))

        enough_time = now - self.cal_start >= self.CALIBRATION_SECONDS
        if enough_time and len(self.cal_ears) >= self.MIN_CAL_SAMPLES:
            # seed only: the running-median window starts empty after this, so
            # a wide/narrow calibration moment stops mattering after ~0.5 s.
            # median: blinks during calibration are brief outliers and barely
            # move it (unlike a mean, but without a percentile's upward bias)
            if self._apply_baseline(float(np.median(self.cal_ears))):
                self.brow_baseline = float(np.median(self.cal_brows)) if self.cal_brows else 0.0
                # the user's own neutral pose: median pitch/yaw seen in cal.
                # The relative gate is measured against this, so a webcam
                # below face level (neutral pitch ~27 deg) no longer gates
                # 73% of frames the way an absolute 25 deg limit did.
                self.neutral_pitch = (float(np.median(self.cal_pitches))
                                      if self.cal_pitches else 0.0)
                self.neutral_yaw = (float(np.median(self.cal_yaws))
                                    if self.cal_yaws else 0.0)
                self.calibrated = True
                self.track_start = now
                log.info("Calibrated: ear_baseline=%.3f brow_baseline=%.1f "
                         "blink_thr=%.3f deep_thr=%.3f neutral_pitch=%.1f neutral_yaw=%.1f",
                         self.ear_baseline, self.brow_baseline, self.blink_thr,
                         self.deep_thr, self.neutral_pitch, self.neutral_yaw)

    def _update_baseline(self, ear, now):
        """Advance the running-median baseline with one frontal frame.
        Closed/blink frames, alert-active frames, and downward-tilted frames
        are ignored: only the user's near-frontal open-eye level defines the
        baseline, so a slouch cannot drag the blink line down and hide blinks."""
        if self.drowsy or ear < self.BLINK_RATIO * self.ear_baseline:
            return
        pd = self.last_pitch_delta
        if pd is not None and pd > self.BASELINE_MAX_PITCH:
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
    # Blink detection (deep-closure runs, duration-classified)
    # ------------------------------------------------------------------
    # Blink detection (dual threshold: adaptive blink line + deep line)
    # ------------------------------------------------------------------
    def _forget_closure(self):
        self.close_active = False
        self.close_start = None
        self.close_frames = 0
        self.close_min_ear = 1.0
        self.open_frames = 0
        self.close_end_t = None

    def _forget_deep(self):
        self.deep_active = False
        self.deep_start = None

    def _compensate_ear(self, ear, pitch_delta):
        """Lift EAR back toward its neutral-pitch value when the head is tilted
        down. Downward pitch foreshortens the eye aperture on real webcams
        (~0.001-0.0035 EAR/deg) even with the eye open, so a threshold tuned
        at neutral falsely reads "closed" when looking down. Returns the raw
        EAR when there is nothing to compensate (upright head / no pose)."""
        if ear is None or pitch_delta is None or pitch_delta <= 0:
            return ear
        deg = min(float(pitch_delta), self.EAR_PITCH_COMP_MAX)
        return min(0.6, ear + self.EAR_PITCH_SLOPE * deg)

    def update_closures(self, ear, now=None, pitch_delta=None):
        """Closure state machine built on ONE robust run (plus informational
        deep-span tracking).

        The BLINK run (ear < blink_thr = 0.75 x baseline) is the primary
        "eyes closed" signal. blink_thr sits ABOVE the closed-eye EAR plateau
        even when dlib fails to collapse the eyelid points on a full closure
        (a low camera makes a real 2-3 s closure plateau around 0.6 x baseline
        instead of ~0.03), so the run holds cleanly through the WHOLE closure
        until the eye truly reopens. deep_thr (0.60 x baseline) is used only
        as a DEPTH GUARD - did the run ever reach deep depth? - so a shallow
        lingering squint (dips below blink_thr but never near deep_thr) never
        raises a sustained alert. (Driving the alert off a "below deep_thr"
        run instead made it START late - EAR only briefly touches deep_thr on
        a real low-camera closure - so it never held DROWSY_CLOSED_SECONDS and
        real 2-3 s closures were missed.)

        Classification of a BLINK run by duration (and depth):
          <= MAX_BLINK_SECONDS                    -> blink
          0.4-1.5 s and min < deep_thr           -> slow closure (feeds pattern)
          0.4-1.5 s and min >= deep_thr          -> squint/noise, ignored
          >= 1.5 s and min < deep_thr            -> sustained (alerted mid-run)
        Invalid frames HOLD the run for up to INVALID_HOLD_SECONDS.
        pitch_delta (deg vs neutral) gates ONLY the sustained alert.
        Returns (drowsy, seconds_eyes_currently_closed_beyond_a_blink)."""
        now = now or time.time()
        valid = bool(ear is not None and ear > 0 and self.calibrated
                     and self.blink_thr and self.deep_thr)

        if not valid:
            if (self.last_valid_t is not None
                    and now - self.last_valid_t > self.INVALID_HOLD_SECONDS):
                self._forget_closure()
                self._forget_deep()
            return self.drowsy, 0.0

        # a gap between usable frames longer than the hold window means we
        # cannot classify the run reliably - drop it instead of guessing
        if (self.last_valid_t is not None
                and now - self.last_valid_t > self.INVALID_HOLD_SECONDS):
            self._forget_closure()
            self._forget_deep()
        self.last_valid_t = now

        # Downward-pitch EAR foreshortening is undone ONLY for the open/closed
        # boundary (blink line) so an OPEN eye looking down stays "open" and no
        # false closure run starts. The depth guard keeps RAW EAR, so a genuine
        # closure (which dips far below deep_thr even at a tilt) still registers
        # as deep. Compensating depth too would lift a real closure across the
        # deep line and suppress the drowsy alert.
        ear_c = self._compensate_ear(ear, pitch_delta)

        # ---- DEEP span (informational state only) ----
        # Tracks ear < deep_thr spans for reset/compat. It does NOT drive the
        # alert, banner timer or clear window - those come from the blink run
        # below, because the deep span STARTS too late on a real low-camera
        # closure to hold DROWSY_CLOSED_SECONDS reliably.
        if ear < self.deep_thr or (self.deep_active and ear < self.blink_thr):
            if not self.deep_active:
                self.deep_active = True
                self.deep_start = now
        else:
            self._forget_deep()

        # ---- BLINK run (counting + sustained alert + banner timer) ----
        # A run ends only after CLOSE_END_CONFIRM CONSECUTIVE open-eye frames
        # (debounce). dlib EAR is noisy at webcam fps: a single mid-blink frame
        # can flicker above blink_thr, which used to SPLIT one physical blink
        # into two short runs - both counted -> ~2x over-count (observed live:
        # 10 real blinks reported as ~19). The run's true end is the FIRST
        # open frame, so duration classification is unchanged by the debounce.
        eye_closure_sec = 0.0
        if ear_c < self.blink_thr:
            if not self.close_active:
                self.close_active = True
                self.close_start = now
                self.close_frames = 0
                self.close_min_ear = 1.0
            self.close_frames += 1
            self.open_frames = 0        # closed again: cancel any pending end
            self.close_end_t = None
            self.close_min_ear = min(self.close_min_ear, ear)
            close_dur = now - self.close_start
            deep_enough = self.close_min_ear < self.deep_thr
            if deep_enough:
                self.last_closure = close_dur
                # banner timer counts the FULL closure (not just post-alert)
                eye_closure_sec = close_dur
                # a real closure (> MAX_BLINK_SECONDS) interrupts the ~4 s
                # clear window; a normal blink does NOT restart it, so the
                # alert hides ~4 s after the eyes reopen even if blinking.
                if close_dur > self.MAX_BLINK_SECONDS:
                    self.open_since = None
                # sustained drowsiness: eyes held closed long enough AND deep
                # enough, head near neutral.
                near_neutral = (pitch_delta is None
                                or abs(pitch_delta) <= self.POSE_SUSTAINED_MAX_PITCH)
                if (near_neutral and not self.drowsy
                        and close_dur >= self.DROWSY_CLOSED_SECONDS):
                    self._enter_drowsy(
                        now, 'sustained',
                        'sustained closure %.2fs >= %.2fs (min_ear=%.3f vs '
                        'deep=%.3f, pitch_delta=%s)'
                        % (close_dur, self.DROWSY_CLOSED_SECONDS,
                           self.close_min_ear, self.deep_thr, pitch_delta))
        elif self.close_active:
            # open-eye frame while a run is pending: debounce it. The run only
            # ENDS (and is classified) once CLOSE_END_CONFIRM consecutive open
            # frames confirm the eye really reopened.
            if self.close_end_t is None:
                self.close_end_t = now
            self.open_frames += 1
            if self.open_frames < self.CLOSE_END_CONFIRM:
                # not confirmed yet - keep the run alive, no classification
                if self.close_min_ear < self.deep_thr:
                    self.last_closure = self.close_end_t - self.close_start
            else:
                run_end = self.close_end_t          # true end = first open frame
                run_dur = run_end - self.close_start
                run_min = self.close_min_ear
                self._forget_closure()
                self.last_closure = 0.0
                if run_dur <= self.MAX_BLINK_SECONDS:
                    if run_end - self.last_blink_time > self.MIN_BLINK_INTERVAL:
                        self.blink_count += 1
                        self.blink_timestamps.append(run_end)
                        self.last_blink_time = run_end
                        log.debug("blink #%d frames=%d dur=%.2f min_ear=%.3f",
                                  self.blink_count, self.close_frames, run_dur, run_min)
                elif run_dur < self.DROWSY_CLOSED_SECONDS and run_min < self.deep_thr:
                    # slow DEEP closure feeds the pattern rule; a shallow squint
                    # (min >= deep_thr) that lingered below the sensitive blink
                    # line is just a squint - never drowsiness.
                    self.closure_history.append(run_end)
                    recent = [t for t in self.closure_history
                              if run_end - t <= self.PATTERN_WINDOW_SECONDS]
                    if len(recent) >= self.PATTERN_MIN_CLOSURES:
                        self._enter_drowsy(
                            run_end, 'pattern',
                            'pattern: %d slow closures (%.1f-%.0fs) in %.0fs, last=%.2fs'
                            % (len(recent), self.SUSPICIOUS_CLOSURE_SECONDS,
                               self.DROWSY_CLOSED_SECONDS, self.PATTERN_WINDOW_SECONDS,
                               run_dur))
                elif run_dur >= self.DROWSY_CLOSED_SECONDS and run_min < self.deep_thr:
                    # BORDERLINE sustained: the run reached DROWSY_CLOSED_SECONDS
                    # end-to-end but its last SAMPLED closed frame fell just under
                    # the threshold (the eye reopened between frames), so the
                    # mid-run check never saw close_dur >= 1.5 s. Fire here at the
                    # end so a real ~1.5-2 s closure still alerts. `not self.drowsy`
                    # skips closures that already alerted mid-run.
                    near_neutral = (pitch_delta is None
                                    or abs(pitch_delta) <= self.POSE_SUSTAINED_MAX_PITCH)
                    if near_neutral and not self.drowsy:
                        self._enter_drowsy(
                            run_end, 'sustained',
                            'sustained closure %.2fs >= %.2fs at run end '
                            '(min_ear=%.3f vs deep=%.3f, pitch_delta=%s)'
                            % (run_dur, self.DROWSY_CLOSED_SECONDS,
                               run_min, self.deep_thr, pitch_delta))

        if self.open_since is None:
            self.open_since = now
        elif self.drowsy and now - self.open_since >= self.DROWSY_CLEAR_SECONDS:
            self.drowsy = False
            self.drowsy_rule = None
        return self.drowsy, eye_closure_sec

    def _check_continuity(self, now):
        """Safety net for gaps the view could not report (e.g. server error):
        a very long gap between readings is treated like face loss. Normal
        face loss is signalled explicitly by note_face_lost()."""
        if self.last_tick is not None and now - self.last_tick > self.FACE_GAP_SECONDS:
            self._forget_closure()
            self._forget_deep()
            self.last_closure = 0.0
            self.open_since = now   # clear timer runs from the face return
        self.last_tick = now

    def _enter_drowsy(self, now, rule='', reason=''):
        self.drowsy = True
        self.drowsy_rule = rule
        # reset the ~4 s clear window from the ALERT onset: without this a
        # stale open_since (set long before the closure) lets the bottom-of-
        # update_closures logic clear drowsy on the very same frame it was
        # set, so the banner flashes for 0 frames and Drowsiness-Free never
        # drops. Normal blinks (< MAX_BLINK_SECONDS) do NOT reset open_since,
        # so the alert still hides ~4 s after the eyes reopen even if the
        # user keeps blinking.
        self.open_since = None
        if now - self.last_event_time >= self.DROWSY_MIN_EVENT_GAP:
            self.drowsiness_events += 1
            self.last_event_time = now
            log.info("Drowsiness event #%d (%s)", self.drowsiness_events, reason)

    def _update_rate(self, now):
        while self.blink_timestamps and now - self.blink_timestamps[0] > self.WINDOW_SECONDS:
            self.blink_timestamps.popleft()

        elapsed = now - self.track_start
        self.warming_up = elapsed < self.WARMUP_SECONDS
        self.blink_rate_reliable = not self.warming_up

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
        score is high AND no drowsiness alert is active.

        Tip priority: drowsy alert > posture > normal score-based tip. While the
        drowsy banner is active, only recovery/break tips are eligible - never a
        positive tip like 'Feeling good? Keep it up!'."""
        now = time.time()
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
        positive_tips = [
            "You're doing great! Keep the momentum going.",
            "Feeling good? Keep it up!",
            "Great focus - your eyes look relaxed.",
        ]
        # Posture tip: ONE clear message reflecting the CURRENT head pose -
        # the old static "Good posture check - sit up straight!" read as a
        # contradiction. The slouch flag uses the EMA-smoothed pose with
        # HYSTERESIS so the tip does not flip-flop on frame-to-frame jitter.
        sp = self.smooth_pitch_delta
        sy = self.smooth_yaw_delta
        if self.posture_slouching:
            upright_p = (sp is None or sp < self.POSTURE_EXIT_PITCH)
            upright_y = (sy is None or abs(sy) < self.POSTURE_EXIT_YAW)
            if upright_p and upright_y:
                self.posture_slouching = False
        else:
            down_p = (sp is not None and sp > self.POSTURE_ENTER_PITCH)
            turn_y = (sy is not None and abs(sy) > self.POSTURE_ENTER_YAW)
            if down_p or turn_y:
                self.posture_slouching = True
        slouching = self.posture_slouching
        posture_tip = ("Posture check: sit up straight." if slouching
                       else "Good posture. Keep it up.")
        posture_tips = {"Posture check: sit up straight.",
                        "Good posture. Keep it up."}
        maintenance_tips = [
            posture_tip,
            "Hydration check! Drink some water.",
            "Roll your neck slowly in circles.",
        ]
        # "Keep blinking!" reads as mockery when the session shows the user
        # barely blinking (blink_rate < ~8, the same line the score penalises)
        # or when they are drowsy / eyes currently closed. Suppress it there.
        if not (self.blink_rate < 8 or self.drowsy or self.close_active):
            maintenance_tips.append("Keep blinking! Your eyes are doing great.")
        # Drowsy-specific tips: always actionable rest/break advice, never the
        # tension-oriented recovery line that read as irrelevant under the banner.
        drowsy_tips = [
            "Drowsy? Look away from the screen and blink a few times.",
            "Take a short break - stand up and stretch for 30 seconds.",
            "Rest your eyes: look at something 20 feet away for 20 seconds.",
            "Splash cold water on your face or take a quick walk.",
        ]

        # ---- priority ladder: Drowsy > Stress/low > Posture > Blink > Positive ----
        # Each tier picks a pool whose tips are ALL appropriate for that state,
        # so a positive / celebratory tip can never surface under a drowsy
        # banner or a stressed / low score.
        if self.drowsy:                          # tier 1: drowsy alert active
            pool = list(drowsy_tips)
        elif score < 50:                         # tier 2: stress / low score
            pool = list(recovery_tips)
            if break_allowed:
                pool += break_tips
        elif slouching:                          # tier 3: posture needs correcting
            pool = [posture_tip,
                    "Hydration check! Drink some water.",
                    "Roll your neck slowly in circles."]
            if break_allowed:
                pool += break_tips
        elif self.blink_rate < 8:                # tier 4: under-blinking (screen stare)
            pool = ["Rest your eyes for a minute. Look away from the screen.",
                    "Try the 20-20-20 rule: Look 20ft away for 20 sec.",
                    posture_tip,
                    "Hydration check! Drink some water."]
        else:                                    # tier 5: healthy - maintenance/positive
            pool = list(maintenance_tips)
            if score >= 85:
                pool += positive_tips
            if break_allowed:
                pool += break_tips

        # Hold a posture tip for at least POSTURE_TIP_HOLD_SECONDS so a small
        # pose wobble (that slips past hysteresis) cannot swap the wording
        # instantly. A drowsy alert or a low score still overrides at once.
        if (not self.drowsy and score >= 50 and self.last_tip in posture_tips
                and now - self.last_tip_time < self.POSTURE_TIP_HOLD_SECONDS):
            return self.last_tip

        # Refresh IMMEDIATELY if the tip on screen is no longer valid for the
        # current state (e.g. a positive tip left over from a high-score moment
        # now showing under a drowsy banner or a stressed score). Otherwise keep
        # it for TIP_INTERVAL_SECONDS.
        if (self.last_tip and self.last_tip in pool
                and now - self.last_tip_time < self.TIP_INTERVAL_SECONDS):
            return self.last_tip

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

        # head-pose gate (RELATIVE to the calibrated neutral pose).
        # A webcam mounted below the face puts neutral pitch at 26-30 deg; an
        # absolute 25 deg limit gated 73% of frames in a live test and killed
        # every blink. So: during calibration (neutral unknown) the gate is
        # OFF and we simply collect pitch/yaw for the neutral estimate; after
        # calibration the gate measures deviation from that neutral. The
        # limits (30/25) are unchanged - looking down at a keyboard is still
        # +30-40 deg past neutral and still gated.
        pose_bad = False
        yaw_deg = pitch_deg = 0.0
        pitch_delta = yaw_delta = None
        if head_pose is not None:
            try:
                yaw_deg = abs(float(head_pose.get('yaw') or 0.0))
                pitch_deg = abs(float(head_pose.get('pitch') or 0.0))
            except (AttributeError, TypeError, ValueError):
                yaw_deg = pitch_deg = 0.0
            if self.calibrated:
                neutral_p = self.neutral_pitch if self.neutral_pitch is not None else 0.0
                neutral_y = self.neutral_yaw if self.neutral_yaw is not None else 0.0
                pitch_delta = pitch_deg - neutral_p
                yaw_delta = yaw_deg - neutral_y
                self.last_pitch_delta = pitch_delta   # remembered for the posture tip
                self.last_yaw_delta = yaw_delta
                # EMA-smooth the pose for posture decisions: raw deltas flicker
                # frame-to-frame around the slouch threshold and flip-flopped tip.
                a = self.POSTURE_SMOOTH_ALPHA
                if self.smooth_pitch_delta is None:
                    self.smooth_pitch_delta = pitch_delta
                    self.smooth_yaw_delta = yaw_delta
                else:
                    self.smooth_pitch_delta += a * (pitch_delta - self.smooth_pitch_delta)
                    self.smooth_yaw_delta += a * (yaw_delta - self.smooth_yaw_delta)
                pose_bad = (abs(yaw_delta) > self.POSE_MAX_YAW
                            or abs(pitch_delta) > self.POSE_MAX_PITCH)
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

        if valid:
            self.last_ear = ear
        brow = None if brow_tension is None else float(brow_tension)
        self._check_continuity(now)

        if not self.calibrated:
            if valid:
                self._calibrate(ear, brow, now, pitch=pitch_deg, yaw=yaw_deg)
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
                'blink_rate_reliable': False,
            }

        drowsy, eye_closure_sec = self.update_closures(
            ear if valid else None, now, pitch_delta=pitch_delta)
        if valid:
            self._update_baseline(ear, now)
        self._update_rate(now)
        ear_now = ear if valid else self.last_ear

        # Accumulate time the eyes stayed closed beyond a normal blink (slow /
        # sustained closures). Based on the closure RUN length (close_active and
        # close_dur > MAX_BLINK), NOT the deep classification: a half-open or
        # low-camera closure dips below the deep line only briefly (so the old
        # eye_closure_sec gate barely counted it and Drowsiness-Free read ~94%
        # while the eyes were actually shut a much larger share of the session),
        # yet the eye was still substantially closed for the whole run. Normal
        # blinks (<= MAX_BLINK_SECONDS) never accumulate, so healthy blinking
        # does not penalise the score. Drives drowsiness-free %, not banner.
        if (self.close_active and self.close_start is not None
                and (now - self.close_start) > self.MAX_BLINK_SECONDS
                and prev_tick is not None):
            self.closed_drowsy_seconds += min(now - prev_tick, 0.5)

        # brow tension = how far brows have dropped below this user's neutral height.
        # Only sample on stable, near-neutral head poses: dlib's brow landmarks
        # jitter when the head moves or tilts, which used to spike tension
        # (2 -> 47 on a single head move) and fake a Focused/Stressed label.
        # Freezing tension on unstable frames keeps it a pure brow-furrow signal.
        pd, yd = self.last_pitch_delta, self.last_yaw_delta
        pose_stable = ((pd is None or abs(pd) <= self.POSE_TENSION_PITCH)
                       and (yd is None or abs(yd) <= self.POSE_TENSION_YAW))
        if brow is not None and self.brow_baseline > 0 and pose_stable:
            drop_pct = max(0.0, self.brow_baseline - brow) / self.brow_baseline * 100.0
            self.brow_history.append(min(100.0, drop_pct * self.BROW_GAIN))
        avg_brow = (sum(self.brow_history) / len(self.brow_history)) if self.brow_history else 0.0

        expression = self.classify_expression(avg_brow, ear_now)
        score = self.calculate_wellness_score(self.blink_rate, avg_brow, expression, ear_now)
        tip = self.get_wellness_tip(score, expression, avg_brow)

        log.debug("ear=%s thr=%.3f closed=%d blinks=%d rate=%d brow=%.1f",
                  ear, self.deep_thr, int(self.close_active), self.blink_count,
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
            'blink_rate_reliable': self.blink_rate_reliable,
        }
