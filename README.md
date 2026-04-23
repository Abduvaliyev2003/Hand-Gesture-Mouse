# 🖐️ Hand Gesture Mouse Controller

Kamera orqali qo'l harakatlari bilan kompyuterni boshqarish tizimi. MediaPipe va Python yordamida qurilgan.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Linux%20(Wayland%20%7C%20X11)-orange)](https://ubuntu.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📋 Talablar

| Dastur/Kutubxona | Versiya |
|---|---|
| Python | 3.10+ |
| OpenCV | 4.x |
| MediaPipe | 0.10+ |
| pynput | 1.8+ |
| PyAutoGUI | 0.9+ (screenshot uchun) |
| NumPy | 1.x |

**Qurilma:** Istalgan USB yoki ichki veb-kamera

---

## 🚀 O'rnatish

```bash
# 1. Repozitoriyani klonlash
git clone https://github.com/Abduvaliyev2003/Hand-Gesture-Mouse.git
cd Hand-Gesture-Mouse

# 2. Virtual muhit yaratish
python3 -m venv venv
source venv/bin/activate

# 3. Kutubxonalarni o'rnatish
pip install -r requirements.txt

# 4. Dasturni ishga tushirish
python main.py
```

---

## 🎮 Gestlar Qo'llanmasi

> **Muhim:** Qo'lni kamera oldida, 40–70 sm masofada, yaxshi yoritilgan joyda ushlab turing.

---

### ✋ O'ng Qo'l — Sichqoncha Boshqaruvi

| Gest | Tasvir | Harakat |
|------|--------|---------|
| Ko'rsatkich barmoq — yuqoriga | ☝️ | **Sichqoncha harakati** |
| Bosh + Ko'rsatkich — yaqin | 🤏 | **Chap tugma (Click)** |
| Bosh + Ko'rsatkich — uzoq ushlab | 🤏⏳ | **Sudrab ko'chirish (Drag)** |
| Ko'rsatkich + O'rta yaqin | ✌️ | **Skroll (yuqori/pastga)** |
| Ko'rsatkich + O'rta + Nomsiz yaqin | 🤟 | **O'ng tugma (Right Click)** |
| Ko'rsatkich + Jimjiloq yaqin | 🤙 | **Zoom (kattalashtirish/kichraytirish)** |
| O'rta + Nomsiz + Jimjiloq yaqin | 🖖 | **Ovozni boshqarish** |

---

### 🤚 Chap Qo'l — Tizim Komandalari

| Gest | Tasvir | Harakat |
|------|--------|---------|
| Bosh + Ko'rsatkich yaqin | 🤌 | **Nusxa olish (Copy)** |
| Bosh + O'rta barmoq yaqin | 🤌 | **Instagram ochish** |
| Bosh + Nomsiz barmoq yaqin | 🤌 | **YouTube ochish** |
| Bosh + Jimjiloq yaqin | 🤌 | **Ekran rasmi (Screenshot)** |

---

### ☝️ Bitta Qo'l Rejimi (Universal)

Agar faqat **bitta qo'l** ko'rinsa, u avtomatik ravishda ham sichqoncha, ham komandalar uchun ishlatiladi.

---

## 🖥️ Tizim Moslik Jadvali

| Muhit | Sichqoncha | Shortcutlar | Skroll | URL ochish |
|-------|-----------|------------|--------|-----------|
| **X11 (Xorg)** | ✅ | ✅ | ✅ | ✅ |
| **Wayland** | ✅ | ⚠️ Cheklangan | ✅ | ✅ |

> **Wayland foydalanuvchilari uchun:** Alt+Tab va boshqa tizim shortcutlari to'liq ishlamasligi mumkin. To'liq funksionallik uchun Login ekranida **"GNOME on Xorg"** ni tanlang.

---

## ⚙️ Sozlamalar (`main.py`)

```python
# Kamera o'lchami
W_CAM, H_CAM = 640, 480

# Sichqoncha harakat hududi (katta = sichqoncha yurishiga ko'proq joy)
FRAME_REDUCE = 120

# Silliqlash (katta = sekinroq, lekin tezroq)
SMOOTHENING = 7

# Klik uchun barmoqlar orasidagi masofa (katta = osonroq bosiladi)
CLICK_DIST = 38
```

---

## 📁 Loyiha Tuzilishi

```
Hand-Gesture-Mouse/
│
├── main.py              # Asosiy dastur (gestlar, kamera, HUD)
├── mouse_controller.py  # Sichqoncha va klaviatura boshqaruvi
├── hand_tracker.py      # MediaPipe qo'l aniqlash moduli
├── hand_landmarker.task # MediaPipe modeli fayli
├── requirements.txt     # Python kutubxonalari ro'yxati
├── screenshots/         # Screenshot-lar saqlanadigan papka
└── README.md            # Ushbu fayl
```

---

## 🔧 Muammolar va Yechimlar (FAQ)

**❓ Sichqoncha harakatlanmayapti**
- Wayland muhitida ekanligingizni tekshiring: `echo $XDG_SESSION_TYPE`
- Agar `wayland` chiqsa, `pynput` to'g'ri o'rnatilganini tekshiring: `pip show pynput`

**❓ Kamera ochilmayapti**
- Kamera ruxsatini tekshiring: `ls /dev/video*`
- Kamera raqamini o'zgartiring: `main.py` da `cv2.VideoCapture(0)` → `(1)` ga o'zgartiring

**❓ Qo'l aniqlanmayapti**
- Yoritishni yaxshilang
- Qo'lingizni kamera oldida 40–70 sm masofada tuting
- Qo'l fonidan (devor, parda) ajralib turishi kerak

**❓ Screenshot ishlamayapti**
- `scrot` ni o'rnating: `sudo apt install scrot`
- Yoki `gnome-screenshot`: `sudo apt install gnome-screenshot`

**❓ FPS juda past (5 dan kam)**
- `detection_con` ni kamaytiring: `HandTracker(detection_con=0.65)`
- Boshqa ilovalarni yoping

---

## 🛠️ Texnologiyalar

- **[MediaPipe](https://mediapipe.dev/)** — Real-vaqt qo'l aniqlash
- **[OpenCV](https://opencv.org/)** — Kamera va video boshqaruvi
- **[pynput](https://pynput.readthedocs.io/)** — Sichqoncha/Klaviatura boshqaruvi (Wayland/X11)
- **[PyAutoGUI](https://pyautogui.readthedocs.io/)** — Screenshot olish

---

## 📜 Litsenziya

MIT License — bepul foydalanish, o'zgartirish va tarqatish mumkin.

---

*Muallif: Abduvaliyev | 2024*
