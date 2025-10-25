import socket
import threading
import cv2
from picarx import Picarx

px = Picarx()

CONTROL_PORT = 5000
VIDEO_PORT = 8080
HOST = ''  # 모든 인터페이스

# -----------------------------
# 제어 서버 (명령 수신)
# -----------------------------
def control_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, CONTROL_PORT))
    server.listen(5)
    print("Control server running...")

    while True:
        conn, addr = server.accept()
        data = conn.recv(1024).decode().strip()
        print("Received:", data)

        if data == "won":
            px.forward(50)
        elif data == "woff":
            px.stop()
        elif data == "aon":
            px.set_dir_servo_angle(-30)
        elif data == "aoff":
            px.set_dir_servo_angle(0)
        elif data == "son":
            px.backward(50)
        elif data == "soff":
            px.stop()
        elif data == "don":
            px.set_dir_servo_angle(30)
        elif data == "doff":
            px.set_dir_servo_angle(0)

        conn.close()

# -----------------------------
# 비디오 서버 (MJPEG 송신)
# -----------------------------
def video_server():
    video_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    video_sock.bind((HOST, VIDEO_PORT))
    video_sock.listen(1)
    print("Video server running...")

    conn, addr = video_sock.accept()
    print("Video client connected:", addr)

    cap = cv2.VideoCapture(0)
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        _, jpg = cv2.imencode('.jpg', frame, encode_param)
        conn.sendall(jpg.tobytes())

    cap.release()
    conn.close()

# -----------------------------
# 메인 실행
# -----------------------------
if __name__ == "__main__":
    threading.Thread(target=control_server, daemon=True).start()
    video_server()
