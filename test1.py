import cv2
import threading
from flask import Flask, Response
from pynput import keyboard
from time import sleep
from sunfounder_servo import Servo  # Example module (replace with actual SunFounder servo lib)
from sunfounder_motor import Motor  # Example module (replace with actual SunFounder motor lib)

# ---------------------- Motor & Servo Setup ----------------------
left_motor = Motor(0)    # Replace 0 with actual channel
right_motor = Motor(1)   # Replace 1 with actual channel

pan_servo = Servo(2)     # Replace with actual servo channel
tilt_servo = Servo(3)

pan_angle = 90
tilt_angle = 90
pan_servo.write(pan_angle)
tilt_servo.write(tilt_angle)

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
            left_motor.forward(50)
            right_motor.forward(50)
        elif key.char == 's':     # Backward
            left_motor.backward(50)
            right_motor.backward(50)
        elif key.char == 'a':     # Left
            left_motor.backward(40)
            right_motor.forward(40)
        elif key.char == 'd':     # Right
            left_motor.forward(40)
            right_motor.backward(40)
        elif key.char == 'o':     # Pan left
            pan_angle = min(pan_angle + 5, 180)
            pan_servo.write(pan_angle)
        elif key.char == 'l':     # Pan right
            pan_angle = max(pan_angle - 5, 0)
            pan_servo.write(pan_angle)
        elif key.char == 'k':     # Tilt up
            tilt_angle = min(tilt_angle + 5, 180)
            tilt_servo.write(tilt_angle)
        elif key.char == ';':     # Tilt down
            tilt_angle = max(tilt_angle - 5, 0)
            tilt_servo.write(tilt_angle)
    except AttributeError:
        pass

def on_release(key):
    # Stop motors when key is released
    left_motor.stop()
    right_motor.stop()

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