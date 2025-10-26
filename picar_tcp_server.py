import socket
import threading
import struct
import time
import cv2
import RPi.GPIO as GPIO
from picarx import Picarx

# ==============================
# 설정
# ==============================
CONTROL_HOST = "0.0.0.0"
CONTROL_PORT = 9000
VIDEO_HOST = "0.0.0.0"
VIDEO_PORT = 8001

IR_PIN = 17  # 적외선 센서 핀 번호 (BCM 기준)
FPS = 30

px = Picarx()
GPIO.setmode(GPIO.BCM)
GPIO.setup(IR_PIN, GPIO.IN)

# ==============================
# 전역 변수
# ==============================
is_forward = False
is_backward = False
steer_dir = "center"
line_count = -1
prev_black = False

# ==============================
# 차량 제어 루프
# ==============================
def control_loop():
    global is_forward, is_backward, steer_dir
    while True:
        if is_forward:
            px.forward(30)
        elif is_backward:
            px.backward(30)
        else:
            px.stop()

        if steer_dir == "left":
            px.set_dir_servo_angle(-30)
        elif steer_dir == "right":
            px.set_dir_servo_angle(30)
        else:
            px.set_dir_servo_angle(0)

        time.sleep(0.05)

# ==============================
# 제어 명령 서버 (TCP)
# ==============================
def command_server():
    global is_forward, is_backward, steer_dir
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((CONTROL_HOST, CONTROL_PORT))
    server.listen(1)
    print(f"[CONTROL] Waiting on port {CONTROL_PORT}...")
    conn, addr = server.accept()
    print(f"[CONTROL] Connected from {addr}")

    while True:
        data = conn.recv(1024)
        if not data:
            break
        cmd = data.decode().strip()

        if cmd == "won": is_forward = True
        elif cmd == "woff": is_forward = False
        elif cmd == "son": is_backward = True
        elif cmd == "soff": is_backward = False
        elif cmd == "aon": steer_dir = "left"
        elif cmd == "aoff": steer_dir = "center"
        elif cmd == "don": steer_dir = "right"
        elif cmd == "doff": steer_dir = "center"

    conn.close()
    server.close()

# ==============================
# 영상 송신 서버 (TCP)
# ==============================
def video_server():
    global line_count, prev_black

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((VIDEO_HOST, VIDEO_PORT))
    server.listen(1)
    print(f"[VIDEO] Waiting on port {VIDEO_PORT}...")
    conn, addr = server.accept()
    print(f"[VIDEO] Connected from {addr}")

    cam = cv2.VideoCapture(0)
    cam.set(3, 1280)
    cam.set(4, 720)

    while True:
        ret, frame = cam.read()
        if not ret:
            continue

        # ---- IR 감지 ----
        ir_value = GPIO.input(IR_PIN)
        is_black = (ir_value == 0)  # 검은색이면 LOW
        if is_black and not prev_black:
            line_count += 1
            print(f"[IR] Line detected → Count: {line_count}")
        prev_black = is_black

        # ---- JPEG 인코딩 ----
        _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        data = jpeg.tobytes()

        # ---- 패킷 전송 ----
        header = struct.pack("<ii", len(data), line_count)
        try:
            conn.sendall(header + data)
        except:
            print("[VIDEO] Disconnected.")
            break

        time.sleep(1.0 / FPS)

    cam.release()
    conn.close()
    server.close()

# ==============================
# 메인
# ==============================
if __name__ == "__main__":
    threading.Thread(target=control_loop, daemon=True).start()
    threading.Thread(target=command_server, daemon=True).start()
    video_server()

