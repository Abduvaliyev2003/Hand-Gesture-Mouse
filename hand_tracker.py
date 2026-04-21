import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import math
import time

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),      # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),      # Index finger
    (5, 9), (9, 10), (10, 11), (11, 12), # Middle finger
    (9, 13), (13, 14), (14, 15), (15, 16), # Ring finger
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20) # Pinky
]

class HandTracker:
    def __init__(self, mode=False, max_hands=1, detection_con=0.7, track_con=0.7):
        self.model_path = 'hand_landmarker.task'
        
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2, # Set to 2 for dual-hand support
            min_hand_detection_confidence=float(detection_con),
            min_hand_presence_confidence=float(track_con),
            min_tracking_confidence=float(track_con)
        )
        self.detector = vision.HandLandmarker.create_from_options(options)
        self.results = None
        self._start_time = time.time()
        
    def find_hands(self, img, draw=True):
        # MediaPipe tasks requires an RGB format
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Create MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
        
        # Calculate timestamp for VIDEO mode
        current_timestamp_ms = int((time.time() - self._start_time) * 1000)
        
        # Run inference
        self.results = self.detector.detect_for_video(mp_image, current_timestamp_ms)
        
        if draw and self.results.hand_landmarks:
            for i, hand_landmarks in enumerate(self.results.hand_landmarks):
                h, w, _ = img.shape
                
                # Draw connections
                for connection in HAND_CONNECTIONS:
                    p1 = hand_landmarks[connection[0]]
                    p2 = hand_landmarks[connection[1]]
                    
                    x1, y1 = int(p1.x * w), int(p1.y * h)
                    x2, y2 = int(p2.x * w), int(p2.y * h)
                    
                    cv2.line(img, (x1, y1), (x2, y2), (200, 200, 200), 1) # Thinner, grey lines
                    
                # Draw landmarks
                for id, landmark in enumerate(hand_landmarks):
                    x, y = int(landmark.x * w), int(landmark.y * h)
                    # Tips get a special highlight
                    if id in [4, 8, 12, 16, 20]:
                        cv2.circle(img, (x, y), 6, (0, 255, 255), cv2.FILLED)
                        cv2.circle(img, (x, y), 8, (0, 255, 255), 1)
                    else:
                        cv2.circle(img, (x, y), 3, (150, 150, 150), cv2.FILLED)
                
                # Draw hand label (Left/Right)
                handedness = self.results.handedness[i][0].category_name
                cv2.putText(img, handedness, (int(hand_landmarks[0].x * w), int(hand_landmarks[0].y * h) - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                    
        return img
        
    def find_all_hands(self, img):
        hands_data = []
        if self.results and self.results.hand_landmarks:
            h, w, _ = img.shape
            for i, hand_landmarks in enumerate(self.results.hand_landmarks):
                lms = []
                for id, lm in enumerate(hand_landmarks):
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    lms.append([id, cx, cy])
                
                # In MediaPipe, handedness is often inverted when the image is flipped
                # for a mirror effect. We'll return the raw label for now.
                label = self.results.handedness[i][0].category_name
                hands_data.append({"label": label, "lms": lms})
        return hands_data
        
    def get_distance(self, p1, p2, img=None, draw=True, r=15, t=3):
        x1, y1 = p1[1], p1[2]
        x2, y2 = p2[1], p2[2]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        
        if draw and img is not None:
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), t)
            cv2.circle(img, (x1, y1), r, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (x2, y2), r, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (cx, cy), r, (0, 0, 255), cv2.FILLED)
            
        length = math.hypot(x2 - x1, y2 - y1)
        return length, img, [x1, y1, x2, y2, cx, cy]
