
import logging
import os
import cv2
from threading import Thread
import time
from datetime import datetime
import requests
import json

import settings


# DEFAULT_CAPTURE_WIDTH = 1920
# DEFAULT_CAPTURE_HEIGHT = 1080
DEFAULT_CAPTURE_WIDTH = 1280
DEFAULT_CAPTURE_HEIGHT = 720


IMAGE_SAVE_DIR = "save/"
STATUS_SAVE_DIR = "save/"
STATUS_FILE = "collect_status.json"
FILE_UPLOAD_URL = settings.API_BASE_URL + "files/upload"

# init logger
logger = logging.getLogger(__name__)


def file_upload(file_path, dev_guid, rule_id):
    files = {"file": open(file_path, 'rb')}
    data_info = {"device_guid": "test", "rule_id": rule_id}
    res = requests.post(FILE_UPLOAD_URL, files=files, data=data_info)
    logger.info("파일 업로드:{0}".format(res.status_code))
    return res.status_code


class CaptureVideo(Thread):
    def __init__(self, name, rule_info, is_continue=False, continue_count=0):
        super().__init__()
        self.name = name

        self.run_video = True
        self.last_capture_time = datetime.min
        self.max_count = rule_info["max_img_num"]
        self.capture_interval = rule_info["interval"]
        self.save_dir = IMAGE_SAVE_DIR
        self.dev_guid = settings.DEV_GUID
        self.rule_id = rule_info["id"]
        self.is_continue = is_continue
        self.continue_count = continue_count

        self.camera = cv2.VideoCapture(0)

        # 해상도 설정
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT_CAPTURE_WIDTH)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT_CAPTURE_HEIGHT)

        #ret, image = self.camera.read()
        #self.height, self.width = image.shape[:2]

    def run(self):
        logger.info("collection thread run...")
        capture_count = self.continue_count

        while self.run_video:
            ret, image = self.camera.read()

            # 최종 수집 시간이 설정된 수집 간격보다 클때만 수집 작업 진행
            gap_time = datetime.now() - self.last_capture_time
            if gap_time.total_seconds() <= self.capture_interval:
                time.sleep(0.02)
                continue

            if capture_count >= self.max_count:
                logger.info("complete capture up to the maximum number...")
                break

            # detect - skip
            print("기능 구현 : 객체 인식 - skip")

            # 조건에 맞으면 로컬 파일로 저장
            file_name = self.save_file(image)

            # 서버 전송
            res_code = file_upload(file_name, self.dev_guid, self.rule_id)

            if res_code == 200:
                os.remove(file_name)
            else:
                str_log = "파일 전송 실패... res_code:{0}, file_name:{1}".format(res_code, file_name)
                logger.error(str_log)

            # 최종 수집 시간 갱신
            capture_count += 1
            self.last_capture_time = datetime.now()

            # 수집 상태 로컬 저장
            self.update_collect_status(capture_count)

        self.camera.release()

    def stop_capture(self):
        self.run_video = False

    def save_file(self, image):
        file_name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_name = file_name + '.jpg'
        file_name = os.path.join(self.save_dir, file_name)

        if not os.path.exists(self.save_dir):
            os.mkdir(self.save_dir)

        cv2.imwrite(file_name, image)
        logger.info("image save :{0}".format(file_name))
        return file_name

    def update_collect_status(self, count):
        status_file = STATUS_SAVE_DIR + STATUS_FILE
        status_info = None
        with open(status_file) as f:
            status_info = json.loads(f.read())
            status_info["collect_count"] = count

        if status_info is not None:
            with open(status_file, 'w') as f:
                json.dump(status_info, f)
                logger.info("collect status updated... {0}".format(count))
