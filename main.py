"""
Hand Gesture Mouse Controller
==============================
Bitta yoki ikki qo'l bilan ishlaydi.
Komandalar: qo'l harakatsiz turganida va barmoqlar JUDA yaqin tekkizilganda.
Sichqoncha: har doim, qo'l harakatlanayotganda.
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
FRAME_REDUCE  = 110
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

# Harakat tezligi chegarasi (px/kadr) - shu dan katta bo'lsa komanda bloklanadi
VEL_THRESHOLD = 15


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


# ─── HUD ──────────────────────────────────────────────────────────────────────
def draw_hud(img, fps, mode, gesture, ripples):
    h, w = img.shape[:2]
    ov = img.copy()
    cv2.rectangle(ov, (0, 0), (w, 44), (10, 10, 10), -1)
    cv2.addWeighted(ov, 0.65, img, 0.35, 0, img)

    col = (0, 220, 80) if "Dual" in mode else (80, 180, 255)
    cv2.putText(img, f"FPS:{int(fps)}", (8, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(img, mode, (w - 210, 28),
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

    def check(self, key, active):
        if not active:
            self._s.pop(key, None)
            self._d.discard(key)
            return False
        if key not in self._s:
            self._s[key] = time.time()
        elapsed = time.time() - self._s[key]
        if elapsed >= self.hold_sec and key not in self._d:
            self._d.add(key)
            return True
        return False

    def pct(self, key):
        if key not in self._s:
            return 0
        return min(99, int((time.time() - self._s[key]) / self.hold_sec * 100))

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

    # Harakat tezligini hisoblash uchun
    prev_x, prev_y = 0, 0
    velocity       = 0     # px/kadr

    print("✅ Hand Control Pro | Chiqish: 'q'")
    print("   Gestlar: Ko'rs=Harakat | 2barmoq=Scroll | Bosh+Ko'rs=Click")
    print("   Komandalar: Barmoqni tekkizib 1sek ushlang")

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

        # ── Qo'llarni taqsimlash ─────────────────────────────────────
        if len(hands) == 0:
            mode = "No Hands"
            mouse.reset_continuous()
            timer.clear()
            velocity = 0
            prev_x, prev_y = 0, 0

        elif len(hands) == 1:
            nav = cmd = hands[0]['lms']
            mode = f"Universal | {hands[0]['label']}"

        else:
            for h in hands:
                if h['label'] == "Right": nav = h['lms']
                else: cmd = h['lms']
            mode = "Dual | Nav+CMD"
            timer.clear()  # dual modeda hold timer reset

        # ══════════════════════════════════════════════════════════════
        # NAVIGATION (har doim nav bo'lsa)
        # ══════════════════════════════════════════════════════════════
        if nav:
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
        # KOMANDALAR
        # Qo'l harakatsiz bo'lgandagina ishlaydi (velocity < VEL_THRESHOLD)
        # ══════════════════════════════════════════════════════════════
        hand_still = velocity < VEL_THRESHOLD

        if cmd is not None and (time.time() - last_cmd) > CMD_CD:
            lc  = cmd
            now = time.time()

            d48c  = dm(tracker, lc, 4, 8)
            d412c = dm(tracker, lc, 4, 12)
            d416c = dm(tracker, lc, 4, 16)
            d420c = dm(tracker, lc, 4, 20)

            # Qo'l harakatlanayotsa — barcha komandalarni tozala
            if not hand_still:
                timer.clear()
                if gesture == "Move":
                    pass  # Faqat harakatlanish ko'rsatiladi
            else:
                fired = False

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

                if fired:
                    timer.clear()

        elif cmd is None:
            timer.clear()

        # ── HUD va ko'rsatish ─────────────────────────────────────────
        now_t = time.time()
        fps   = 1 / (now_t - pTime) if (now_t - pTime) > 0 else 0
        pTime = now_t

        draw_hud(img, fps, mode, gesture, ripples)
        cv2.imshow(win, img)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("👋 Dastur tugatildi.")


if __name__ == "__main__":
    main()
