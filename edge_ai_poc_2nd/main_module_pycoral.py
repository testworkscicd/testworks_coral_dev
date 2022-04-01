
# main module : 상태 체크, 정책 확인
import logging
import init_logger

import os
import threading
import time
import requests
import json

import settings
from capture_video_pycoral import CaptureVideo


# DEV_INFO_URL = "http://192.168.4.58:1323/api/devices/12"
# RULE_INFO_URL = "http://192.168.4.58:1323/api/rules/"

DEV_STATUS_URL = settings.API_BASE_URL + "device/status"
DEV_INFO_HEALTH_URL = settings.API_BASE_URL + "device/health"
RULE_INFO_URL = settings.API_BASE_URL + "rule/"
DNN_INFO_URL = settings.API_BASE_URL + "dnn/"
FILE_UPLOAD_URL = settings.API_BASE_URL + "file/fileUpload"

STATUS_SAVE_DIR = "save/"
STATUS_FILE = "collect_status.json"

RULE_CHECK_INTERVAL = 3

DEV_STATUS_STOP = "1"
DEV_STATUS_START = "3"
DEV_STATUS_DETECTING = "5"
DEV_STATUS_WAITING = "7"

_dev_status_dic = {DEV_STATUS_STOP: "STOP", DEV_STATUS_START: "START", DEV_STATUS_DETECTING: "DETECTING",
                   DEV_STATUS_WAITING: "WAITING"}

_thread_detect = None
_dev_id = -1

# init logger
logger = logging.getLogger(__name__)


def init_dev():
    str_info = "Device initialization... DEV_GUID:{0}, DEV_NAME:{1}".format(settings.DEV_GUID, settings.DEV_NAME)
    logger.info(str_info)
    # status save dir
    if not os.path.exists(STATUS_SAVE_DIR):
        os.mkdir(STATUS_SAVE_DIR)


def check_timer():
    timer_handler()
    threading.Timer(RULE_CHECK_INTERVAL, check_timer).start()


def timer_handler():
    global _thread_detect, _dev_id

    res_info = put_dev_info_health(settings.DEV_GUID)
    dev_info_dict = res_info['device'][0]
    if dev_info_dict is None:
        return

    _dev_id = dev_info_dict["id"]
    dev_status = dev_info_dict["status"]
    logger.info("check server... status: {0}".format(_dev_status_dic[dev_status]))

    # 이전 작업이 완료되지 않고 종료됐으면 이어서 하기
    status_file = STATUS_SAVE_DIR + STATUS_FILE
    if (dev_status == DEV_STATUS_WAITING) and os.path.isfile(status_file):
        # 수집 정책 가져오기
        rule_info = None
        with open(status_file) as f:
            status_info = json.loads(f.read())
            rule_info = status_info["rule"]
        # 수집 쓰레드 생성, 시작
        if rule_info is not None:
            logger.info("continue collecting work...")
            dnn_info = get_dnn_info(rule_info["dnn_id"])
            if dnn_info is not None:
                update_dev_info(DEV_STATUS_DETECTING, settings.DEV_GUID)
                _thread_detect = CaptureVideo("detect", rule_info, dnn_info["path"], True, status_info["collect_count"])
                _thread_detect.daemon = True
                _thread_detect.start()

    # 수집 시작 상태 체크
    if (dev_status == DEV_STATUS_START) and (_thread_detect is None):
        # 수집 정책 받아오기
        rule_info = res_info['rule'][0]
        logger.info("rule info : {0}".format(rule_info))

        if rule_info is not None:
            dnn_info = get_dnn_info(rule_info["dnn_id"])
            if dnn_info is not None:
                # save initial status : rule info, transfer_count = 0
                save_collect_status(rule_info, 0)

                update_dev_info(DEV_STATUS_DETECTING, settings.DEV_GUID)
                _thread_detect = CaptureVideo("detect", rule_info, dnn_info["path"])
                _thread_detect.daemon = True
                _thread_detect.start()

    # 수집 중단 : status=="stop", th_detect.isAlive == True
    if dev_status == DEV_STATUS_STOP:
        if (_thread_detect is not None) and _thread_detect.is_alive():
            _thread_detect.stop_capture()
            logger.info("Stop detect thread...")

    # detect thread status check
    if _thread_detect and (not _thread_detect.is_alive()):
        logger.info("Detect thread terminated...")
        _thread_detect = None
        delete_collect_status_file()
        update_dev_info(DEV_STATUS_WAITING, settings.DEV_GUID)


# 기기에서 서버로 health check를 하면서 응답으로 상태 정보를 가져옴
def put_dev_info_health(dev_guid):
    json_data = {'guid': dev_guid}
    res = requests.put(DEV_INFO_HEALTH_URL, json=json_data)
    if res.status_code != 200:
        logger.error("Fail to PUT device health Info... guid:{0}".format(dev_guid))
        return None
    else:
        #print(res, res.text)
        res_dict = json.loads(res.text)
        #return res_dict['data']['device'][0]
        return res_dict['data']


# deprecated
def get_rule_info(id):
    if id is None:
        return None

    rule_url = RULE_INFO_URL + str(id)
    res = requests.get(rule_url)
    if res.status_code != 200:
        return None

    logger.info("수집 정책 가져오기... 성공")

    res_dic = json.loads(res.text)
    rule_info = res_dic['data'][0]
    logger.info("rule info : {0}".format(rule_info))
    return rule_info


def get_dnn_info(id):
    if id is None:
        return None

    req_url = DNN_INFO_URL + str(id)
    res = requests.get(req_url)
    if res.status_code != 200:
        return None

    logger.info("DNN 정보 가져오기... 성공")

    res_dic = json.loads(res.text)
    dnn_info = res_dic["data"][0]
    logger.info("dnn info : {0}".format(dnn_info))
    return dnn_info


def update_dev_info(status, dev_guid):
    json_data = {'status': status, 'guid': dev_guid}
    res = requests.put(DEV_STATUS_URL, json=json_data)
    logger.info("update_dev_info:{0}".format(res))


def save_collect_status(rule_info, count):
    save_dic = dict()
    save_dic["rule"] = rule_info
    save_dic["collect_count"] = count

    with open(STATUS_SAVE_DIR + STATUS_FILE, 'w') as f:
        json.dump(save_dic, f)


def delete_collect_status_file():
    save_file = STATUS_SAVE_DIR + STATUS_FILE
    if os.path.isfile(save_file):
        os.remove(save_file)







def main():
    init_dev()
    update_dev_info(DEV_STATUS_WAITING, settings.DEV_GUID)
    check_timer()
    print("main module")


if __name__ == "__main__":
    main()
