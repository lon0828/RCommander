px = Picarx()

HOST = ''   # 모든 인터페이스
PORT = 5000

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((HOST, PORT))
sock.listen(5)

print("TCP server waiting for connection...")

while True:
    conn, addr = sock.accept()
    print("Connected by", addr)
    data = conn.recv(1024).decode().strip()
    print("Received:", data)

    if data == "won":
        px.forward(50)
    elif data == "woff":
        px.stop()

    elif data == "aon":
        px.set_dir_servo_angle(-30)  # 왼쪽
    elif data == "aoff":
        px.set_dir_servo_angle(0)

    elif data == "son":
        px.backward(50)
    elif data == "soff":
        px.stop()

    elif data == "don":
        px.set_dir_servo_angle(30)  # 오른쪽
    elif data == "doff":
        px.set_dir_servo_angle(0)

    conn.close()