
import logging
import os
import cv2
from threading import Thread
import time
from datetime import datetime
import requests
import json

from pycoral.adapters import common
from pycoral.adapters import detect
#from pycoral.utils.dataset import read_label_file
from pycoral.utils.edgetpu import make_interpreter
from pycoral.utils.edgetpu import run_inference

import settings


# DEFAULT_CAPTURE_WIDTH = 1920
# DEFAULT_CAPTURE_HEIGHT = 1080
DEFAULT_CAPTURE_WIDTH = 1280
DEFAULT_CAPTURE_HEIGHT = 720

IMAGE_SAVE_DIR = "save/"
STATUS_SAVE_DIR = "save/"
STATUS_FILE = "collect_status.json"
FILE_UPLOAD_URL = settings.API_BASE_URL + "file/fileUpload"

MODEL_DIR = "models/"
# MODEL_PATH = os.path.join(os.getcwd(), "models", "ssd_mobilenetv2_tf1_edgetpu_sidewalk.tflite")
# MODEL_LABEL_PATH = os.path.join(os.getcwd(), "models", "sidewalk_labels.txt")
MODEL_DETECT_SCORE_THRESHOLD = 0.5
MODEL_DETECT_TOP_K = 20

# init logger
logger = logging.getLogger(__name__)


def file_upload(file_path, save_dir):
    files = {"img": open(file_path, 'rb')}
    data_info = {"filePath": save_dir}
    res = requests.post(FILE_UPLOAD_URL, files=files, data=data_info)
    logger.info("File upload... :{0}".format(res.status_code))
    return res.status_code


def get_labels(labelPath):
    with open(labelPath) as f:
        lines = [line.strip().split() for line in f.readlines()]
        label_dict = dict()

        for elem in lines:
            label_dict[int(elem[0])] = elem[1]

        return label_dict


class CaptureVideo(Thread):
    def __init__(self, name, rule_info, model_name, is_continue=False, continue_count=0):
        super().__init__()
        self.name = name

        if model_name:
            self.model_name = model_name

        self.run_video = True
        self.last_capture_time = datetime.min
        self.max_count = rule_info["max_img_num"]
        self.capture_interval = rule_info["intervals"]
        self.object_list = self.get_object_list(rule_info["objects"])
        self.min_object_count = rule_info["min_obj_num"]
        self.save_dir = IMAGE_SAVE_DIR
        self.dev_guid = settings.DEV_GUID
        self.rule_id = rule_info["id"]
        self.file_upload_path = rule_info["save_dir"]
        self.is_continue = is_continue
        self.continue_count = continue_count

        self.camera = cv2.VideoCapture(1)

        # 해상도 설정
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT_CAPTURE_WIDTH)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT_CAPTURE_HEIGHT)

        logger.info("detect object : " + str(self.object_list))        

    def get_model_path(self):
        path = os.path.join(os.getcwd(), MODEL_DIR, self.model_name)
        return path

    def get_model_label_path(self):
        path = os.path.join(os.getcwd(), MODEL_DIR, os.path.splitext(self.model_name)[0] + ".txt")
        return path

    def get_object_list(self, str_obj):
        """
        문자열로 이루어진 대상 객체를 리스트 형태로 변환하여 반환
        :param str_obj: ex-'car, bus, truck'
        :return: ex-['car', 'bus', 'truck']
        """
        return [k.strip() for k in str_obj.split(',')]

    def run(self):
        logger.info("collection thread run...")

        try:
            logger.info("model path:" + self.get_model_path())
            logger.info("model label path:" + self.get_model_label_path())            
            interpreter = make_interpreter(self.get_model_path())
            interpreter.allocate_tensors()
            label_dict = get_labels(self.get_model_label_path())
            capture_count = self.continue_count
            inference_size = common.input_size(interpreter)

            while self.run_video:
                ret, image = self.camera.read()

                if not ret:
                    continue

                # 최종 수집 시간이 설정된 수집 간격보다 클때만 수집 작업 진행
                gap_time = datetime.now() - self.last_capture_time
                if gap_time.total_seconds() <= self.capture_interval:
                    time.sleep(0.03) # 대략 30fps 기준
                    continue

                if capture_count >= self.max_count:
                    logger.info("complete capture up to the maximum number...")
                    break

                # detect
                cv2_im = image
                cv2_im_rgb = cv2.cvtColor(cv2_im, cv2.COLOR_BGR2RGB)
                cv2_im_rgb = cv2.resize(cv2_im_rgb, inference_size)
                run_inference(interpreter, cv2_im_rgb.tobytes())

                detection = detect.get_objects(interpreter, MODEL_DETECT_SCORE_THRESHOLD)[:MODEL_DETECT_TOP_K]                

                if detection:
                    target_count = 0
                    for detect_result in detection:
                        text = label_dict[int(detect_result.id)]
                        # 대상 객체인지 체크
                        if text in self.object_list:
                            target_count += 1

                    # 인식 최소 객체 수 체크
                    if target_count < self.min_object_count:
                        time.sleep(0.2) # 대상 객체가 없을 경우 부하 상태로 객체 인식하지 않도록 sleep
                        continue
                else:
                    time.sleep(0.2)  # 대상 객체가 없을 경우 부하 상태로 객체 인식하지 않도록 sleep
                    continue

                logger.info("Total detect: {0}, target detect :{1}".format(len(detection), target_count))

                # 조건에 맞으면 로컬 파일로 저장
                file_name = self.save_file(image)

                # 서버 전송
                res_code = file_upload(file_name, self.file_upload_path)

                if (res_code == 200) or (res_code == 201):
                    os.remove(file_name)
                else:
                    str_log = "파일 전송 실패... res_code:{0}, file_name:{1}".format(res_code, file_name)
                    logger.error(str_log)

                # 최종 수집 시간 갱신
                capture_count += 1
                self.last_capture_time = datetime.now()

                # 수집 상태 로컬 저장
                self.update_collect_status(capture_count)

        except Exception as ex:
            logger.error(ex)

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
