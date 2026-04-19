import cv2
import pyautogui
import time
import sys
from hand_tracker import HandTracker
from mouse_controller import MouseController

def main():
    w_cam, h_cam = 640, 480
    frameR = 100 # Frame Reduction to create an active tracking area
    smoothening = 6 # Sensitivity of mouse
    
    cap = cv2.VideoCapture(0)
    cap.set(3, w_cam)
    cap.set(4, h_cam)
    
    # Allow MediaPipe to warm up and check camera
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        sys.exit(1)
    
    try:
        tracker = HandTracker(max_hands=1, detection_con=0.8)
    except Exception as e:
        print(f"Failed to initialize MediaPipe HandTracker: {e}")
        print("Please ensure 'hand_landmarker.task' is downloaded in the directory.")
        sys.exit(1)
    
    screen_w, screen_h = pyautogui.size()
    mouse = MouseController(screen_w, screen_h, w_cam, h_cam, smoothening=smoothening, frame_reduce=frameR)
    
    # Finger tip landmark IDs
    THUMB_TIP = 4
    INDEX_TIP = 8
    MIDDLE_TIP = 12
    RING_TIP = 16
    PINKY_TIP = 20
    
    pTime = 0
    
    print("Starting Hand Gesture Mouse Controller...")
    
    while True:
        success, img = cap.read()
        if not success:
            break
            
        # Flip image horizontally for natural (mirror-like) interaction
        img = cv2.flip(img, 1)
        
        # Draw the active tracking area on screen
        cv2.rectangle(img, (frameR, frameR), (w_cam - frameR, h_cam - frameR), (255, 0, 255), 2)
        
        # Passing img to our new tracker which also generates internal timestamp
        img = tracker.find_hands(img)
        lms_list = tracker.find_position(img)
        
        if len(lms_list) != 0:
            x1, y1 = lms_list[INDEX_TIP][1], lms_list[INDEX_TIP][2]
            
            # Distance Tracking
            length_left, img, line_info_left = tracker.get_distance(lms_list[THUMB_TIP], lms_list[INDEX_TIP], img, False)
            length_right, img, line_info_right = tracker.get_distance(lms_list[THUMB_TIP], lms_list[MIDDLE_TIP], img, False)
            length_pinky, img, line_info_pinky = tracker.get_distance(lms_list[THUMB_TIP], lms_list[PINKY_TIP], img, False)
            length_firefox, img, line_info_firefox = tracker.get_distance(lms_list[THUMB_TIP], lms_list[RING_TIP], img, False)
            
            # Continuous mode distances
            length_scroll, img, _ = tracker.get_distance(lms_list[INDEX_TIP], lms_list[MIDDLE_TIP], img, False)
            length_volume, img, _ = tracker.get_distance(lms_list[MIDDLE_TIP], lms_list[RING_TIP], img, False)

            CLICK_THRESHOLD = 30
            
            # Reset continuous actions if gesture is not active
            if length_scroll >= CLICK_THRESHOLD and length_volume >= CLICK_THRESHOLD:
                mouse.reset_continuous()
            
            # Execution Logic
            if length_scroll < CLICK_THRESHOLD and length_left > CLICK_THRESHOLD and length_right > CLICK_THRESHOLD:
                # Scroll Mode
                cv2.circle(img, (x1, y1), 15, (255, 255, 0), cv2.FILLED)
                mouse.scroll(y1)
            elif length_volume < CLICK_THRESHOLD and length_firefox > CLICK_THRESHOLD and length_right > CLICK_THRESHOLD:
                # Volume Mode (using Middle finger Y as reference)
                y_vol = lms_list[MIDDLE_TIP][2]
                cv2.circle(img, (lms_list[MIDDLE_TIP][1], y_vol), 15, (0, 0, 255), cv2.FILLED)
                mouse.change_volume(y_vol)
            else:
                # Normal move
                mouse.move_mouse(x1, y1)
                
                # Single action clicks
                if length_left < CLICK_THRESHOLD:
                    cv2.circle(img, (line_info_left[4], line_info_left[5]), 15, (0, 255, 0), cv2.FILLED)
                    mouse.left_click()
                elif length_right < CLICK_THRESHOLD:
                    cv2.circle(img, (line_info_right[4], line_info_right[5]), 15, (255, 0, 0), cv2.FILLED)
                    mouse.right_click()
                elif length_firefox < CLICK_THRESHOLD:
                    cv2.circle(img, (line_info_firefox[4], line_info_firefox[5]), 15, (0, 165, 255), cv2.FILLED)
                    mouse.open_firefox()
                elif length_pinky < CLICK_THRESHOLD:
                    cv2.circle(img, (line_info_pinky[4], line_info_pinky[5]), 15, (0, 255, 255), cv2.FILLED)
                    mouse.take_screenshot()
                
        # Calculate and show FPS
        cTime = time.time()
        fps = 1 / (max(cTime - pTime, 0.001)) # prevent divide by zero
        pTime = cTime
        cv2.putText(img, f'FPS: {int(fps)}', (20, 50), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)
        
        cv2.imshow("Hand Gesture Mouse System", img)
        
        # Press 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
