import time
import numpy as np
import webbrowser
import subprocess
import os
import pyautogui  # screenshot uchun saqlanadi

from pynput.mouse import Button, Controller as MouseCtrl
from pynput.keyboard import Key, KeyCode, Controller as KeyboardCtrl


class MouseController:
    def __init__(self, screen_w, screen_h, frame_w, frame_h, smoothening=7, frame_reduce=100):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.frame_w = frame_w
        self.frame_h = frame_h
        self.smoothening = smoothening
        self.frame_reduce = frame_reduce

        self.mouse = MouseCtrl()
        self.keyboard = KeyboardCtrl()

        self.ploc_x, self.ploc_y = 0, 0
        self.cloc_x, self.cloc_y = 0, 0

        # Cooldown timers
        self.last_left_click_time = 0
        self.last_right_click_time = 0
        self.last_screenshot_time = 0
        self.last_url_time = 0
        self.last_volume_time = 0
        self.last_workspace_time = 0
        self.last_lock_time = 0
        self.last_app_time = 0
        self.click_cooldown = 0.5
        self.screenshot_cooldown = 2.0
        self.url_cooldown = 3.0
        self.volume_cooldown = 0.15
        self.workspace_cooldown = 1.5
        self.lock_cooldown = 5.0
        self.app_cooldown = 2.0

        # Continuous control state
        self.prev_y_scroll = None
        self.prev_y_volume = None
        self.prev_y_zoom = None
        self.is_dragging = False

        # Screenshot klasörü
        self.screenshot_dir = "screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)

    # ─── MOUSE MOVEMENT ────────────────────────────────────────────────
    def move_mouse(self, x, y):
        """Kamera koordinatlarini ekran koordinatlariga o'girib sichqonchani siljitadi."""
        x3 = np.interp(x, (self.frame_reduce, self.frame_w - self.frame_reduce), (0, self.screen_w))
        y3 = np.interp(y, (self.frame_reduce, self.frame_h - self.frame_reduce), (0, self.screen_h))

        dx = x3 - self.ploc_x
        dy = y3 - self.ploc_y
        dist = (dx ** 2 + dy ** 2) ** 0.5
        curr_smooth = max(2, self.smoothening - dist / 15)

        self.cloc_x = self.ploc_x + dx / curr_smooth
        self.cloc_y = self.ploc_y + dy / curr_smooth

        move_x = max(0, min(self.screen_w - 1, int(self.cloc_x)))
        move_y = max(0, min(self.screen_h - 1, int(self.cloc_y)))

        try:
            self.mouse.position = (move_x, move_y)
        except Exception:
            pass

        self.ploc_x, self.ploc_y = self.cloc_x, self.cloc_y

    # ─── CLICKS ────────────────────────────────────────────────────────
    def left_click(self):
        t = time.time()
        if t - self.last_left_click_time > self.click_cooldown:
            if not self.is_dragging:
                self.mouse.click(Button.left)
                self.last_left_click_time = t
                return True
        return False

    def right_click(self):
        t = time.time()
        if t - self.last_right_click_time > self.click_cooldown:
            self.mouse.click(Button.right)
            self.last_right_click_time = t
            return True
        return False

    def drag_start(self):
        if not self.is_dragging:
            self.mouse.press(Button.left)
            self.is_dragging = True

    def drag_stop(self):
        if self.is_dragging:
            self.mouse.release(Button.left)
            self.is_dragging = False

    # ─── SCROLL ────────────────────────────────────────────────────────
    def scroll(self, y):
        if self.prev_y_scroll is None:
            self.prev_y_scroll = y
            return
        dy = y - self.prev_y_scroll
        if abs(dy) > 6:
            # dy > 0 → qo'l pastga tushdi → sahifa pastga skrollanadi
            # dy < 0 → qo'l yuqoriga ko'tarildi → sahifa yuqoriga skrollanadi
            direction = -1 if dy > 0 else 1
            self.mouse.scroll(0, direction * 5)
            self.prev_y_scroll = y

    # ─── VOLUME ────────────────────────────────────────────────────────
    def change_volume(self, y):
        if self.prev_y_volume is None:
            self.prev_y_volume = y
            return
        dy = y - self.prev_y_volume
        t = time.time()
        if abs(dy) > 10 and (t - self.last_volume_time > self.volume_cooldown):
            cmd = "pactl set-sink-volume @DEFAULT_SINK@ "
            cmd += "-5%" if dy > 0 else "+5%"
            os.system(cmd)
            self.prev_y_volume = y
            self.last_volume_time = t

    # ─── ZOOM ──────────────────────────────────────────────────────────
    def zoom(self, y):
        if self.prev_y_zoom is None:
            self.prev_y_zoom = y
            return
        dy = y - self.prev_y_zoom
        if abs(dy) > 15:
            with self.keyboard.pressed(Key.ctrl):
                self.keyboard.tap(KeyCode.from_char('-') if dy > 0 else KeyCode.from_char('='))
            self.prev_y_zoom = y

    # ─── KEYBOARD SHORTCUTS ────────────────────────────────────────────
    def system_shortcut(self, *keys):
        """Tizim shortcut ko'ngilgichlarini bosadi. Masalan: system_shortcut(Key.alt, Key.tab)"""
        pressed = []
        try:
            for k in keys[:-1]:
                self.keyboard.press(k)
                pressed.append(k)
            self.keyboard.tap(keys[-1])
        finally:
            for k in reversed(pressed):
                self.keyboard.release(k)
        print(f"Shortcut: {keys}")

    def edit_control(self, action):
        """Matn tahrirlash amallari."""
        mapping = {
            'copy':  (Key.ctrl, KeyCode.from_char('c')),
            'paste': (Key.ctrl, KeyCode.from_char('v')),
            'undo':  (Key.ctrl, KeyCode.from_char('z')),
            'redo':  (Key.ctrl, KeyCode.from_char('y')),
        }
        if action in mapping:
            ctrl_key, char_key = mapping[action]
            with self.keyboard.pressed(ctrl_key):
                self.keyboard.tap(char_key)
            print(f"Edit: {action}")

    def browser_control(self, action):
        """Brauzer tab boshqaruvi."""
        if action == 'next_tab':
            with self.keyboard.pressed(Key.ctrl):
                self.keyboard.tap(Key.tab)
        elif action == 'prev_tab':
            with self.keyboard.pressed(Key.ctrl):
                with self.keyboard.pressed(Key.shift):
                    self.keyboard.tap(Key.tab)

    def window_control(self, action):
        """Oyna boshqaruvi — faqat X11 da to'liq ishlaydi."""
        if action == 'minimize':
            with self.keyboard.pressed(Key.super):
                self.keyboard.tap(KeyCode.from_char('d'))
        elif action == 'close':
            with self.keyboard.pressed(Key.alt):
                self.keyboard.tap(Key.f4)

    # ─── APPS & WEB ────────────────────────────────────────────────────
    def open_url(self, url):
        """Brauzerni ochib URL-ni yuklaydi."""
        t = time.time()
        if t - self.last_url_time > self.url_cooldown:
            webbrowser.open(url)
            print(f"Opening: {url}")
            self.last_url_time = t
            return True
        return False

    def take_screenshot(self):
        """Ekranning rasmini oladi va saqlaydi."""
        t = time.time()
        if t - self.last_screenshot_time > self.screenshot_cooldown:
            filename = os.path.join(self.screenshot_dir, f"screenshot_{int(t)}.png")
            try:
                pyautogui.screenshot(filename)
                print(f"Screenshot saved: {filename}")
            except Exception:
                # pyautogui ishlamasa, scrot bilan urinib ko'r
                os.system(f"scrot '{filename}' 2>/dev/null || gnome-screenshot -f '{filename}' 2>/dev/null")
            self.last_screenshot_time = t
            return True
        return False

    # ─── RESET ─────────────────────────────────────────────────────────
    def reset_continuous(self):
        """Uzluksiz boshqaruv holatlarini tiklaydi."""
        self.prev_y_scroll = None
        self.prev_y_volume = None
        self.prev_y_zoom = None
        if self.is_dragging:
            self.drag_stop()

    # ─── WORKSPACE SWITCH ──────────────────────────────────────────────
    def switch_workspace(self, direction):
        """GNOME workspace almashtirish. direction: 'left' yoki 'right'"""
        t = time.time()
        if t - self.last_workspace_time > self.workspace_cooldown:
            if direction == 'left':
                with self.keyboard.pressed(Key.ctrl):
                    with self.keyboard.pressed(Key.alt):
                        self.keyboard.tap(Key.left)
            else:
                with self.keyboard.pressed(Key.ctrl):
                    with self.keyboard.pressed(Key.alt):
                        self.keyboard.tap(Key.right)
            self.last_workspace_time = t
            print(f"🖥️ Workspace: {direction}")
            return True
        return False

    # ─── LOCK SCREEN ───────────────────────────────────────────────────
    def lock_screen(self):
        """Ekranni qulflash."""
        t = time.time()
        if t - self.last_lock_time > self.lock_cooldown:
            subprocess.Popen(
                ["loginctl", "lock-session"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self.last_lock_time = t
            print("🔒 Screen locked!")
            return True
        return False

    # ─── APP LAUNCHER ──────────────────────────────────────────────────
    def open_app(self, app_name):
        """Ilovani ochadi."""
        t = time.time()
        if t - self.last_app_time > self.app_cooldown:
            apps = {
                'terminal':  ['gnome-terminal'],
                'files':     ['nautilus'],
                'browser':   ['xdg-open', 'https://google.com'],
                'vscode':    ['code'],
                'settings':  ['gnome-control-center'],
                'telegram':  ['telegram-desktop'],
            }
            cmd = apps.get(app_name)
            if cmd:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.last_app_time = t
                print(f"🚀 Opened: {app_name}")
                return True
        return False

    def launch_by_finger_count(self, count):
        """Barmoq soniga qarab ilova ochadi: 1=Terminal 2=Files 3=Browser 4=VSCode 5=Settings"""
        mapping = {1: 'terminal', 2: 'files', 3: 'browser', 4: 'vscode', 5: 'settings'}
        app = mapping.get(count)
        if app:
            return self.open_app(app)
        return False

