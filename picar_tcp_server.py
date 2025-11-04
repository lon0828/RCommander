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

# 모터 상태
motor_state = {"W": False, "A": False, "S": False, "D": False}
motor_lock = threading.Lock()

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
        l = float(adc_left.read())
        m = float(adc_mid.read())
        r = float(adc_right.read())
        return l, m, r
    except Exception as e:
        log("ADC read error: " + repr(e))
        log(traceback.format_exc())
        return None

# ===================== Command Server =====================
def command_server():
    global control_conn
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((CONTROL_HOST, CONTROL_PORT))
        s.listen(1)
        log(f"[CONTROL] listening on {CONTROL_PORT}")
    except Exception as e:
        log("Failed to bind/listen control port: " + repr(e))
        log(traceback.format_exc())
        return

    while True:
        try:
            conn, addr = s.accept()
            log(f"[CONTROL] client connected from {addr}")
            with control_conn_lock:
                control_conn = conn
            while True:
                data = conn.recv(1024)
                if not data:
                    log("[CONTROL] client closed socket")
                    break
                msg = data.decode(errors="ignore").strip()
                log("[CONTROL][IN] " + repr(msg))
                safe_send(conn, ("ECHO: " + msg + "\n").encode())
                process_command(msg)
        except Exception as e:
            log("command_server loop error: " + repr(e))
            log(traceback.format_exc())
        finally:
            with control_conn_lock:
                try:
                    if control_conn:
                        control_conn.close()
                except:
                    pass
                control_conn = None
            log("[CONTROL] connection cleaned up")

# ===================== Motor Control =====================
def process_command(cmd):
    global tread_count
    cmd = cmd.lower()
    if cmd == "won":
        with motor_lock:
            motor_state["W"] = True
            px.forward(100)
    elif cmd == "woff":
        with motor_lock:
            motor_state["W"] = False
            px.stop()
    elif cmd == "son":
        with motor_lock:
            motor_state["S"] = True
            px.backward(100)
    elif cmd == "soff":
        with motor_lock:
            motor_state["S"] = False
            px.stop()
    elif cmd == "aon":
        with motor_lock:
            motor_state["A"] = True
            px.set_dir_servo_angle(-30)
    elif cmd == "aoff":
        with motor_lock:
            motor_state["A"] = False
            px.set_dir_servo_angle(0)
    elif cmd == "don":
        with motor_lock:
            motor_state["D"] = True
            px.set_dir_servo_angle(30)
    elif cmd == "doff":
        with motor_lock:
            motor_state["D"] = False
            px.set_dir_servo_angle(0)
    elif cmd == "tread":
        with tread_count_lock:
            tread_count += 1
            log(f"[TREAD] Received tread count: {tread_count}")
            if tread_count >= TREAD_MAX_COUNT:
                log("[TREAD] Max tread count reached, stopping timer.")

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
        scale = 100.0 if mx <= 120 else 4095.0
        th = scale * 0.35
        avg = (l+m+r)/3.0
        if avg < scale*0.6:
            is_black = (l<th) or (m<th) or (r<th)
        else:
            is_black = (l>scale*0.8) or (m>scale*0.8) or (r>scale*0.8)

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
    t1 = threading.Thread(target=command_server, daemon=True)
    t1.start()
    t2 = threading.Thread(target=sensor_watcher, daemon=True)
    t2.start()
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

