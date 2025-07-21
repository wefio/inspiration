# 训练
import cv2
import os
import numpy as np

faces = []
labels = []

for f in os.listdir('faces'):
    if f.endswith('.jpg'):
        faces.append(cv2.imread(os.path.join('faces', f), cv2.IMREAD_GRAYSCALE))
        labels.append(0)

if len(faces) == 0:
    raise Exception("No face images found for training")
else:
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array(labels))
    recognizer.write('trainer.yml')
    print("Training complete")