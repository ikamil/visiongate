import requests
from .creds import *
import base64, hmac, json, hashlib
import logging
URL = "https://eu-apia.coolkit.cc/v2/"


def ewelink_auth() -> str:
    creds = dict(email=APP_EMAIL, password=APP_PASSWORD, countryCode="+7")
    sign = base64.b64encode(hmac.new(APP_SECRET, msg=json.dumps(creds).encode(), digestmod=hashlib.sha256).digest()).decode()
    session = requests.post(f"{URL}user/login", headers={"Authorization": f"Sign {sign}", "x-ck-appid": APP_ID}, json=creds).json()
    logging.warning(session)
    return session.get("data", {}).get("at")


def post(token, json):
    return requests.post(f"{URL}device/thing/status", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=json).json()


def ewelink_on(token: str, dev: str):
    switch = {"type": 1, "id": dev, "params": {"switches": [{"switch": "on", "outlet": 0}]}}
    if not token:
        token = ewelink_auth()
    res = post(token, switch)
    if "token" in res["msg"] or res["error"] != 0:
        token = ewelink_auth()
        post(token, switch)
