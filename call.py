from picarx import Picarx
import time

px = Picarx()

# 초기 offset값
offset = 0

print("앞바퀴 캘리브레이션 시작!")
print("좌/우 보정값을 키보드로 조정하고, 's'를 누르면 저장합니다.")
print("오른쪽 보정 +1, 왼쪽 보정 -1")

px.set_dir_servo_angle(0)  # 초기 각도

try:
    while True:
        cmd = input("커맨드 (a:왼쪽, d:오른쪽, s:저장 종료): ").strip().lower()

        if cmd == "a":
            offset -= 1
            px.dir_servo_offset = offset
            print(f"왼쪽으로 -1: 현재 offset = {offset}")
        elif cmd == "d":
            offset += 1
            px.dir_servo_offset = offset
            print(f"오른쪽으로 +1: 현재 offset = {offset}")
        elif cmd == "s":
            print(f"캘리브레이션 완료! 최종 offset = {offset}")
            break
        else:
            print("a/d/s 중 하나만 입력하세요.")

finally:
    px.set_dir_servo_angle(0)  # 최종 확인용, 중앙으로
    px.stop()