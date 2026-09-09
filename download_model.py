import urllib.request
import bz2
import os

url = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
output_path = "models/shape_predictor_68_face_landmarks.dat"

print("Downloading dlib shape predictor model...")
print("This may take a few minutes (~99MB)")

urllib.request.urlretrieve(url, output_path + ".bz2")

print("Extracting...")
with bz2.open(output_path + ".bz2", 'rb') as f:
    data = f.read()
    with open(output_path, 'wb') as out:
        out.write(data)

os.remove(output_path + ".bz2")
print("Done! Model saved to:", output_path)
