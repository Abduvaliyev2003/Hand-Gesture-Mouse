import pyautogui
import time
import numpy as np

class MouseController:
    def __init__(self, screen_w, screen_h, frame_w, frame_h, smoothening=7, frame_reduce=100):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.frame_w = frame_w
        self.frame_h = frame_h
        self.smoothening = smoothening
        self.frame_reduce = frame_reduce
        
        self.ploc_x, self.ploc_y = 0, 0
        self.cloc_x, self.cloc_y = 0, 0
        
        # Cooldown state to prevent multiple rapid clicks
        self.last_left_click_time = 0
        self.last_right_click_time = 0
        self.last_screenshot_time = 0
        self.last_firefox_time = 0
        self.last_volume_time = 0
        self.click_cooldown = 0.5 # Seconds
        self.screenshot_cooldown = 2.0 # Seconds
        self.firefox_cooldown = 3.0 # Seconds
        self.volume_cooldown = 0.1 # Seconds
        
        self.prev_y_scroll = None
        self.prev_y_volume = None
        
        # Usually fine to disable if we do bounded moves, but helps avoid program crashes
        pyautogui.FAILSAFE = False
        
    def move_mouse(self, x, y):
        # Map values from reduced camera frame box to screen resolution
        x3 = np.interp(x, (self.frame_reduce, self.frame_w - self.frame_reduce), (0, self.screen_w))
        y3 = np.interp(y, (self.frame_reduce, self.frame_h - self.frame_reduce), (0, self.screen_h))
        
        # Smoothen values to reduce jitter
        self.cloc_x = self.ploc_x + (x3 - self.ploc_x) / self.smoothening
        self.cloc_y = self.ploc_y + (y3 - self.ploc_y) / self.smoothening
        
        # Ensure we stay within screen bounds (roughly)
        move_x = max(0, min(self.screen_w, self.cloc_x))
        move_y = max(0, min(self.screen_h, self.cloc_y))
        
        # Perform move
        try:
            pyautogui.moveTo(move_x, move_y)
        except Exception as e:
            pass
            
        self.ploc_x, self.ploc_y = self.cloc_x, self.cloc_y
            
    def left_click(self):
        current_time = time.time()
        if current_time - self.last_left_click_time > self.click_cooldown:
            pyautogui.click()
            self.last_left_click_time = current_time
            return True
        return False
        
    def right_click(self):
        current_time = time.time()
        if current_time - self.last_right_click_time > self.click_cooldown:
            pyautogui.rightClick()
            self.last_right_click_time = current_time
            return True
        return False
        
    def take_screenshot(self):
        current_time = time.time()
        if current_time - self.last_screenshot_time > self.screenshot_cooldown:
            filename = f"screenshot_{int(current_time)}.png"
            pyautogui.screenshot(filename)
            print(f"Screenshot taken: {filename}")
            self.last_screenshot_time = current_time
            return True
        return False
        
    def open_firefox(self):
        current_time = time.time()
        if current_time - self.last_firefox_time > self.firefox_cooldown:
            import subprocess
            subprocess.Popen(['firefox'])
            print("Firefox launched!")
            self.last_firefox_time = current_time
            return True
        return False

    def scroll(self, y):
        if self.prev_y_scroll is None:
            self.prev_y_scroll = y
            return
        
        dy = y - self.prev_y_scroll
        if abs(dy) > 5:  # sensitivity threshold
            if dy > 0:
                pyautogui.scroll(-80) # Scroll Down
            else:
                pyautogui.scroll(80)  # Scroll Up
            self.prev_y_scroll = y

    def change_volume(self, y):
        if self.prev_y_volume is None:
            self.prev_y_volume = y
            return
            
        dy = y - self.prev_y_volume
        current_time = time.time()
        
        if abs(dy) > 10 and (current_time - self.last_volume_time > self.volume_cooldown):
            import os
            if dy > 0:
                os.system("pactl set-sink-volume @DEFAULT_SINK@ -5%")
                print("Volume Down")
            else:
                os.system("pactl set-sink-volume @DEFAULT_SINK@ +5%")
                print("Volume Up")
            self.prev_y_volume = y
            self.last_volume_time = current_time

    def reset_continuous(self):
        self.prev_y_scroll = None
        self.prev_y_volume = None
