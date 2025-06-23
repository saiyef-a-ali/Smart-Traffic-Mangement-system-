
# opencv.py

import cv2
from ultralytics import YOLO
import time
from google.colab import files

# Configuration
MODEL = "yolo11x.pt"
TARGET_CLASSES = [1, 2, 3, 5, 7]   # {1: 'bicycle', 2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
FRAME_SKIP = 3
IMG_SIZE = 320
input_path = "traffic2.mp4"
output_path = "processed_video.mp4"

# Initialize
model = YOLO(MODEL)
model.fuse()
cap = cv2.VideoCapture(input_path)

# Get video properties
fps = cap.get(cv2.CAP_PROP_FPS)
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
video_length = frame_count / fps

# Video writer setup
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_path, fourcc, fps//FRAME_SKIP,
                      (int(cap.get(3)), int(cap.get(4))))

# Start processing timer
start_time = time.time()

flag = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    if int(cap.get(cv2.CAP_PROP_POS_FRAMES)) % FRAME_SKIP != 0:
        continue

    results = model.predict(
        frame,
        imgsz=IMG_SIZE,
        classes=TARGET_CLASSES,
        half=True,
        device=0,
        verbose=False,
    )

    flag += 1

    if flag == 10:
        result = results[0]
        boxes = result.boxes

        print("\n🔍 First Detection Frame Results:")
        for i, box in enumerate(boxes):
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            coords = box.xyxy[0].tolist()
            class_name = model.names[cls_id]

            print(f"Detection {i+1}:")
            print(f"  - Class: {class_name} (ID: {cls_id})")
            print(f"  - Confidence: {conf:.2f}")
            print(f"  - Coordinates: {coords}")
            print()

    annotated_frame = results[0].plot()
    out.write(annotated_frame)

# Calculate processing time
end_time = time.time()
processing_duration = end_time - start_time

cap.release()
out.release()

print(f"\n⏱️ Performance Metrics:")
print(f"- Video length: {video_length:.2f} seconds")
print(f"- Processing time: {processing_duration:.2f} seconds")
print(f"- Real-time ratio: {video_length/processing_duration:.2f}x")

files.download(output_path)
