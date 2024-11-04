from typing import List

from django.shortcuts import render
import asyncio
from django.http import StreamingHttpResponse
import cv2
import logging

from paddleocr import PaddleOCR

from .models import *
from django.shortcuts import redirect
from .numberplate import boxes, numbers


def generate(cam: Camera, src, ocr: PaddleOCR, allowed: List[str]):
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
	# return the response generated along with the specific media
	# type (mime type)
	from paddleocr import PaddleOCR
	ocr = PaddleOCR(lang="en")
	cam = Camera.objects.get(id=id)
	logging.warning(f"ocr loaded cam={cam.location}")
	if cam.location.allowed:
		allowed = cam.location.allowed.split("\n")
		allowed = [x.strip().upper() for x in allowed]
	else:
		allowed = []
	src = cam.sample.path
	res = StreamingHttpResponse(generate(cam, src, ocr, allowed), content_type = "multipart/x-mixed-replace; boundary=frame")
	# res["Cache-Control"] = "no-cache"  # prevent client cache
	# res["X-Accel-Buffering"] = "no"  # Allow Stream over NGINX server
	return res


import time

def streaming_view(request):
	async def async_generator():
		for i in range(3):
			await asyncio.sleep(1)  # Асинхронная задержка
			yield i  # Генерация значения

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