
import json

DEV_INFO_PATH = "device_info.json"
DEV_GUID = ""
DEV_NAME = ""
API_BASE_URL = ""

with open(DEV_INFO_PATH) as f:
    dev_init_info = json.loads(f.read())
    DEV_GUID = dev_init_info["device_guid"]
    DEV_NAME = dev_init_info["device_name"]
    API_BASE_URL = dev_init_info["api_base_url"]


