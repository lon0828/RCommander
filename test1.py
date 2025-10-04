import cv2
import pygame
from picarx import Picarx
import threading
import time

# Initialize Picar-X
px = Picarx()

# Initialize Pygame for keyboard control
pygame.init()
screen = pygame.display.set_mode((200, 200))
pygame.display.set_caption("PiCar-X Control")

# Initialize camera using rpicam
cap = cv2.VideoCapture(0)  # Use /dev/video0

# Check if camera works
if not cap.isOpened():
    print("❌ Camera not detected. Try running: sudo raspi-config -> Interfaces -> Camera -> Enable")
    exit()

# Camera servo angles
pan_angle = 0
tilt_angle = 0

# Motor power
speed = 30  # You can adjust this (0~100)

# Thread for camera streaming
def camera_stream():
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        cv2.imshow("PiCar-X Camera", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

# Start camera thread
threading.Thread(target=camera_stream, daemon=True).start()

# Main control loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()

    # --- Driving ---
    if keys[pygame.K_w]:
        px.forward(speed)
    elif keys[pygame.K_s]:
        px.backward(speed)
    else:
        px.stop()

    # --- Steering ---
    if keys[pygame.K_a]:
        px.set_dir_servo_angle(-30)
    elif keys[pygame.K_d]:
        px.set_dir_servo_angle(30)
    else:
        px.set_dir_servo_angle(0)

    # --- Camera Control ---
    if keys[pygame.K_o]:
        tilt_angle += 2
        px.set_cam_tilt_servo_angle(tilt_angle)
    elif keys[pygame.K_l]:
        tilt_angle -= 2
        px.set_cam_tilt_servo_angle(tilt_angle)
    if keys[pygame.K_k]:
        pan_angle -= 2
        px.set_cam_pan_servo_angle(pan_angle)
    elif keys[pygame.K_SEMICOLON]:
        pan_angle += 2
        px.set_cam_pan_servo_angle(pan_angle)

    time.sleep(0.05)

pygame.quit()
px.stop()
cap.release()
cv2.destroyAllWindows()
