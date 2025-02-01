import asyncio

from asgiref.sync import sync_to_async
from django.http import HttpResponse, HttpRequest
from django.shortcuts import redirect
from main.ewelink import *
from main.views import get_client_ip
from main.models import Event
import datetime
import os
import cv2
import numpy as np
import requests


async def webdav(request, cnt: int = 10):
	@sync_to_async
	def get_user_from_request(request: HttpRequest):
		return request.user if bool(request.user) else None
	user = await get_user_from_request(request)
	is_local = get_client_ip(request)
	if (not user or not user.is_authenticated) and not is_local:
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")

	@sync_to_async
	def do(id: int, url: str, img: str):
		if os.path.exists(img):
			os.unlink(img)
		event = Event.objects.get(id=id)
		event.cloud_url = url
		event.image = None
		event.save()

	@sync_to_async
	def get_events():
		records = Event.objects.raw("""select id, image, status, changed from main_event
		where nullif(trim(image), '') is not null and changed < (current_timestamp - interval '10 days')
		order by id limit  %s + 1""", [cnt])
		columns = records.columns
		result = []
		for record in records:
			result.append({col: getattr(record, col) for col in columns})
		return result

	created_dirs = set()
	prev_frame: cv2.typing.MatLike = np.ndarray([])
	gray_frame: cv2.typing.MatLike = np.ndarray([])
	frame: cv2.typing.MatLike = np.ndarray([])
	prev_frame_diff_min = 2
	prev_cloud_url = ""
	prev_url = ""
	events = await get_events()
	if len(events) == 0:
		logging.warning("No events found")
		resp = 600
	for event in events[:cnt]:
		print(event)
		resp = 1
		eid = event["id"]
		event_date: datetime = event["changed"]
		img = settings.MEDIA_ROOT + "/" + str(event["image"])
		file = img.split("/")[-1]
		if os.path.exists(img):
			frame = cv2.imread(img)
			try:
				gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
			except Exception as _:
				pass
		else:
			logging.warning(f"Image {img} not exists, skipping")
		if len(prev_frame.shape) and len(gray_frame.shape) and len(frame.shape):
			diff = np.sum(cv2.subtract(prev_frame, gray_frame) ** 2) / frame.shape[0] / frame.shape[1]
		else:
			diff = 100.0
		logging.warning(f"Processing Event {event} with diff {diff}")
		if os.path.exists(img) and diff > prev_frame_diff_min:
			year, month, day = event_date.year, event_date.month, event_date.day
			base = "https://webdav.cloud.mail.ru/___big/dev/uploads/visiongate"
			path_type = (event["status"].lower() + "/") if event["status"] and event["status"].strip() else ""
			date_dir = f"{path_type}{year}/{month}/{day}"
			date_path = f"{base}/{date_dir}"
			url = f"{date_path}/{file}"
			cloud_url = f"{CLOUD_SHARE}/{date_dir}/{file}"
			headers = {"Authorization": f"Basic {WEBDAV_AUTH}"}
			logging.warning(str(event) + " " + str(diff))
			dir_url = f"{base}"
			for pth in date_dir.split("/"):
				dir_url = f"{dir_url}/{pth}"
				if dir_url in created_dirs:
					continue
				res = requests.request("MKCOL", dir_url, headers=headers)
				logging.warning(dir_url + "  => "  + res.text + ": " + str(res.status_code))
				created_dirs.add(dir_url)
			res = requests.put(url, open(img, "rb").read(), headers=headers)
			logging.warning(url + res.text + "  => " + str(res.status_code))
			logging.warning(f"Cloud {url} result {res.text} with status={res.status_code}")
			prev_cloud_url = cloud_url
			prev_url = url
			prev_frame = gray_frame
			cloud_action = "created"
			cloud_status = res.status_code
		else:
			cloud_action = "reused"
			cloud_url = prev_cloud_url
			url = prev_url
			cloud_status = 0
		if cloud_action == "reused" or cloud_status == 201:
			logging.warning(f"Event id={eid}: {cloud_action} cloud {url}; deleting {img}")
			await do(eid, cloud_url, img)
			if cloud_action == "created" and cnt > 1:
				await asyncio.sleep(1)

	return HttpResponse(resp, content_type="text/plain")
