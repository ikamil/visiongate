import logging
from typing import List

from asgiref.sync import sync_to_async, async_to_sync
from django.http import StreamingHttpResponse, JsonResponse, HttpRequest
import cv2
from paddleocr import PaddleOCR
from .models import *
from django.shortcuts import redirect
from django.db.models import Q
from .numberplate import boxes, numbers
from .ewelink import *
from django.forms.models import model_to_dict
import asyncio


async def gate_open(request, id: int, do_open: bool):
	@sync_to_async
	def get_user_from_request(request: HttpRequest):
		return request.user if bool(request.user) else None
	user = await get_user_from_request(request)
	if not user.is_authenticated:
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")

	@sync_to_async
	def get_location() -> Location:
		if not user.is_superuser:
			loc = Location.objects.get(Q(id=id) & Q(owner_id=request.user.id))
		else:
			loc = Location.objects.get(Q(id=id))
		return loc
	loc: Location = await get_location()

	@sync_to_async
	def do():
		open_close(loc, do_open)

	if do_open is not None:
		await do()

	res = model_to_dict(loc)
	res["status_title"] = loc.get_status_display()
	return JsonResponse(res)


def generate(cam: Camera, src, ocr: PaddleOCR, allowed: List[str], token: str, dev: str):
	# loop over frames from the output stream
	num_box = 20
	num_ocr = 20
	cnt = 0
	after_pause = 0
	pause = False
	again = 200
	cap = cv2.VideoCapture(src)
	numbers_list = []
	prefix = (str(allowed) if len(allowed) == 1 else len(allowed)) + ": "
	while cap.isOpened():
		ret, frame = cap.read()
		if not ret:
			break
			# encode the frame in JPEG format
			# ensure the frame was successfully encoded
		if pause:
			after_pause += 1
			if divmod(after_pause, again)[1] == 0:
				pause = False
		if divmod(cnt, num_box)[1] == 0 and not pause:
			boxes_list = boxes(frame)
			logging.warning(boxes_list)
			if divmod(cnt, num_ocr)[1] == 0:
				numbers_list = numbers(frame, boxes_list, ocr)
				if any([x in numbers_list for x in allowed]):
					pause = True
					after_pause = 0
					event = Event(location=cam.location, camera=cam, inout=cam.inout, payload=numbers_list, owner=cam.owner)
					event.save()
					open_close(cam.location)
				logging.warning(numbers_list)
		frame = cv2.resize(frame, (590, 290), interpolation=cv2.INTER_LINEAR)
		frame = cv2.putText(frame, prefix + (" ! " if pause else "") + numbers_list.__str__(), (15, 35), cv2.FONT_HERSHEY_SIMPLEX,	fontScale=1, color=(255, 100, 0), thickness=2, lineType=cv2.LINE_AA)
		(flag, encodedImage) = cv2.imencode(".jpg", frame)
		jpeg_bytes = encodedImage.tobytes()
		cnt += 1
		# yield the output frame in the byte format
		yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
		# time.sleep(0.005)


def video(request, id: int):
	if not request.user.is_authenticated:
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")
	from paddleocr import PaddleOCR
	ocr = PaddleOCR(lang="en")
	if not request.user.is_superuser:
		cam = Camera.objects.get(Q(id=id) & Q(owner_id=request.user.id))
	else:
		cam = Camera.objects.get(Q(id=id))
	if not cam:
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")
	loc = cam.location
	logging.warning(f"ocr loaded cam={loc}")
	if loc.allowed:
		allowed = loc.allowed.split("\n")
		allowed = [x.strip().upper() for x in allowed]
	else:
		allowed = []
	src = cam.sample.path
	token = ewelink_auth()
	loc.token = token
	loc.save()
	res = StreamingHttpResponse(generate(cam, src, ocr, allowed, token, loc.device), content_type = "multipart/x-mixed-replace; boundary=frame")
	# res["Cache-Control"] = "no-cache"  # prevent client cache
	# res["X-Accel-Buffering"] = "no"  # Allow Stream over NGINX server
	return res


import time

def streaming_view(request):
	def stream_data():
		for i in range(3):
			time.sleep(1)
			yield f"Data chunk test {i}{'_______'.zfill(1024)}\n"
			# Simulate delay between chunks

	response = StreamingHttpResponse(stream_data())
	# response["Content-Type"] = "text/plain"
	# response["Cache-Control"] = "no-cache"
	# response["X-Accel-Buffering"] = "no"
	return response