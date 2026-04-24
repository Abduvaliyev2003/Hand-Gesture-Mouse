"""
Hand Gesture Mouse Controller — ULTRA Edition
================================================
Bitta yoki ikki qo'l bilan ishlaydi.

NAVIGATION gestlar:
  Ko'rsatkich = Harakat | Bosh+Ko'rs = Click/Drag
  2 barmoq = Scroll | 3 barmoq = Volume | Zoom

KOMANDALAR (1s ushlab turish):
  Bosh+Ko'rs = Copy | Bosh+O'rta = Instagram
  Bosh+Nomsiz = YouTube | Bosh+Jim = Screenshot

CRAZY GESTLAR:
  🖐️ Kaft surish chapga/o'ngga = Workspace switch
  🤟 Rock (ko'rs+jimjiloq) 1s = Telegram
  👆 Barmoq soni 1-5 ushlab = App launcher
  ✌️ Peace 1.5s = Air Drawing rejimi
  ✋ Qo'l silkitish 3x = Lock screen
"""

import os
os.environ["NO_AT_BRIDGE"] = "1"
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.*=false"
os.environ["QT_QPA_PLATFORM"] = "xcb"

import cv2
import sys
import time
import numpy as np
import pyautogui

from hand_tracker import HandTracker
from mouse_controller import MouseController

# ─── Sozlamalar ───────────────────────────────────────────────────────────────
W_CAM, H_CAM  = 640, 480
FRAME_REDUCE  = 15
SMOOTHENING   = 6

# Navigation gestlari (px)
G_CLICK       = 36
G_RIGHTCLICK  = 25
G_SCROLL      = 25
G_VOLUME      = 28

# Komanda gestlari
G_CMD         = 22    # Juda qattiq chegarasi (ataylab tekkizish kerak)
CMD_HOLD      = 1.0   # Ushlab turish vaqti (sek)
CMD_CD        = 1.5   # Komandalar orasidagi kutish (sek)

# Drag
DRAG_HOLD     = 0.35

# Harakat tezligi chegarasi (px/kadr)
VEL_THRESHOLD = 15


# ─── Barmoqlar yuqorimi? ─────────────────────────────────────────────────────
def fingers_up(lms, label="Right", tracker=None):
    """Qaysi barmoqlar ko'tarilgan: [thumb, index, middle, ring, pinky]"""
    fup = []
    # Bosh barmoq — x koordinataga emas, 17-nuqtaga masofasiga qaraymiz (aniqroq)
    if tracker:
        d4_17 = tracker.get_distance(lms[4], lms[17], img=None, draw=False)[0]
        d3_17 = tracker.get_distance(lms[3], lms[17], img=None, draw=False)[0]
        # Agar uch qismi (4) bo'g'imdan (3) ko'ra uzoqroq bo'lsa -> yoniq (UP)
        fup.append(d4_17 > d3_17)
    else:
        if label == "Right":
            fup.append(lms[4][1] < lms[3][1])
        else:
            fup.append(lms[4][1] > lms[3][1])
            
    # Qolgan 4 ta barmoq — tip.y < pip.y = yuqorida
    for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
        fup.append(lms[tip][2] < lms[pip][2])
    return fup


# ─── Ripple ──────────────────────────────────────────────────────────────────
class Ripple:
    def __init__(self, x, y, color=(0, 255, 100)):
        self.x, self.y, self.color = x, y, color
        self.r, self.alpha = 8, 255

    def update(self):
        self.r    += 4
        self.alpha -= 18
        return self.r < 55 and self.alpha > 0

    def draw(self, img):
        ov = img.copy()
        cv2.circle(ov, (self.x, self.y), self.r, self.color, 2)
        cv2.addWeighted(ov, self.alpha / 255, img, 1 - self.alpha / 255, 0, img)


# ─── Swipe Detector ──────────────────────────────────────────────────────────
class SwipeDetector:
    """Kaftni chapga/o'ngga surish — workspace switch"""
    def __init__(self, min_swipe_px=130, time_window=0.45):
        self.min_swipe     = min_swipe_px
        self.time_window   = time_window
        self.history       = []      # [(x, t), ...]
        self.last_swipe    = 0
        self.cooldown      = 1.5

    def update(self, x, palm_open):
        now = time.time()
        if not palm_open:
            self.history.clear()
            return None
        self.history.append((x, now))
        self.history = [(px, pt) for px, pt in self.history if now - pt < self.time_window]
        if len(self.history) < 5 or now - self.last_swipe < self.cooldown:
            return None
        dx = self.history[-1][0] - self.history[0][0]
        if abs(dx) > self.min_swipe:
            self.last_swipe = now
            self.history.clear()
            return "left" if dx > 0 else "right"   # mirrored camera
        return None

    def reset(self):
        self.history.clear()


# ─── Wave Detector ────────────────────────────────────────────────────────────
class WaveDetector:
    """Qo'lni tez silkitish (3x) = lock screen"""
    def __init__(self, needed=4, time_window=1.8, min_move=30):
        self.needed      = needed
        self.time_window = time_window
        self.min_move    = min_move
        self.positions   = []
        self.last_wave   = 0
        self.cooldown    = 5.0

    def update(self, x, palm_open):
        now = time.time()
        if not palm_open or now - self.last_wave < self.cooldown:
            self.positions.clear()
            return False
        self.positions.append((x, now))
        self.positions = [(px, pt) for px, pt in self.positions if now - pt < self.time_window]
        if len(self.positions) < 8:
            return False
        changes, prev_dir = 0, 0
        for i in range(1, len(self.positions)):
            dx = self.positions[i][0] - self.positions[i - 1][0]
            if abs(dx) < 5:
                continue
            cur = 1 if dx > 0 else -1
            if prev_dir != 0 and cur != prev_dir:
                changes += 1
            prev_dir = cur
        if changes >= self.needed:
            self.last_wave = now
            self.positions.clear()
            return True
        return False

    def reset(self):
        self.positions.clear()


# ─── Air Canvas ───────────────────────────────────────────────────────────────
class AirCanvas:
    """Havoda chizish uchun canvas"""
    COLORS = [
        (0, 255, 0),      # Yashil
        (255, 100, 0),    # Ko'k
        (0, 0, 255),      # Qizil
        (0, 255, 255),    # Sariq
        (255, 0, 255),    # Pushti
        (255, 255, 255),  # Oq
    ]
    COLOR_NAMES = ["Green", "Blue", "Red", "Yellow", "Pink", "White"]

    def __init__(self, w, h, sw, sh):
        self.w, self.h = w, h
        self.sw, self.sh = sw, sh
        self.canvas    = np.zeros((sh, sw, 3), dtype=np.uint8)
        self.active    = False
        self.prev_pt   = None
        self.color_idx = 0
        self.color     = self.COLORS[0]
        self.thickness = 3
        self.save_dir  = "drawings"
        self.bg_img    = None
        os.makedirs(self.save_dir, exist_ok=True)

    def toggle(self):
        if self.active:
            path = self.save()
            self.active = False
            self.prev_pt = None
            self.bg_img = None
            cv2.destroyWindow("Air Drawing Screen")
            return False, path
        else:
            self.canvas = np.zeros((self.sh, self.sw, 3), dtype=np.uint8)
            self.active = True
            self.prev_pt = None
            print("🎨 Air Drawing: ON")
            
            # Ekranni rasmga olib orqa fon qilish
            bg = pyautogui.screenshot()
            self.bg_img = cv2.cvtColor(np.array(bg), cv2.COLOR_RGB2BGR)
            
            # Fullscreen oyna yaratish
            cv2.namedWindow("Air Drawing Screen", cv2.WINDOW_NORMAL)
            cv2.setWindowProperty("Air Drawing Screen", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            return True, None

    def draw_line(self, x, y):
        if self.prev_pt is not None:
            cv2.line(self.canvas, self.prev_pt, (x, y), self.color, self.thickness)
        self.prev_pt = (x, y)

    def lift(self):
        self.prev_pt = None

    def next_color(self):
        self.color_idx = (self.color_idx + 1) % len(self.COLORS)
        self.color = self.COLORS[self.color_idx]
        self.prev_pt = None
        print(f"🎨 Color: {self.COLOR_NAMES[self.color_idx]}")

    def clear(self):
        self.canvas = np.zeros((self.sh, self.sw, 3), dtype=np.uint8)
        self.prev_pt = None
        print("🧹 Canvas cleared")

    def save(self):
        fname = os.path.join(self.save_dir, f"drawing_{int(time.time())}.png")
        cv2.imwrite(fname, self.canvas)
        print(f"💾 Drawing saved: {fname}")
        return fname

    def overlay(self, img):
        if not self.active:
            return img
        # Kichik oyna (kamera) uchun canvasni qisqartirib ko'rsatamiz
        small_canvas = cv2.resize(self.canvas, (self.w, self.h))
        gray = cv2.cvtColor(small_canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
        mask_inv = cv2.bitwise_not(mask)
        bg = cv2.bitwise_and(img, img, mask=mask_inv)
        fg = cv2.bitwise_and(small_canvas, small_canvas, mask=mask)
        return cv2.add(bg, fg)

    def draw_palette(self, img):
        """Kamera oynasiga kichik palitra chizish"""
        if not self.active:
            return
        x_start = 10
        for i, c in enumerate(self.COLORS):
            cx = x_start + i * 28
            cy = 70
            r = 10 if i != self.color_idx else 13
            cv2.circle(img, (cx, cy), r, c, -1)
            if i == self.color_idx:
                cv2.circle(img, (cx, cy), r + 3, (255, 255, 255), 2)

    def update_screen_window(self, mx=None, my=None):
        if not self.active or self.bg_img is None:
            return
        
        gray = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
        mask_inv = cv2.bitwise_not(mask)
        
        bg = cv2.bitwise_and(self.bg_img, self.bg_img, mask=mask_inv)
        fg = cv2.bitwise_and(self.canvas, self.canvas, mask=mask)
        res = cv2.add(bg, fg)
        
        # Ekrandagi katta palitra
        x_start = 50
        for i, c in enumerate(self.COLORS):
            cx = x_start + i * 50
            cy = 50
            r = 15 if i != self.color_idx else 20
            cv2.circle(res, (cx, cy), r, c, -1)
            if i == self.color_idx:
                cv2.circle(res, (cx, cy), r + 3, (255, 255, 255), 3)

        # Kursor chizish
        if mx is not None and my is not None:
            cv2.circle(res, (mx, my), 6, self.color, -1)
            cv2.circle(res, (mx, my), 10, self.color, 2)
                
        cv2.imshow("Air Drawing Screen", res)


# ─── HUD ──────────────────────────────────────────────────────────────────────
def draw_hud(img, fps, mode, gesture, ripples, drawing=False):
    h, w = img.shape[:2]
    ov = img.copy()
    cv2.rectangle(ov, (0, 0), (w, 44), (10, 10, 10), -1)
    cv2.addWeighted(ov, 0.65, img, 0.35, 0, img)

    col = (0, 220, 80) if "Dual" in mode else (80, 180, 255)
    if drawing:
        col = (0, 200, 255)
        mode = "🎨 DRAWING MODE"

    cv2.putText(img, f"FPS:{int(fps)}", (8, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(img, mode, (w - 250, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, col, 1, cv2.LINE_AA)

    if gesture:
        ov2 = img.copy()
        cv2.rectangle(ov2, (0, h - 36), (w, h), (10, 10, 10), -1)
        cv2.addWeighted(ov2, 0.65, img, 0.35, 0, img)
        cv2.putText(img, gesture, (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 210, 255), 2, cv2.LINE_AA)

    for r in ripples[:]:
        if not r.update(): ripples.remove(r)
        else: r.draw(img)


# ─── Masofa ───────────────────────────────────────────────────────────────────
def dm(tracker, lms, a, b):
    return tracker.get_distance(lms[a], lms[b], img=None, draw=False)[0]


# ─── Hold Timer ───────────────────────────────────────────────────────────────
class HoldTimer:
    def __init__(self, hold_sec=CMD_HOLD):
        self.hold_sec = hold_sec
        self._s = {}    # timers
        self._d = set() # done (bir marta ishga tushgan)

    def check(self, key, active, custom_hold=None):
        hs = custom_hold if custom_hold else self.hold_sec
        if not active:
            self._s.pop(key, None)
            self._d.discard(key)
            return False
        if key not in self._s:
            self._s[key] = time.time()
        elapsed = time.time() - self._s[key]
        if elapsed >= hs and key not in self._d:
            self._d.add(key)
            return True
        return False

    def pct(self, key, custom_hold=None):
        hs = custom_hold if custom_hold else self.hold_sec
        if key not in self._s:
            return 0
        return min(99, int((time.time() - self._s[key]) / hs * 100))

    def clear(self):
        self._s.clear()
        self._d.clear()


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    win = "Hand Control Pro"
    cv2.namedWindow(win, cv2.WINDOW_GUI_NORMAL)
    cv2.resizeWindow(win, W_CAM, H_CAM)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W_CAM)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H_CAM)
    cap.set(cv2.CAP_PROP_FPS, 30)
    if not cap.isOpened():
        print("❌ Kamera topilmadi!")
        sys.exit(1)

    tracker  = HandTracker(detection_con=0.75)
    sw, sh   = pyautogui.size()
    mouse    = MouseController(sw, sh, W_CAM, H_CAM,
                               smoothening=SMOOTHENING,
                               frame_reduce=FRAME_REDUCE)
    timer    = HoldTimer(CMD_HOLD)
    pTime    = 0
    pinch_t  = None
    last_cmd = 0
    ripples  = []
    mode     = "No Hands"

    # Harakat tezligi
    prev_x, prev_y = 0, 0
    velocity       = 0

    # ── Yangi detektorlar ──
    swipe   = SwipeDetector()
    wave    = WaveDetector()
    canvas  = AirCanvas(W_CAM, H_CAM, sw, sh)

    APP_NAMES = {1: 'Terminal', 2: 'Files', 3: 'Browser', 4: 'VSCode', 5: 'Settings'}

    print("✅ Hand Control Pro — ULTRA Edition | Chiqish: 'q'")
    print("   Gestlar: Ko'rs=Harakat | 2barmoq=Scroll | Bosh+Ko'rs=Click")
    print("   Komandalar: Barmoqni tekkizib 1sek ushlang")
    print("   CRAZY: Swipe=Workspace | Rock=Telegram | Fingers=App")
    print("          Peace=Drawing | Wave=Lock")

    while True:
        ok, img = cap.read()
        if not ok:
            continue

        img   = cv2.flip(img, 1)
        img   = tracker.find_hands(img)
        hands = tracker.find_all_hands(img)

        gesture = None
        nav     = None
        cmd     = None
        nav_label = "Right"
        cmd_label = "Left"

        # ── Qo'llarni taqsimlash ─────────────────────────────────────
        if len(hands) == 0:
            mode = "No Hands"
            mouse.reset_continuous()
            timer.clear()
            velocity = 0
            prev_x, prev_y = 0, 0
            swipe.reset()
            wave.reset()

        elif len(hands) == 1:
            nav = cmd = hands[0]['lms']
            nav_label = cmd_label = hands[0]['label']
            mode = f"Universal | {hands[0]['label']}"

        else:
            for h in hands:
                if h['label'] == "Right":
                    nav = h['lms']
                    nav_label = "Right"
                else:
                    cmd = h['lms']
                    cmd_label = "Left"
            mode = "Dual | Nav+CMD"
            timer.clear()

        # ══════════════════════════════════════════════════════════════
        # PALM SWIPE & WAVE (har qanday ko'rinadigan qo'lda)
        # ══════════════════════════════════════════════════════════════
        any_lms = nav if nav else cmd
        any_label = nav_label if nav else cmd_label
        if any_lms and not canvas.active:
            fup_any = fingers_up(any_lms, any_label, tracker)
            palm_open = all(fup_any)
            palm_x = any_lms[9][1]

            swipe_dir = swipe.update(palm_x, palm_open)
            if swipe_dir:
                mouse.switch_workspace(swipe_dir)
                gesture = f"✅ 🖥️ Workspace {swipe_dir.upper()}"
                ripples.append(Ripple(palm_x, any_lms[9][2], (255, 200, 0)))

            if wave.update(palm_x, palm_open):
                mouse.lock_screen()
                gesture = "✅ 🔒 SCREEN LOCKED"
                ripples.append(Ripple(palm_x, any_lms[9][2], (0, 0, 255)))
        else:
            swipe.reset()
            wave.reset()

        # ══════════════════════════════════════════════════════════════
        # AIR DRAWING MODE (nav qo'l bilan)
        # ══════════════════════════════════════════════════════════════
        screen_mx, screen_my = None, None
        
        if canvas.active and nav:
            fup = fingers_up(nav, nav_label, tracker)
            x1, y1 = nav[8][1], nav[8][2]
            
            # Chizish uchun kamera koordinatasini ekranga o'tkazish
            mouse.move_mouse(x1, y1)
            sx, sy = int(mouse.cloc_x), int(mouse.cloc_y)
            screen_mx, screen_my = sx, sy

            d812_nav = dm(tracker, nav, 8, 12)

            # Faqat index up → chizish
            if fup[1] and not fup[2] and not fup[3] and not fup[4]:
                canvas.draw_line(sx, sy)
                gesture = "🎨 Drawing..."
                timer.check('next_color', False)
                timer.check('clear_draw', False)
                timer.check('drawing_off', False)

            # Faqat thumb up → next color
            elif fup[0] and not fup[1] and not fup[2] and not fup[3] and not fup[4]:
                if timer.check('next_color', True, 0.8):
                    canvas.next_color()
                gesture = f"🎨 Color: {canvas.COLOR_NAMES[canvas.color_idx]}"
                canvas.lift()
                timer.check('clear_draw', False)
                timer.check('drawing_off', False)

            # Barcha barmoqlar yuqori → clear
            elif all(fup):
                if timer.check('clear_draw', True, 1.5):
                    canvas.clear()
                    gesture = "🧹 Cleared!"
                else:
                    gesture = f"🧹 Clear {timer.pct('clear_draw', 1.5)}%"
                canvas.lift()
                timer.check('next_color', False)
                timer.check('drawing_off', False)

            # Peace sign → toggle off
            elif not fup[0] and fup[1] and fup[2] and not fup[3] and not fup[4] and d812_nav > 40:
                if timer.check('drawing_off', True, 1.5):
                    active, path = canvas.toggle()
                    gesture = "✅ 💾 Saved!"
                else:
                    gesture = f"💾 Saving {timer.pct('drawing_off', 1.5)}%"
                canvas.lift()
                timer.check('clear_draw', False)
                timer.check('next_color', False)

            # Mushtum → pen lift
            else:
                canvas.lift()
                timer.check('clear_draw', False)
                timer.check('next_color', False)
                timer.check('drawing_off', False)

        # ══════════════════════════════════════════════════════════════
        # NAVIGATION (drawing mode bo'lmagandagina)
        # ══════════════════════════════════════════════════════════════
        elif nav:
            lms = nav
            x1, y1 = lms[8][1], lms[8][2]

            # Tezlikni hisoblash
            velocity = ((x1 - prev_x)**2 + (y1 - prev_y)**2) ** 0.5
            prev_x, prev_y = x1, y1

            d48   = dm(tracker, lms, 4, 8)
            d812  = dm(tracker, lms, 8, 12)
            d1216 = dm(tracker, lms, 12, 16)
            d1620 = dm(tracker, lms, 16, 20)
            d820  = dm(tracker, lms, 8, 20)
            now   = time.time()

            # 1. O'ng tugma
            if d812 < G_RIGHTCLICK and d1216 < G_RIGHTCLICK and d48 > 55:
                gesture = "Right Click"
                if mouse.right_click():
                    ripples.append(Ripple(x1, y1, (80, 80, 255)))

            # 2. Skroll
            elif d812 < G_SCROLL and d1216 > 48:
                gesture = "Scroll"
                mouse.scroll(y1)

            # 3. Ovoz
            elif d1216 < G_VOLUME and d1620 < G_VOLUME:
                gesture = "Volume"
                mouse.change_volume(lms[12][2])

            # 4. Zoom
            elif d820 < 42 and d812 > 48:
                gesture = "Zoom"
                mouse.zoom(y1)

            # 5. Harakat / Click / Drag
            else:
                if d48 < G_CLICK:
                    if pinch_t is None:
                        pinch_t = now
                    if now - pinch_t > DRAG_HOLD:
                        mouse.drag_start()
                        gesture = "Drag"
                else:
                    if pinch_t is not None:
                        if now - pinch_t <= DRAG_HOLD:
                            if mouse.left_click():
                                ripples.append(Ripple(x1, y1))
                        mouse.drag_stop()
                        pinch_t = None
                    gesture = "Move"
                mouse.move_mouse(x1, y1)

        # ══════════════════════════════════════════════════════════════
        # KOMANDALAR (drawing mode bo'lmagandagina)
        # ══════════════════════════════════════════════════════════════
        hand_still = velocity < VEL_THRESHOLD

        if not canvas.active and cmd is not None and (time.time() - last_cmd) > CMD_CD:
            lc  = cmd
            now = time.time()

            d48c  = dm(tracker, lc, 4, 8)
            d412c = dm(tracker, lc, 4, 12)
            d416c = dm(tracker, lc, 4, 16)
            d420c = dm(tracker, lc, 4, 20)
            d812c = dm(tracker, lc, 8, 12)

            fup_cmd = fingers_up(lc, cmd_label, tracker)

            # Qo'l harakatlanayotsa — barcha komandalarni tozala
            if not hand_still:
                timer.clear()
                if gesture == "Move":
                    pass
            else:
                fired = False

                # ── Mavjud komandalar ──────────────────────────────

                # Bosh + Ko'rsatkich → Copy
                if not fired and d48c < G_CMD:
                    if timer.check('copy', True):
                        mouse.edit_control('copy')
                        gesture = "✅ Copy"
                        last_cmd, fired = now, True
                    else:
                        gesture = f"Copy {timer.pct('copy')}%"
                else:
                    timer.check('copy', False)

                # Bosh + O'rta → Instagram
                if not fired and d412c < G_CMD and d48c >= G_CMD:
                    if timer.check('instagram', True):
                        mouse.open_url("https://www.instagram.com")
                        gesture = "✅ Instagram"
                        last_cmd, fired = now, True
                    else:
                        gesture = f"Instagram {timer.pct('instagram')}%"
                else:
                    timer.check('instagram', False)

                # Bosh + Nomsiz → YouTube
                if not fired and d416c < G_CMD and d412c >= G_CMD and d48c >= G_CMD:
                    if timer.check('youtube', True):
                        mouse.open_url("https://www.youtube.com")
                        gesture = "✅ YouTube"
                        last_cmd, fired = now, True
                    else:
                        gesture = f"YouTube {timer.pct('youtube')}%"
                else:
                    timer.check('youtube', False)

                # Bosh + Jimjiloq → Screenshot
                if not fired and d420c < G_CMD and d416c >= G_CMD and d412c >= G_CMD and d48c >= G_CMD:
                    if timer.check('screenshot', True):
                        mouse.take_screenshot()
                        gesture = "✅ Screenshot"
                        last_cmd, fired = now, True
                    else:
                        gesture = f"Screenshot {timer.pct('screenshot')}%"
                else:
                    timer.check('screenshot', False)

                # ── CRAZY KOMANDALAR ───────────────────────────────

                # ✌️ Peace sign → Air Drawing toggle (1.5s)
                is_peace = (not fup_cmd[0] and fup_cmd[1] and fup_cmd[2]
                            and not fup_cmd[3] and not fup_cmd[4] and d812c > 40)
                if not fired and is_peace and d48c >= G_CMD:
                    if timer.check('drawing', True, 1.5):
                        active, path = canvas.toggle()
                        if active:
                            gesture = "✅ 🎨 DRAWING ON"
                        else:
                            gesture = f"✅ 💾 Saved!"
                        last_cmd, fired = now, True
                    else:
                        gesture = f"🎨 Drawing {timer.pct('drawing', 1.5)}%"
                else:
                    timer.check('drawing', False)

                # 🤟 Rock gesture → Telegram (1.5s)
                is_rock = (not fup_cmd[0] and fup_cmd[1] and not fup_cmd[2]
                           and not fup_cmd[3] and fup_cmd[4])
                if not fired and is_rock and d48c >= G_CMD:
                    if timer.check('rock', True, 1.5):
                        mouse.open_app('telegram')
                        gesture = "✅ 🤟 Telegram"
                        last_cmd, fired = now, True
                    else:
                        gesture = f"🤟 Telegram {timer.pct('rock', 1.5)}%"
                else:
                    timer.check('rock', False)

                # 👆 Finger Counter → App Launcher (2.0s)
                no_thumb_touch = (d48c >= G_CMD and d412c >= G_CMD
                                  and d416c >= G_CMD and d420c >= G_CMD)
                
                app_idx = 0
                if no_thumb_touch and not is_rock and not is_peace:
                    if not fup_cmd[0] and fup_cmd[1] and not fup_cmd[2] and not fup_cmd[3] and not fup_cmd[4]:
                        app_idx = 1
                    elif not fup_cmd[0] and fup_cmd[1] and fup_cmd[2] and not fup_cmd[3] and not fup_cmd[4] and d812c <= 40:
                        app_idx = 2
                    elif not fup_cmd[0] and fup_cmd[1] and fup_cmd[2] and fup_cmd[3] and not fup_cmd[4]:
                        app_idx = 3
                    elif not fup_cmd[0] and fup_cmd[1] and fup_cmd[2] and fup_cmd[3] and fup_cmd[4]:
                        app_idx = 4
                    elif fup_cmd[0] and fup_cmd[1] and fup_cmd[2] and fup_cmd[3] and fup_cmd[4]:
                        app_idx = 5
                
                if not fired and app_idx > 0:
                    key = f'app_{app_idx}'
                    if timer.check(key, True, 2.5):
                        mouse.launch_by_finger_count(app_idx)
                        gesture = f"✅ 🚀 {APP_NAMES.get(app_idx)}"
                        last_cmd, fired = now, True
                    else:
                        gesture = f"👆 {APP_NAMES.get(app_idx, '?')} {timer.pct(key, 2.5)}%"
                    
                    for i in range(1, 6):
                        if i != app_idx:
                            timer.check(f'app_{i}', False)
                else:
                    for i in range(1, 6):
                        timer.check(f'app_{i}', False)

                if fired:
                    timer.clear()

        elif cmd is None:
            timer.clear()

        # ── Canvas overlay ────────────────────────────────────────────
        img = canvas.overlay(img)
        canvas.draw_palette(img)
        canvas.update_screen_window(screen_mx, screen_my)

        # ── HUD va ko'rsatish ─────────────────────────────────────────
        now_t = time.time()
        fps   = 1 / (now_t - pTime) if (now_t - pTime) > 0 else 0
        pTime = now_t

        draw_hud(img, fps, mode, gesture, ripples, drawing=canvas.active)
        cv2.imshow(win, img)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("👋 Dastur tugatildi.")


if __name__ == "__main__":
    main()
