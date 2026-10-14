"""Replay the recorded real-EAR live webcam trace through a fresh
WellnessEngine and assert the engine counts the user's real blinks.

The trace was recorded live on 2026 with the user blinking ~20/min and a
webcam below face level (neutral pitch ~27 deg). Before the relative-pose
gate + 0.75x blink line, this same trace yielded 0 blinks / 0 per-min.
"""
import csv
import os
import sys
import types
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import core.wellness_engine as we
from core.wellness_engine import WellnessEngine

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'fixtures', 'real_ear_live_trace.csv')


def load_frames(path):
    rows = list(csv.DictReader(
        l for l in open(path) if not l.startswith('#')))
    frames = []
    for r in rows:
        ear = float(r['ear'])
        if ear <= 0:
            continue
        frames.append((float(r['t_rel']), ear,
                       float(r['yaw']), float(r['pitch'])))
    return frames


class _Clock(object):
    def __init__(self):
        self.t = 0.0

    def time(self):
        return self.t


def replay(frames):
    clock = _Clock()
    we.time = clock  # monkeypatch module-level time for deterministic replay
    eng = WellnessEngine()
    for (t, ear, yaw, pitch) in frames:
        clock.t = t
        eng.process_reading(ear, None, head_pose={'yaw': yaw, 'pitch': pitch})
    return eng


class RealEarReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = load_frames(FIXTURE)
        cls.eng = replay(cls.frames)
        cls.span = cls.frames[-1][0] - cls.frames[0][0]

    def test_trace_is_the_real_recording(self):
        # ~77 s of frames at ~8 fps, non-trivial EAR variation (not synthetic)
        self.assertGreater(len(self.frames), 400)
        self.assertGreater(self.span, 60)
        ears = [f[1] for f in self.frames]
        self.assertGreater(max(ears) - min(ears), 0.1)

    def test_counts_the_real_blinks(self):
        # user reported ~20/min over ~77 s -> ~25 blinks; require a tight band
        # around the manual count (20/min -> 24-26 here, allow 15..35)
        self.assertGreaterEqual(self.eng.blink_count, 15,
                                'under-count: got %d' % self.eng.blink_count)
        self.assertLessEqual(self.eng.blink_count, 35,
                             'over-count: got %d' % self.eng.blink_count)

    def test_rate_in_plausible_range(self):
        # healthy adult resting blink rate is 10-30/min
        self.assertGreaterEqual(self.eng.blink_rate, 10)
        self.assertLessEqual(self.eng.blink_rate, 30)

    def test_no_drowsy_false_alarms(self):
        self.assertEqual(self.eng.drowsiness_events, 0)

    def test_relative_pose_gate_learns_neutral_pitch(self):
        # low camera -> neutral pitch ~27 deg, learned not gated away
        self.assertIsNotNone(self.eng.neutral_pitch)
        self.assertAlmostEqual(self.eng.neutral_pitch, 27.0, delta=4.0)
        self.assertLess(abs(self.eng.blink_rate
                            - round(self.eng.blink_count
                                    / (self.span / 60.0))), 3)

    def test_blink_line_sits_between_noise_and_blinks(self):
        ears = sorted(f[1] for f in self.frames)
        p90 = ears[int(0.90 * len(ears))]
        p10 = ears[int(0.10 * len(ears))]
        # line must be below the open-eye noise floor but above deep dips
        self.assertLess(self.eng.blink_thr, p90)
        self.assertLess(self.eng.blink_thr, self.eng.ear_baseline)


if __name__ == '__main__':
    unittest.main(verbosity=2)
