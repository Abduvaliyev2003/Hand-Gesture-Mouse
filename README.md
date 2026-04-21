# Hand Gesture Mouse Controller

This project allows you to control your computer mouse using hand gestures over a webcam.

## Features
- Control the mouse cursor with your index finger.
- Left-click by touching your thumb and index finger together.
- Right-click by touching your thumb and middle finger together.
- Smooth mouse movement enabled to prevent jittering.

## Setup Instructions

1. Ensure you have Python installed. It is recommended to use a virtual environment.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Linux only) Depending on your desktop environment, you might need `xlib` extensions or specific screen modules for PyAutoGUI (e.g., `python3-xlib` or similar).

## Running the Application

### 1. (Linux/Wayland/X11 Only) Authorize Display Access
If you encounter `Xlib.error.DisplayConnectionError`, run:
```bash
xhost +local:$(whoami)
```

### 2. Execute the main script
Use the virtual environment's Python to ensure all dependencies are available:
```bash
./venv/bin/python main.py
```

A webcam window will appear. Bring your hand into the frame. Note the tracking points:
- Moves cursor: **Index finger tip**.
- Left Click: Pinched **Index + Thumb**.
- Right Click: Pinched **Middle + Thumb**.

To stop the program, press the `q` key on your keyboard while focusing the video output window.
