# debug_line_tread_motor.py
import socket, threading, time, traceback, sys, os

LOGFILE = "debug_log.txt"

def log(s):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} {s}"
    print(line)
    try:
        with open(LOGFILE, "a") as f:
            f.write(line + "\n")
    except:
        pass

log("=== START debug_line_tread_motor.py ===")
log("Python: " + sys.version.replace('\n', ' '))

# ===================== Imports =====================
px = None
ADC = None
try:
    from picarx import Picarx
    log("imported picarx")
    try:
        px = Picarx()
        log("Picarx() ok")
    except Exception as e:
        log("Picarx() init failed: " + repr(e))
        log(traceback.format_exc())
except Exception as e:
    log("import picarx failed: " + repr(e))
    log(traceback.format_exc())

try:
    from robot_hat import ADC as ADC_cls
    ADC = ADC_cls
    log("imported robot_hat.ADC")
except Exception as e:
    log("import robot_hat.ADC failed: " + repr(e))
    log(traceback.format_exc())

# ===================== Config =====================
CONTROL_HOST = "0.0.0.0"
CONTROL_PORT = 9000
SEND_MIN_INTERVAL = 0.5
BLACK_THRESHOLD_COUNT = 3
A0_NAME, A1_NAME, A2_NAME = "A0", "A1", "A2"
TREAD_MAX_COUNT = 6  # tread 누적 시 자동 타이머 종료

# ===================== ADC =====================
adc_left = adc_mid = adc_right = None
if ADC is not None:
    try:
        adc_left = ADC(A0_NAME)
        adc_mid  = ADC(A1_NAME)
        adc_right= ADC(A2_NAME)
        log("ADC objects created for A0/A1/A2")
    except Exception as e:
        log("ADC init failed: " + repr(e))
        log(traceback.format_exc())
else:
    log("ADC class not available; sensor reads will fail.")

# ===================== Globals =====================
control_conn = None
control_conn_lock = threading.Lock()
tread_count = 0
tread_count_lock = threading.Lock()
i2c_lock = threading.Lock()  # <<== 새로 추가된 I2C 락

# 모터 상태
motor_state = {"W": False, "A": False, "S": False, "D": False}
motor_lock = threading.Lock()

is_forward = False
is_backward = False
steer_dir = "center"

# ===================== Helpers =====================
def safe_send(conn, b):
    try:
        conn.sendall(b)
        return True
    except Exception as e:
        log("safe_send failed: " + repr(e))
        return False

def read_adc_values():
    if adc_left is None or adc_mid is None or adc_right is None:
        return None
    try:
        # I2C 버스 보호
        with i2c_lock:
            l = float(adc_left.read())
            m = float(adc_mid.read())
            r = float(adc_right.read())
        return l, m, r
    except Exception as e:
        log("ADC read error: " + repr(e))
        log(traceback.format_exc())
        return None

# ===================== Motor Control =====================
def control_loop():
    global is_forward, is_backward, steer_dir
    while True:
        with i2c_lock:
            if is_forward:
                px.forward(100)
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
    global is_forward, is_backward, steer_dir, control_conn
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((CONTROL_HOST, CONTROL_PORT))
    server.listen(1)
    print(f"[CONTROL] Waiting on {CONTROL_PORT}")
    conn, addr = server.accept()
    control_conn = conn
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

# ===================== Sensor Watcher =====================
def sensor_watcher():
    prev_black = False
    last_sent = 0.0
    black_counter = 0
    while True:
        vals = read_adc_values()
        if vals is None:
            log("[SENSOR] ADC values not available")
            time.sleep(1.0)
            continue
        l, m, r = vals
        mx = max(l, m, r)
        scale = 4095.0
        th = scale * 0.35
        avg = (l+m+r)/3.0
        is_black = avg > 10 and avg < 30

        log(f"[SENSOR] L={l:.1f} M={m:.1f} R={r:.1f} avg={avg:.1f} is_black={is_black}")

        if is_black:
            black_counter += 1
        else:
            black_counter = 0
            prev_black = False

        if black_counter >= BLACK_THRESHOLD_COUNT and not prev_black:
            now = time.time()
            if now - last_sent >= SEND_MIN_INTERVAL:
                with control_conn_lock:
                    if control_conn:
                        try:
                            control_conn.sendall(b"tread\n")
                            log("[SENSOR] SENT 'tread'")
                        except Exception as e:
                            log("[SENSOR] send failed: " + repr(e))
                    else:
                        log("[SENSOR] WOULD SEND 'tread' but no control connection")
                last_sent = now
            prev_black = True
            black_counter = 0
        time.sleep(0.2)

# ===================== Main =====================
try:
    t3 = threading.Thread(target=control_loop, daemon=True)
    t3.start()
    time.sleep(1.0)  # 하드웨어 초기화 대기
    t2 = threading.Thread(target=sensor_watcher, daemon=True)
    t2.start()
    t1 = threading.Thread(target=command_server, daemon=True)
    t1.start()

    log("Threads started. Main loop now prints status every 5s.")
    while True:
        with control_conn_lock:
            conn_status = "connected" if control_conn else "no-conn"
        with tread_count_lock:
            tc = tread_count
        log(f"[STATUS] control_conn={conn_status} tread_count={tc}")
        time.sleep(5)
except KeyboardInterrupt:
    log("Interrupted by user; exiting.")
except Exception as e:
    log("Main exception: " + repr(e))
    log(traceback.format_exc())

log("=== END ===")

