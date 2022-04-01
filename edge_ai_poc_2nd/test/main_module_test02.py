
# api 호출 테스트
import threading
import time
import requests
import json


DEV_INFO_URL = "http://192.168.4.58:1323/api/devices/12"



def check_timer():
    threading.Timer(2, check_timer).start()
    timer_handler()


def timer_handler():
    print("timer handler", time.strftime('%Y-%m-%d %I:%M:%S %p', time.localtime()))
    res_dict = get_dev_info()
    #print(res_dict)
    print("상태 :", res_dict["status"])


def get_dev_info():
    #res = requests.get(test_get_url)
    res = requests.get(DEV_INFO_URL)
    #print(res, res.text)
    res_dict = json.loads(res.text)
    return res_dict['device']


if __name__ == "__main__":
    check_timer()
    # while():
    #     time.sleep(0.5)
