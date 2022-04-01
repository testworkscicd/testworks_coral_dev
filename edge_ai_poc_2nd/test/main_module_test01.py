
# 카메라 쓰레드 테스트
import os
import time
from capture_video import CaptureVideo

th01 = CaptureVideo("th01", 10, 1.5)
th01.daemon = True
th01.start()

# 중단 테스트
time.sleep(3)
th01.stop_capture()

th01.join()
th01 = None
print("main terminate...")
