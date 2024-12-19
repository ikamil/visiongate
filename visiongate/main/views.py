import datetime
from typing import List
from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse, JsonResponse, HttpRequest
import cv2
from paddleocr import PaddleOCR
from django.shortcuts import redirect
from django.core.files import File
from django.db.models import Q
from .numberplate import boxes, numbers
from .ewelink import *
from django.forms.models import model_to_dict
import os
import io


async def gate_open(request, id: int, do_open: bool):
	@sync_to_async
	def get_user_from_request(request: HttpRequest):
		return request.user if bool(request.user) else None
	user = await get_user_from_request(request)
	if not user.is_authenticated:
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")

	@sync_to_async
	def get_camera_loc():
		if not user.is_superuser:
			cam = Camera.objects.get(Q(id=id) & Q(owner_id=request.user.id))
		else:
			cam = Camera.objects.get(Q(id=id))
		return cam, cam.location

	cam, loc = await get_camera_loc()

	@sync_to_async
	def do():
		open_close(cam, do_open)

	if do_open is not None:
		await do()

	res = model_to_dict(loc)
	res["status_title"] = loc.get_status_display()
	return JsonResponse(res)


def nums_allowed(numbers_list, allowed):
	def unify(src: str) -> str:
		res = src.replace("O", "0")
		if res.endswith("C"):
			res = res[:-1] + "0"
		if res.startswith("4"):
			res = "A" + res[1:]
		return res

	return any([unify(x) in [unify(n) for n in numbers_list] for x in allowed])


def generate(cam: Camera, src, ocr: PaddleOCR, allowed: List[str], is_local: bool):
	# loop over frames from the output stream
	num_box = 20
	batch = settings.ONNX_BATCH_SIZE
	num_ocr = num_box * batch
	num_stream = 3
	cnt = 0
	after_pause = 0
	pause = False
	again = 200
	last_open = datetime.datetime.now() - datetime.timedelta(hours=1)
	cap = cv2.VideoCapture(src)
	numbers_list = []
	prev_numbers = []
	frames = []
	prefix = (str(allowed) if len(allowed) == 1 else str(len(allowed))) + ": "
	while cap.isOpened():
		ret, frame = cap.read()
		if not ret:
			break
			# encode the frame in JPEG format
			# ensure the frame was successfully encoded
		cnt += 1
		if pause:
			after_pause += 1
			if after_pause % again == 0:
				pause = False
		if cnt % num_box == 0 and not pause:
			frames.append(frame)
			if len(frames) == batch:
				frames_boxes_list = boxes(frames)
				nums = []
				for boxes_list, frame_ in zip(frames_boxes_list, frames):
					if cnt % num_ocr == 0:
						nums.extend(numbers(frame_, boxes_list, ocr))
				numbers_list = list(set(nums))
				if nums_allowed(numbers_list, allowed):
					pause = True
					after_pause = 0
					if last_open < datetime.datetime.now() - datetime.timedelta(seconds=10):
						open_close(cam)
						last_open = datetime.datetime.now()
				if cnt == num_ocr or (len(numbers_list) > 0 and numbers_list[0]):
					event = Event(location=cam.location, camera=cam, inout=cam.inout, payload=numbers_list, image="img.jpg", owner=cam.owner)
					if not any(x in prev_numbers for x in numbers_list):
						(flag, encodedImage) = cv2.imencode(".jpg", frame)
						event.image.save(
							os.path.basename(event.image.url),
							File(io.BytesIO(encodedImage.tobytes()))
						)
					else:
						event.image = None
					event.save()
				logging.warning(f"cnt={cnt}, {frames_boxes_list}, {numbers_list}")
				frames = []
				prev_numbers = numbers_list
		if not is_local:
			frame = cv2.resize(frame, (590, 290), interpolation=cv2.INTER_LINEAR)
			frame = cv2.putText(frame, prefix + (" ! " if pause else "") + numbers_list.__str__(), (15, 35), cv2.FONT_HERSHEY_SIMPLEX,	fontScale=1, color=(255, 100, 0), thickness=2, lineType=cv2.LINE_AA)
			(flag, encodedImage) = cv2.imencode(".jpg", frame)
			jpeg_bytes = encodedImage.tobytes()
			# yield the output frame in the byte format
			yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
			# time.sleep(0.005)
		else:
			yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n')


def get_client_ip(request):
	x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
	if x_forwarded_for:
		ip = x_forwarded_for.split(",")[0]
	else:
		ip = request.META.get("REMOTE_ADDR")
	logging.warning(ip)
	return ip == "127.0.0.1"


def video(request, id: int):
	is_local = get_client_ip(request)
	if not request.user.is_authenticated and not is_local:
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")
	from paddleocr import PaddleOCR
	ocr = PaddleOCR(lang="en")
	if not request.user.is_superuser and not is_local:
		cam = Camera.objects.get(Q(id=id) & Q(owner_id=request.user.id))
	else:
		cam = Camera.objects.get(Q(id=id))
	if not cam:
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")
	loc = cam.location
	logging.warning(f"ocr loaded cam={loc}")
	if loc.allowed:
		allowed = loc.allowed.replace("\r", "").split("\n")
		allowed = [x.strip().upper() for x in allowed]
	else:
		allowed = []
	src = cam.url or cam.sample.path
	token = ewelink_auth()
	loc.token = token
	loc.save()
	res = StreamingHttpResponse(generate(cam, src, ocr, allowed, is_local), content_type = "multipart/x-mixed-replace; boundary=frame")
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