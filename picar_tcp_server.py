import socket
import threading
import time
from picarx import Picarx
from picamera2 import Picamera2
import cv2
import struct

# ==============================
CONTROL_HOST = "0.0.0.0"
CONTROL_PORT = 9000

VIDEO_HOST = "192.168.0.23"  # 수신 PC IP
VIDEO_PORT = 8001  # TCP 포트
FPS = 30
# ==============================

px = Picarx()
is_forward = False
is_backward = False
steer_dir = "center"

# ------------------------------
# 차량 제어 루프
# ------------------------------
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

# ------------------------------
# TCP 명령 수신
# ------------------------------
def command_server():
    global is_forward, is_backward, steer_dir
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((CONTROL_HOST, CONTROL_PORT))
    server.listen(1)
    print(f"[CONTROL] Waiting on {CONTROL_PORT}")
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

# ------------------------------
# TCP 영상 송신
# ------------------------------
def video_tcp():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((VIDEO_HOST, VIDEO_PORT))
    print(f"[VIDEO] Connected to {VIDEO_HOST}:{VIDEO_PORT}")

    picam2 = Picamera2()
    video_config = picam2.create_preview_configuration(main={"size": (1280, 720)})
    picam2.configure(video_config)
    picam2.start()
    time.sleep(1)

    frame_interval = 1.0 / FPS
    while True:
        start_time = time.time()
        frame = picam2.capture_array()
        _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        data = buffer.tobytes()

        # 먼저 길이 4바이트 전송
        client.sendall(struct.pack("<I", len(data)))
        # 다음 실제 JPEG 데이터 전송
        client.sendall(data)

        elapsed = time.time() - start_time
        time.sleep(max(0, frame_interval - elapsed))

# ------------------------------
# 메인
# ------------------------------
if __name__ == "__main__":
    threading.Thread(target=control_loop, daemon=True).start()
    threading.Thread(target=command_server, daemon=True).start()
    video_tcp()
