# import 단계에서 호출되어 logger 초기화
import os
import logging
import logging.config

if not os.path.exists("log/"):
    os.mkdir("log/")
logging.config.fileConfig('logging.conf')



