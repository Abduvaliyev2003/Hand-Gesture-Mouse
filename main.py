import cv2
import pyautogui
import time
import sys
import numpy as np
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

def is_finger_extended(tracker, lms, finger_tip):
    # Very basic check: is the finger tip further from the wrist (0) than the pip joint (tip-2)?
    # For more accuracy, use a proper extension check.
    d_tip = get_distance_lms(tracker, lms, 0, finger_tip)
    d_pip = get_distance_lms(tracker, lms, 0, finger_tip - 2)
    return d_tip > d_pip

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
    SHORTCUT_COOLDOWN = 2.0  # Increased cooldown
    DRAG_THRESHOLD = 0.35 
    CLICK_DISTANCE = 35
    
    ripples = []
    status_msg = "Initializing System..."
    active_gesture = None
    
    # Initialization Greeting removed
    
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
        
        # Identify Left and Right hands (MediaPipe labels are mirrored in original view)
        for hand in hands_data:
            if hand['label'] == "Right": # Mirrored physical Right hand
                nav_hand = hand['lms']
            else:
                cmd_hand = hand['lms']

        # Navigation Hand Logic (Right)
        if nav_hand:
            x1, y1 = nav_hand[8][1], nav_hand[8][2]
            
            d_index = get_distance_lms(tracker, nav_hand, 4, 8)
            
            is_yt = get_distance_lms(tracker, nav_hand, 4, 8) < 45 and \
                    get_distance_lms(tracker, nav_hand, 4, 12) < 45 and \
                    get_distance_lms(tracker, nav_hand, 4, 16) < 45 and \
                    get_distance_lms(tracker, nav_hand, 4, 20) > 60
            
            is_ig = get_distance_lms(tracker, nav_hand, 4, 12) < 45 and \
                    get_distance_lms(tracker, nav_hand, 4, 16) < 45 and \
                    get_distance_lms(tracker, nav_hand, 4, 20) < 45 and \
                    get_distance_lms(tracker, nav_hand, 4, 8) > 60
            
            if is_yt:
                if mouse.open_url('https://www.youtube.com'):
                    ripples.append(Ripple(x1, y1, (0, 0, 255)))
                    active_gesture = "Opening YouTube"
            elif is_ig:
                if mouse.open_url('https://www.instagram.com'):
                    ripples.append(Ripple(x1, y1, (255, 0, 255)))
                    active_gesture = "Opening Instagram"
            elif all(get_distance_lms(tracker, nav_hand, 4, tip) < 45 for tip in [12, 16, 20]) and d_index < 45:
                if mouse.toggle_media():
                    ripples.append(Ripple(x1, y1, (255, 255, 0)))
                active_gesture = "Media Toggle"
            elif get_distance_lms(tracker, nav_hand, 8, 12) < CLICK_DISTANCE:
                active_gesture = "Scrolling"
                mouse.scroll(y1)
            elif get_distance_lms(tracker, nav_hand, 12, 16) < CLICK_DISTANCE:
                active_gesture = "Volume"
                mouse.change_volume(nav_hand[12][2])
            elif get_distance_lms(tracker, nav_hand, 16, 20) < CLICK_DISTANCE:
                active_gesture = "Brightness"
                mouse.change_brightness(nav_hand[16][2])
            elif get_distance_lms(tracker, nav_hand, 8, 20) < CLICK_DISTANCE:
                active_gesture = "Zoom"
                mouse.zoom(nav_hand[8][2])
            else:
                mouse.reset_continuous()
                if get_distance_lms(tracker, nav_hand, 4, 16) < CLICK_DISTANCE:
                    active_gesture = "Browser"
                    mouse.open_app('firefox')
                elif get_distance_lms(tracker, nav_hand, 4, 20) < CLICK_DISTANCE:
                    active_gesture = "Screenshot"
                    if mouse.take_screenshot():
                        ripples.append(Ripple(x1, y1, (0, 255, 255)))
                elif get_distance_lms(tracker, nav_hand, 4, 12) < CLICK_DISTANCE:
                    active_gesture = "Right Click"
                    if mouse.right_click():
                        ripples.append(Ripple(x1, y1, (255, 0, 0)))
                elif d_index < CLICK_DISTANCE:
                    if pinch_start_time is None: pinch_start_time = time.time()
                    if time.time() - pinch_start_time > DRAG_THRESHOLD:
                        mouse.drag_start()
                        active_gesture = "Dragging"
                    else: active_gesture = "Pinching..."
                    mouse.move_mouse(x1, y1)
                else:
                    if pinch_start_time is not None:
                        if time.time() - pinch_start_time <= DRAG_THRESHOLD:
                            if mouse.left_click(): ripples.append(Ripple(x1, y1, (0, 255, 0)))
                        mouse.drag_stop()
                        pinch_start_time = None
                    mouse.move_mouse(x1, y1)
        else:
            mouse.reset_continuous()
            pinch_start_time = None

        # Commander Hand Logic (Left)
        if cmd_hand:
            curr_time = time.time()
            if curr_time - last_shortcut_time > SHORTCUT_COOLDOWN:
                d_4_8 = get_distance_lms(tracker, cmd_hand, 4, 8)
                d_4_12 = get_distance_lms(tracker, cmd_hand, 4, 12)
                d_4_20 = get_distance_lms(tracker, cmd_hand, 4, 20)
                
                # Optimized logic: Pinch must be clear (other fingers extended)
                # Pinch Index + Thumb = Alt+Tab
                if d_4_8 < CLICK_DISTANCE and is_finger_extended(tracker, cmd_hand, 12):
                    mouse.system_shortcut(['alt', 'tab'])
                    last_shortcut_time = curr_time
                # Pinch Middle + Thumb = Show Desktop (Super+D)
                elif d_4_12 < CLICK_DISTANCE and is_finger_extended(tracker, cmd_hand, 8):
                    mouse.system_shortcut(['super', 'd'])
                    last_shortcut_time = curr_time
                # Pinch Pinky + Thumb = Close Window (Alt+F4)
                elif d_4_20 < CLICK_DISTANCE and is_finger_extended(tracker, cmd_hand, 8):
                    mouse.system_shortcut(['alt', 'f4'])
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
