import os
# Suppress GTK/Qt module warnings
os.environ["NO_AT_BRIDGE"] = "1"
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.*=false"
os.environ["QT_QPA_PLATFORM"] = "xcb" # Often more stable on Linux/X11
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
        tx, ty = (w - text_size[0]) // 2, h - 15
        cv2.putText(img, active_gesture.upper(), (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    
    for ripple in ripples[:]:
        if not ripple.update():
            ripples.remove(ripple)
        else:
            ripple.draw(img)

def get_distance_lms(tracker, lms, p1, p2):
    return tracker.get_distance(lms[p1], lms[p2], img=None, draw=False)[0]

def get_fingers_state(lms):
    """
    Returns a list of 5 booleans representing [Thumb, Index, Middle, Ring, Pinky].
    True = Extended, False = Folded.
    """
    fingers = []
    
    # Thumb: Check distance between tip (4) and index mcp (5) vs ip (3) and index mcp (5)
    # Or more simply: tip.x vs ip.x (depends on hand orientation)
    # Improved Thumb check: tip (4) further from wrist (0) than knuckle (2)?
    # Using distances for better reliability
    d_tip = math.hypot(lms[4][1] - lms[0][1], lms[4][2] - lms[0][2])
    d_base = math.hypot(lms[2][1] - lms[0][1], lms[2][2] - lms[0][2])
    fingers.append(d_tip > d_base + 15)

    # Fingers: Index (8), Middle (12), Ring (16), Pinky (20)
    # Check if tip is above the pip joint (tip-2)
    tips = [8, 12, 16, 20]
    for tip in tips:
        if lms[tip][2] < lms[tip-2][2]:
            fingers.append(True)
        else:
            fingers.append(False)
            
    return fingers

def main():
    w_cam, h_cam = 640, 480
    frameR = 120
    smoothening = 5
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FPS, 60)
    cap.set(3, w_cam)
    cap.set(4, h_cam)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        sys.exit(1)
    
    try:
        tracker = HandTracker(detection_con=0.8)
    except Exception as e:
        print(f"HandTracker Error: {e}")
        sys.exit(1)
    
    screen_w, screen_h = pyautogui.size()
    mouse = MouseController(screen_w, screen_h, w_cam, h_cam, smoothening=smoothening, frame_reduce=frameR)
    
    pTime = 0
    pinch_start_time = None
    last_shortcut_time = 0
    SHORTCUT_COOLDOWN = 1.0  # Reduced for responsiveness
    DRAG_THRESHOLD = 0.30 
    CLICK_DISTANCE = 35
    
    ripples = []
    status_msg = "Awaiting input"
    active_gesture = None
    
    while True:
        success, img = cap.read()
        if not success: break
        img = cv2.flip(img, 1)
        
        cv2.rectangle(img, (frameR, frameR), (w_cam - frameR, h_cam - frameR), (0, 255, 255), 1)
        
        img = tracker.find_hands(img)
        hands_data = tracker.find_all_hands(img)
        
        active_gesture = None
        status_msg = "Awaiting input" if not hands_data else f"{len(hands_data)} Hands Detected"
        
        nav_hand = None
        cmd_hand = None
        
        for hand in hands_data:
            if hand['label'] == "Right": # Physical Right
                nav_hand = hand['lms']
            else: # Physical Left
                cmd_hand = hand['lms']

        # Navigation Hand (Right) - Precision Control
        if nav_hand:
            lms = nav_hand
            fingers = get_fingers_state(lms)
            x1, y1 = lms[8][1], lms[8][2]
            
            # 1. Cursor Move / Click / Drag (Only Index Up)
            if fingers[1] and not any(fingers[2:]):
                d_index = get_distance_lms(tracker, lms, 4, 8)
                if d_index < CLICK_DISTANCE:
                    if pinch_start_time is None: pinch_start_time = time.time()
                    if time.time() - pinch_start_time > DRAG_THRESHOLD:
                        mouse.drag_start()
                        active_gesture = "Dragging"
                    else: active_gesture = "Pinching..."
                else:
                    if pinch_start_time is not None:
                        if time.time() - pinch_start_time <= DRAG_THRESHOLD:
                            if mouse.left_click(): ripples.append(Ripple(x1, y1, (0, 255, 0)))
                        mouse.drag_stop()
                        pinch_start_time = None
                    active_gesture = "Moving"
                mouse.move_mouse(x1, y1)

            # 2. Scrolling (Index and Middle Up)
            elif fingers[1] and fingers[2] and not any(fingers[3:]):
                active_gesture = "Scrolling"
                mouse.scroll(y1)
            
            # 3. Volume (Middle, Ring, Pinky Up)
            elif all(fingers[2:]):
                active_gesture = "Volume"
                mouse.change_volume(lms[12][2])
                
            # 4. Zoom (Index and Pinky Up)
            elif fingers[1] and fingers[4] and not fingers[2] and not fingers[3]:
                active_gesture = "Zoom"
                mouse.zoom(lms[8][2])

            # 5. Right Click (Index, Middle, Ring Up)
            elif fingers[1] and fingers[2] and fingers[3] and not fingers[4]:
                active_gesture = "Right Click"
                if mouse.right_click(): ripples.append(Ripple(x1, y1, (255, 0, 0)))

            # 6. Tab Switching (Thumb and Index Up Only)
            elif fingers[0] and fingers[1] and not any(fingers[2:]):
                curr_time = time.time()
                if curr_time - last_shortcut_time > SHORTCUT_COOLDOWN:
                    mouse.browser_control('next_tab')
                    active_gesture = "Next Tab"
                    last_shortcut_time = curr_time
            
            else:
                mouse.reset_continuous()
                pinch_start_time = None
        else:
            mouse.reset_continuous()
            pinch_start_time = None

        # Commander Hand (Left) - System Shortcuts
        if cmd_hand:
            lms_c = cmd_hand
            fingers_c = get_fingers_state(lms_c)
            curr_time = time.time()
            
            if curr_time - last_shortcut_time > SHORTCUT_COOLDOWN:
                # 1. Alt + Tab (2 fingers)
                if fingers_c[1] and fingers_c[2] and not any(fingers_c[3:]):
                    mouse.system_shortcut(['alt', 'tab'])
                    active_gesture = "Alt + Tab"
                    last_shortcut_time = curr_time
                # 2. Show Desktop (3 fingers)
                elif all(fingers_c[1:4]) and not fingers_c[4]:
                    mouse.window_control('minimize') # Minimize current or show desktop
                    active_gesture = "Minimize / Desktop"
                    last_shortcut_time = curr_time
                # 3. Copy (Thumb + Index Pinch)
                elif get_distance_lms(tracker, lms_c, 4, 8) < CLICK_DISTANCE:
                    mouse.edit_control('copy')
                    active_gesture = "Copy"
                    last_shortcut_time = curr_time
                # 4. Paste (Thumb + Middle Pinch)
                elif get_distance_lms(tracker, lms_c, 4, 12) < CLICK_DISTANCE:
                    mouse.edit_control('paste')
                    active_gesture = "Paste"
                    last_shortcut_time = curr_time

        cTime = time.time()
        fps = 1 / (max(cTime - pTime, 0.001))
        pTime = cTime
        
        draw_hud(img, fps, status_msg, active_gesture, ripples)
        cv2.imshow("Hand Gesture Control", img)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
