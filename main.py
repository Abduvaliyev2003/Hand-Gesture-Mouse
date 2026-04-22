import os
# Suppress GTK/Qt module warnings
os.environ["NO_AT_BRIDGE"] = "1"
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.*=false"
os.environ["QT_QPA_PLATFORM"] = "xcb" 
import cv2
import pyautogui
import time
import sys
import numpy as np
import math
from hand_tracker import HandTracker
from mouse_controller import MouseController

class Ripple:
    def __init__(self, x, y, color=(0, 255, 0)):
        self.x, self.y = x, y
        self.radius = 10
        self.max_radius = 60
        self.opacity = 255
        self.color = color
    def update(self):
        self.radius += 5
        self.opacity -= 15
        return self.radius < self.max_radius and self.opacity > 0
    def draw(self, img):
        overlay = img.copy()
        cv2.circle(overlay, (self.x, self.y), self.radius, self.color, 2)
        cv2.addWeighted(overlay, self.opacity / 255, img, 1 - self.opacity / 255, 0, img)

def draw_hud(img, fps, status="Ready", active_gesture=None, ripples=[]):
    h, w, _ = img.shape
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
    cv2.rectangle(overlay, (0, h-40), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.4, img, 0.6, 0, img)
    
    cv2.putText(img, f"FPS: {int(fps)}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 1)
    cv2.putText(img, f"STATUS: {status}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    if active_gesture:
        text_size = cv2.getTextSize(active_gesture.upper(), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        tx = (w - text_size[0]) // 2
        cv2.putText(img, active_gesture.upper(), (tx, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    
    for ripple in ripples[:]:
        if not ripple.update(): ripples.remove(ripple)
        else: ripple.draw(img)

def get_distance_lms(tracker, lms, p1, p2):
    return tracker.get_distance(lms[p1], lms[p2], img=None, draw=False)[0]

def main():
    w_cam, h_cam = 640, 480
    frameR = 120
    smoothening = 5
    cap = cv2.VideoCapture(0)
    cap.set(3, w_cam); cap.set(4, h_cam)
    if not cap.isOpened(): sys.exit(1)
    
    tracker = HandTracker(detection_con=0.8)
    screen_w, screen_h = pyautogui.size()
    mouse = MouseController(screen_w, screen_h, w_cam, h_cam, smoothening=smoothening, frame_reduce=frameR)
    
    pTime = 0
    pinch_start_time = None
    last_shortcut_time = 0
    SHORTCUT_COOLDOWN = 1.0  
    DRAG_THRESHOLD = 0.30 
    CLICK_DIST = 35
    
    ripples = []
    
    while True:
        success, img = cap.read()
        if not success: break
        img = cv2.flip(img, 1)
        img = tracker.find_hands(img)
        hands_data = tracker.find_all_hands(img)
        
        active_gesture = None
        nav_hand = None; cmd_hand = None
        for hand in hands_data:
            if hand['label'] == "Right": nav_hand = hand['lms']
            else: cmd_hand = hand['lms']

        if nav_hand:
            lms = nav_hand
            x1, y1 = lms[8][1], lms[8][2]
            
            d_4_8 = get_distance_lms(tracker, lms, 4, 8)   # Thumb-Index
            d_8_12 = get_distance_lms(tracker, lms, 8, 12) # Index-Middle
            d_12_16 = get_distance_lms(tracker, lms, 12, 16) # Middle-Ring
            d_16_20 = get_distance_lms(tracker, lms, 16, 20) # Ring-Pinky
            d_8_20 = get_distance_lms(tracker, lms, 8, 20)  # Index-Pinky (Zoom)
            d_12_20 = get_distance_lms(tracker, lms, 12, 20) # Middle-Pinky (Volume)

            curr_time = time.time()

            # 1. Right Click (Index, Middle, Ring closed)
            if d_8_12 < 35 and d_12_16 < 35 and d_4_8 > 40:
                active_gesture = "Right Click"
                if mouse.right_click(): ripples.append(Ripple(x1, y1, (255, 0, 0)))
            
            # 2. Scroll (Index and Middle closed)
            elif d_8_12 < 30 and d_12_16 > 40:
                active_gesture = "Scrolling"
                mouse.scroll(y1)

            # 3. Volume (Middle, Ring, Pinky together)
            elif d_12_16 < 30 and d_16_20 < 30:
                active_gesture = "Volume"
                mouse.change_volume(lms[12][2])

            # 4. Zoom (Index and Pinky together)
            elif d_8_20 < 40 and d_8_12 > 40:
                active_gesture = "Zoom"
                mouse.zoom(y1)

            # 5. Browser Tab (Thumb and Index together)
            elif d_4_8 < 25 and d_8_12 > 40:
                if curr_time - last_shortcut_time > SHORTCUT_COOLDOWN:
                    mouse.browser_control('next_tab')
                    last_shortcut_time = curr_time
                    active_gesture = "Next Tab"

            # 6. Move & Left Click (Default)
            else:
                if d_4_8 < CLICK_DIST: # Pinch for click/drag
                    if pinch_start_time is None: pinch_start_time = curr_time
                    if curr_time - pinch_start_time > DRAG_THRESHOLD:
                        mouse.drag_start()
                        active_gesture = "Dragging"
                else:
                    if pinch_start_time is not None:
                        if curr_time - pinch_start_time <= DRAG_THRESHOLD:
                            if mouse.left_click(): ripples.append(Ripple(x1, y1))
                        mouse.drag_stop()
                        pinch_start_time = None
                    active_gesture = "Moving"
                mouse.move_mouse(x1, y1)

        if cmd_hand:
            lms_c = cmd_hand
            d_4_8_c = get_distance_lms(tracker, lms_c, 4, 8)   # Thumb-Index
            d_4_12_c = get_distance_lms(tracker, lms_c, 4, 12) # Thumb-Middle
            d_4_16_c = get_distance_lms(tracker, lms_c, 4, 16) # Thumb-Ring
            d_4_20_c = get_distance_lms(tracker, lms_c, 4, 20) # Thumb-Pinky
            
            curr_time = time.time()
            
            if curr_time - last_shortcut_time > SHORTCUT_COOLDOWN:
                # 1. Copy (Thumb + Index)
                if d_4_8_c < 30:
                    mouse.edit_control('copy'); active_gesture = "Copy"
                    last_shortcut_time = curr_time
                # 2. Instagram (Thumb + Middle)
                elif d_4_12_c < 30:
                    mouse.open_url("https://www.instagram.com")
                    active_gesture = "Instagram"
                    last_shortcut_time = curr_time
                # 3. YouTube (Thumb + Ring)
                elif d_4_16_c < 30:
                    mouse.open_url("https://www.youtube.com")
                    active_gesture = "YouTube"
                    last_shortcut_time = curr_time
                # 4. Screenshot (Thumb + Pinky)
                elif d_4_20_c < 30:
                    mouse.take_screenshot()
                    active_gesture = "Screenshot"
                    last_shortcut_time = curr_time
                # 5. Paste (Index and Middle together)
                elif get_distance_lms(tracker, lms_c, 8, 12) < 30:
                    mouse.edit_control('paste'); active_gesture = "Paste"
                    last_shortcut_time = curr_time

        cTime = time.time()
        fps = 1 / (cTime - pTime) if (cTime - pTime) > 0 else 0
        pTime = cTime
        draw_hud(img, fps, f"{len(hands_data)} Hands", active_gesture, ripples)
        cv2.imshow("Hand Control Full Revert", img)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
            
    cap.release(); cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
