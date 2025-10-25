import socket
import threading
import struct
import cv2
import time
from picarx import Picarx  # SunFounder PiCar-X 제어 모듈

# ==============================
# 설정
# ==============================
CONTROL_HOST = "0.0.0.0"     # 명령 수신 서버 (C#이 연결)
CONTROL_PORT = 9000

VIDEO_HOST = "192.168.0.23"  # 영상 수신할 PC IP
VIDEO_PORT = 8000
# ==============================

px = Picarx()

# ==============================
# 차량 제어 상태 변수
# ==============================
is_forward = False
is_backward = False
steer_dir = "center"  # "left", "right", "center"

# ==============================
# 차량 제어 루프
# ==============================
def control_loop():
    global is_forward, is_backward, steer_dir
    while True:
        # 전진/후진
        if is_forward:
            px.forward(30)
        elif is_backward:
            px.backward(30)
        else:
            px.stop()

        # 조향
        if steer_dir == "left":
            px.set_dir_servo_angle(-30)
        elif steer_dir == "right":
            px.set_dir_servo_angle(30)
        else:
            px.set_dir_servo_angle(0)

        time.sleep(0.05)

# ==============================
# 명령 수신 서버
# ==============================
def command_server():
    global is_forward, is_backward, steer_dir
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((CONTROL_HOST, CONTROL_PORT))
    server.listen(1)
    print(f"[CONTROL] Waiting for connection on {CONTROL_PORT}...")
    conn, addr = server.accept()
    print(f"[CONTROL] Connected from {addr}")

    while True:
        data = conn.recv(1024)
        if not data:
            break
        cmd = data.decode().strip()
        print(f"[RECV] {cmd}")

        # --------- 명령 처리 ---------
        if cmd == "won":
            is_forward = True
        elif cmd == "woff":
            is_forward = False
            px.stop()
        elif cmd == "son":
            is_backward = True
        elif cmd == "soff":
            is_backward = False
            px.stop()
        elif cmd == "aon":
            steer_dir = "left"
        elif cmd == "aoff":
            steer_dir = "center"
        elif cmd == "don":
            steer_dir = "right"
        elif cmd == "doff":
            steer_dir = "center"

    conn.close()
    server.close()

# ==============================
# 영상 송신 클라이언트
# ==============================
def video_client():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((VIDEO_HOST, VIDEO_PORT))
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    print(f"[VIDEO] Connected to {VIDEO_HOST}:{VIDEO_PORT}")

    while True:
        ret, frame = cam.read()
        if not ret:
            break
        # JPEG로 인코딩
        _, buffer = cv2.imencode(".jpg", frame)
        data = buffer.tobytes()
        size = struct.pack("L", len(data))
        client.sendall(size + data)

    cam.release()
    client.close()

# ==============================
# 메인
# ==============================
if __name__ == "__main__":
    threading.Thread(target=control_loop, daemon=True).start()
    threading.Thread(target=command_server, daemon=True).start()
    video_client()
