import cv2
import sys
sys.path.insert(0, 'C:\\Users\\Kreeshma\\codestorm')

from core.face_analyzer import FaceAnalyzer

print("Testing FaceAnalyzer...")
analyzer = FaceAnalyzer()

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("ERROR: Cannot open camera")
    exit()

print("Camera opened. Press 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    result = analyzer.analyze_frame(frame)
    
    if result:
        print(f"Face detected! EAR: {result['ear']:.3f}, Brow: {result['brow_tension']:.2f}")
    
    cv2.imshow('Test', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Test complete!")
