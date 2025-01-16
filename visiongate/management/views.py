import asyncio
import logging

from asgiref.sync import sync_to_async
from django.http import HttpResponse
from django.shortcuts import redirect
from django.db.models import Q
from main.ewelink import *
from main.views import get_client_ip
from django.forms.models import model_to_dict
from main.models import Event
import datetime
import os
import cv2
import numpy as np
import requests


async def webdav(request, cnt: int = 10):
	if not get_client_ip(request):
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")

	@sync_to_async
	def do(id: int, url: str, img: str):
		os.unlink(img)
		event = Event.objects.get(id=id)
		event.cloud_url = url
		event.image = None
		event.save()

	@sync_to_async
	def get_events():
		return list(Event.objects.filter(~Q(image="")&Q(image__isnull=False) & Q(deleted__isnull=True) &Q(changed__lt=datetime.datetime.now()-datetime.timedelta(days=10))).order_by("pk")[:cnt + 1].values("pk", "image", "changed"))

	resp = []
	created_dirs = set()
	prev_frame: cv2.typing.MatLike = np.ndarray([])
	prev_frame_diff_min = 2
	prev_cloud_url = ""
	prev_url = ""
	events = await get_events()
	if len(events) == 0:
		resp = [datetime.datetime.now().strftime(settings.DATETIME_FORMAT) + " no old events" + "\n"]
	for event in events[:cnt]:
		eid = event["pk"]
		event_date: datetime = event["changed"]
		img = settings.MEDIA_ROOT + "/" + event["image"]
		file = img.split("/")[-1]
		frame = cv2.imread(img)
		gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		if len(prev_frame.shape):
			diff = np.sum(cv2.subtract(prev_frame, gray_frame) ** 2) / frame.shape[0] / frame.shape[1]
		else:
			diff = 100.0
		logging.warning(f"Processing Event {event} with diff {diff}")
		if diff > prev_frame_diff_min:
			year, month, day = event_date.year, event_date.month, event_date.day
			base = "https://webdav.cloud.mail.ru/___big/dev/uploads/visiongate"
			date_dir = f"{year}/{month}/{day}"
			date_path = f"{base}/{date_dir}"
			url = f"{date_path}/{file}"
			cloud_url = f"{CLOUD_SHARE}/{date_dir}/{file}"
			headers = {"Authorization": f"Basic {WEBDAV_AUTH}"}
			resp.append(str(event) + " " + str(diff) + "\n")
			dir_url = f"{base}"
			for pth in date_dir.split("/"):
				dir_url = f"{dir_url}/{pth}"
				if dir_url in created_dirs:
					continue
				res = requests.request("MKCOL", dir_url, headers=headers)
				resp.append(dir_url + res.text + "  => " + str(res.status_code) + "\n")
				created_dirs.add(dir_url)
			res = requests.put(url, open(img, "rb").read(), headers=headers)
			resp.append(url + res.text + "  => " + str(res.status_code) + "\n")
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
