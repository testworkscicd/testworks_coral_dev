from flask import Flask, render_template, Response
import cv2
#from edgetpu.detection.engine import DetectionEngine
from PIL import Image
import numpy as np
import os
import time

app = Flask(__name__)

# def hello():
#    return "Hello, World!"
video_file = "data/eval_data/20201004_1426.avi"


@app.route("/")
def index():
    return render_template('index.html')


def getLabels(labelPath):
    with open(labelPath) as f:
        lines = [line.strip().split() for line in f.readlines()]
        label_dict = dict()

        for elem in lines:
            label_dict[int(elem[0])] = elem[1]

        return label_dict
        # return {int(key) : value for key, value in lines}


def get_frame():
    #cap = cv2.VideoCapture(video_file)
    cap = cv2.VideoCapture(1)
    # 해상도 설정
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # 프레임 너비/높이, 초당 프레임 수 확인
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)  # 또는 cap.get(3)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)  # 또는 cap.get(4)
    fps = cap.get(cv2.CAP_PROP_FPS)  # 또는 cap.get(5)
    print('Frame width: %d, height: %d, FPS: %d' % (width, height, fps))

    while cap.isOpened():  # cap 정상동작 확인
        ret, frame = cap.read()
        # 프레임이 올바르게 읽히면 ret은 True
        if not ret:
            print("End of Frame ...")
            break
        # frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # web data encoding
        imgencode = cv2.imencode('.jpg', frame)[1]
        stringData = imgencode.tostring()
        yield (b'--frame\r\n'
               b'Content-Type: text/plain\r\n\r\n' + stringData + b'\r\n')

        time.sleep(int(1 / fps))

    cap.release()
    print("Streaming Terminated...")


@app.route('/calc')
def calc():
    return Response(get_frame(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, threaded=True)
