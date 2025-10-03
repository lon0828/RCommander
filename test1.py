import cv2
import threading
from flask import Flask, Response
from pynput import keyboard
from picarx import Picarx

# ---------------------- Init ----------------------
px = Picarx()

speed = 50
pan_angle = 0
tilt_angle = 0

# ---------------------- Camera Streaming ----------------------
app = Flask(__name__)
camera = cv2.VideoCapture(0)

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            _, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ---------------------- Keyboard Control ----------------------
def on_press(key):
    global pan_angle, tilt_angle
    try:
        if key.char == 'w':       # Forward
            px.forward(speed)
        elif key.char == 's':     # Backward
            px.backward(speed)
        elif key.char == 'a':     # Left turn
            px.set_dir_servo_angle(-30)
        elif key.char == 'd':     # Right turn
            px.set_dir_servo_angle(30)
        elif key.char == 'o':     # Camera pan left
            pan_angle = min(pan_angle + 5, 35)
            px.set_cam_pan_angle(pan_angle)
        elif key.char == 'l':     # Camera pan right
            pan_angle = max(pan_angle - 5, -35)
            px.set_cam_pan_angle(pan_angle)
        elif key.char == 'k':     # Camera tilt up
            tilt_angle = min(tilt_angle + 5, 35)
            px.set_cam_tilt_angle(tilt_angle)
        elif key.char == ';':     # Camera tilt down
            tilt_angle = max(tilt_angle - 5, -35)
            px.set_cam_tilt_angle(tilt_angle)
    except AttributeError:
        pass

def on_release(key):
    # Stop motors and reset steering when key released
    px.stop()
    px.set_dir_servo_angle(0)

# ---------------------- Threading ----------------------
def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

if __name__ == "__main__":
    # Run Flask in background thread
    threading.Thread(target=run_flask, daemon=True).start()

    # Keyboard listener
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

    # Release camera when done
    camera.release()
    cv2.destroyAllWindows()