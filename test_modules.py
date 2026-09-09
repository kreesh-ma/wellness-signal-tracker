import sys
sys.path.insert(0, 'C:\\Users\\Kreeshma\\codestorm')

from core.face_analyzer import FaceAnalyzer
from core.wellness_engine import WellnessEngine

print("Testing modules...")

# Test FaceAnalyzer
analyzer = FaceAnalyzer()
print("[OK] FaceAnalyzer initialized")

# Test WellnessEngine
engine = WellnessEngine()
print("[OK] WellnessEngine initialized")

# Test wellness calculation
test_reading = engine.process_reading(ear=0.28, brow_tension=22)
print(f"[OK] Wellness calculation: {test_reading}")

print("\nAll modules working!")
