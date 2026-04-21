import pyautogui
import time
import numpy as np
import webbrowser
import subprocess
import os

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
        self.last_brightness_time = 0
        self.click_cooldown = 0.5 # Seconds
        self.screenshot_cooldown = 2.0 # Seconds
        self.firefox_cooldown = 3.0 # Seconds
        self.volume_cooldown = 0.1 # Seconds
        self.brightness_cooldown = 0.1 # Seconds
        
        # Wayland Keycodes (Linux Kernel)
        self.key_map = {
            'ctrl': 29, 'alt': 56, 'super': 125, 'shift': 42,
            'tab': 15, 'c': 46, 'v': 47, 'z': 44, 
            'up': 103, 'down': 108, 'f4': 62
        }
        
        self.prev_y_scroll = None
        self.prev_y_volume = None
        self.prev_y_brightness = None
        self.prev_y_zoom = None
        
        self.is_dragging = False
        
        # Performance optimization: Zero latency
        pyautogui.PAUSE = 0
        pyautogui.MINIMUM_DURATION = 0
        pyautogui.FAILSAFE = False
        
    def move_mouse(self, x, y):
        # Map values from reduced camera frame box to screen resolution
        x3 = np.interp(x, (self.frame_reduce, self.frame_w - self.frame_reduce), (0, self.screen_w))
        y3 = np.interp(y, (self.frame_reduce, self.frame_h - self.frame_reduce), (0, self.screen_h))
        
        # Adaptive Smoothing: Less smoothing when moving fast, more when nearly still
        dx = x3 - self.ploc_x
        dy = y3 - self.ploc_y
        dist = (dx**2 + dy**2)**0.5
        
        # Dynamic factor: high movement = low smoothing factor (min 2), low movement = high factor
        curr_smooth = max(2, self.smoothening - (dist / 15))
        
        # Smoothen values
        self.cloc_x = self.ploc_x + dx / curr_smooth
        self.cloc_y = self.ploc_y + dy / curr_smooth
        
        # Ensure we stay within screen bounds (roughly)
        move_x = max(0, min(self.screen_w, self.cloc_x))
        move_y = max(0, min(self.screen_h, self.cloc_y))
        
        # Perform move
        try:
            pyautogui.moveTo(move_x, move_y)
        except Exception:
            pass
            
        self.ploc_x, self.ploc_y = self.cloc_x, self.cloc_y
            
    def left_click(self):
        current_time = time.time()
        if current_time - self.last_left_click_time > self.click_cooldown:
            if not self.is_dragging:
                pyautogui.click()
                self.last_left_click_time = current_time
                return True
        return False
        
    def drag_start(self):
        if not self.is_dragging:
            pyautogui.mouseDown()
            self.is_dragging = True
            print("Drag Started")
            
    def drag_stop(self):
        if self.is_dragging:
            pyautogui.mouseUp()
            self.is_dragging = False
            print("Drag Stopped")
        
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
        
    def open_app(self, app_name):
        current_time = time.time()
        # Use a generic cooldown for app launching
        if current_time - self.last_firefox_time > self.firefox_cooldown:
            try:
                subprocess.Popen([app_name])
                print(f"{app_name.capitalize()} launched!")
                self.last_firefox_time = current_time
                return True
            except Exception as e:
                print(f"Failed to launch {app_name}: {e}")
        return False

    def toggle_media(self):
        current_time = time.time()
        if current_time - self.last_right_click_time > self.click_cooldown:
            pyautogui.press('playpause')
            print("Media Play/Pause")
            self.last_right_click_time = current_time
            return True
        return False

    def open_url(self, url):
        current_time = time.time()
        if current_time - self.last_firefox_time > self.firefox_cooldown:
            webbrowser.open(url)
            print(f"Opening URL: {url}")
            self.last_firefox_time = current_time
            return True
        return False


    def _ydotool_key(self, codes):
        """Execute key sequence using ydotool. codes is a list of [code, state] pairs."""
        cmd = "ydotool key " + " ".join([f"{c}:{s}" for c, s in codes])
        os.system(cmd)

    def system_shortcut(self, keys):
        # keys is a list like ['alt', 'tab']
        if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
            sequence = []
            # Press all
            for k in keys:
                if k in self.key_map: sequence.append([self.key_map[k], 1])
            # Release all (reverse order)
            for k in reversed(keys):
                if k in self.key_map: sequence.append([self.key_map[k], 0])
            self._ydotool_key(sequence)
        else:
            pyautogui.hotkey(*keys)
        print(f"Shortcut triggered: {'+'.join(keys)}")

    def scroll(self, y):
        if self.prev_y_scroll is None:
            self.prev_y_scroll = y
            return
        
        dy = y - self.prev_y_scroll
        if abs(dy) > 5:  # sensitivity threshold
            if dy > 0:
                pyautogui.scroll(-120) # Scroll Down
            else:
                pyautogui.scroll(120)  # Scroll Up
            self.prev_y_scroll = y

    def change_volume(self, y):
        if self.prev_y_volume is None:
            self.prev_y_volume = y
            return
            
        dy = y - self.prev_y_volume
        current_time = time.time()
        
        if abs(dy) > 10 and (current_time - self.last_volume_time > self.volume_cooldown):
            if dy > 0:
                os.system("pactl set-sink-volume @DEFAULT_SINK@ -5%")
            else:
                os.system("pactl set-sink-volume @DEFAULT_SINK@ +5%")
            self.prev_y_volume = y
            self.last_volume_time = current_time

    def change_brightness(self, y):
        if self.prev_y_brightness is None:
            self.prev_y_brightness = y
            return
            
        dy = y - self.prev_y_brightness
        current_time = time.time()
        
        if abs(dy) > 10 and (current_time - self.last_brightness_time > self.brightness_cooldown):
            if dy > 0:
                os.system("brightnessctl set 5%- || xbacklight -dec 5")
            else:
                os.system("brightnessctl set +5% || xbacklight -inc 5")
            self.prev_y_brightness = y
            self.last_brightness_time = current_time

    def window_control(self, action):
        """Action can be 'maximize', 'minimize', or 'close'"""
        if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
            if action == 'maximize':
                self._ydotool_key([[125, 1], [103, 1], [103, 0], [125, 0]]) # Super+Up
            elif action == 'minimize':
                self._ydotool_key([[125, 1], [108, 1], [108, 0], [125, 0]]) # Super+Down
            elif action == 'close':
                self._ydotool_key([[56, 1], [62, 1], [62, 0], [56, 0]]) # Alt+F4 (62 is F4)
        else:
            if action == 'maximize': pyautogui.hotkey('super', 'up')
            elif action == 'minimize': pyautogui.hotkey('super', 'down')
            elif action == 'close': pyautogui.hotkey('alt', 'f4')

    def browser_control(self, action):
        """Action can be 'next_tab', 'prev_tab', or 'back'"""
        if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
            if action == 'next_tab':
                self._ydotool_key([[29, 1], [15, 1], [15, 0], [29, 0]]) # Ctrl+Tab
            elif action == 'prev_tab':
                self._ydotool_key([[29, 1], [42, 1], [15, 1], [15, 0], [42, 0], [29, 0]]) # Ctrl+Shift+Tab
        else:
            if action == 'next_tab': pyautogui.hotkey('ctrl', 'tab')
            elif action == 'prev_tab': pyautogui.hotkey('ctrl', 'shift', 'tab')

    def edit_control(self, action):
        """Action can be 'copy', 'paste', or 'undo'"""
        if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
            if action == 'copy':
                self._ydotool_key([[29, 1], [46, 1], [46, 0], [29, 0]]) # Ctrl+C
            elif action == 'paste':
                self._ydotool_key([[29, 1], [47, 1], [47, 0], [29, 0]]) # Ctrl+V
            elif action == 'undo':
                self._ydotool_key([[29, 1], [44, 1], [44, 0], [29, 0]]) # Ctrl+Z
        else:
            if action == 'copy': pyautogui.hotkey('ctrl', 'c')
            elif action == 'paste': pyautogui.hotkey('ctrl', 'v')
            elif action == 'undo': pyautogui.hotkey('ctrl', 'z')

    def zoom(self, y):
        if self.prev_y_zoom is None:
            self.prev_y_zoom = y
            return
            
        dy = y - self.prev_y_zoom
        if abs(dy) > 15:
            if dy > 0:
                pyautogui.hotkey('ctrl', '-')
            else:
                pyautogui.hotkey('ctrl', '+')
            self.prev_y_zoom = y

    def reset_continuous(self):
        self.prev_y_scroll = None
        self.prev_y_volume = None
        self.prev_y_brightness = None
        self.prev_y_zoom = None
        if self.is_dragging:
            self.drag_stop()
