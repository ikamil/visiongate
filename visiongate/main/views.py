import datetime
import logging
from difflib import SequenceMatcher
import numpy as np
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
from management.models import LocationUser
import os
import io
import threading
from threading import Lock


class Capture:
	last_frame = None
	frames = []
	last_ready = None
	url = ""
	lock = Lock()
	paused = False
	stopped = False

	def __init__(self, cam_id: int, rtsp_link: str, gap: int, batch: int = 1):
		self.url = rtsp_link or ""
		self.gap = gap
		self.cam_id = cam_id
		self.batch = batch
		self.capture = cv2.VideoCapture(self.url)
		self.stopped = not self.capture.isOpened()
		self.thread = threading.Thread(target=self.rtsp_cam_buffer, name=f"rtsp_read_thread_{self.cam_id}")
		self.thread.daemon = True
		self.thread.start()
		logging.warning(f"Started rtsp_read_thread_{cam_id} for {self.url} with status {self.capture.isOpened()}")

	def rtsp_cam_buffer(self):
		cnt = -1
		bad = 0
		_gap = max(1, self.gap)
		while not self.stopped:
			with self.lock:
				cnt += 1
				if self.capture.isOpened():
					bad = 0
					if cnt % _gap > 0 or self.paused:
						self.last_ready = self.capture.grab()
					else:
						self.last_ready, self.last_frame = self.capture.read()
						if self.last_ready and self.batch > 1:
							if len(self.frames) == self.batch:
								self.frames.pop(0)
							self.frames.append(self.last_frame)
				else:
					bad += 1
					self.last_ready = None
					if bad > 100:
						self.stopped = True


	def get_frames(self):
		if self.last_ready is not None and self.last_frame is not None:
			if self.batch > 1:
				_frames = []
				for frame in self.frames:
					_frames.append(frame.copy())
				return self.last_ready, _frames.copy()
			else:
				return self.last_ready, [self.last_frame.copy()]
		else:
			return self.last_ready, []

	def get_frame(self):
		if self.last_ready is not None and self.last_frame is not None:
			return self.last_ready, self.last_frame.copy()
		else:
			return self.last_ready, np.array([])

	def stop(self):
		self.stopped = True
		self.capture.release()
		self.thread.join()
		logging.warning(f"Stopped rtsp_read_thread_{self.cam_id} for {self.url} with status {self.capture.isOpened()}")


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
			ids = LocationUser.objects.filter(Q(user=request.user) & Q(deleted__isnull=True)).values_list('location', flat=True)
			cam = Camera.objects.get(Q(id=id) & (Q(owner_id=request.user.id) | Q(location__in=ids)))
		else:
			cam = Camera.objects.get(Q(id=id))
		return cam, cam.location

	cam, loc = await get_camera_loc()

	@sync_to_async
	def do():
		open_close(cam, do_open, user=user)

	if do_open is not None:
		await do()

	res = model_to_dict(loc)
	res["status_title"] = loc.get_status_display()
	return JsonResponse(res)


REPLACE = {"D": "0", "Q": "0", "O": "0", "R": "K", ".": "", ",": "", "V": "Y", "|": "", "I": "", " ": ""}
INPLACE = {"0": {"4": "A", "X": "K", "V": "Y", "9": "B", "7": "T", "1": "T"},
           "4,5": {"0": "C", "8": "B", "1": "T", "3": "B", "7": "T", "V": "Y", "X": "K", "9": "B"},
           "1,2,3": {"B": "8", "A": "4"},
           "6": {"M": "11"}}
CHANGES = {"10": {"6": ""}}
REPLACE2 = {"/": "7",}


def nums_allowed(numbers_list, allowed, sim=1.0) -> List[str]:
	def change(src: str, i: int, v: str) -> str:
		res = src
		res = res[:i] + v + (res[i + 1:] if i != -1 else "")
		return res

	def unify(src: str) -> str:
		res = src
		for r, v in REPLACE.items():
			res = res.replace(r, v)
		for i_, d in INPLACE.items():
			for r, v in d.items():
				for ii in i_.split(","):
					i = int(ii)
					if len(res) > i and res[i] == r:
						res = change(res, i, v)
		for l_, c in CHANGES.items():
			for ll in l_.split(","):
				l = int(ll)
				if len(res) == l:
					for i_, v in c.items():
						for ii in i_.split(","):
							i = int(ii)
							if len(res) > i:
								res = change(res, i, v)
		for r, v in REPLACE2.items():
			res = res.replace(r, v)
		return res

	if (len(allowed) == 1 and allowed[0] == "") or (len(numbers_list) == 1 and numbers_list[0] == ""):
		return []

	res = [x for x in numbers_list if x in allowed]
	if len(res):
		return res

	uni_nums = [unify(x) for x in numbers_list]
	res = [x for x in uni_nums if x in allowed]
	if len(res):
		return res

	if sim == 1.0:
		return [x for x in uni_nums if x in [unify(n) for n in allowed]]
	else:
		res = [x for x in uni_nums if any([SequenceMatcher(None, x, unify(n)).ratio() >= sim for n in allowed])]
		if not len(res):
			res = [x for x in uni_nums if any([y[1:3] == x[1:3] for y in allowed])]
		return res


def generate(cam1: Camera, cam2: Camera, src1: Capture, src2: Capture, ocr: PaddleOCR, allowed: List[str], is_preview: bool):
	# loop over frames from the output stream
	batch = settings.ONNX_BATCH_SIZE
	cnt = 0
	cam_in_bad = 0
	cam_out_bad = 0
	pause = False
	last_open = datetime.datetime.now() - datetime.timedelta(hours=1)
	last_num_save = datetime.datetime.now() - datetime.timedelta(hours=1)
	last_photo_save = datetime.datetime.now() - datetime.timedelta(hours=1)
	last_cam_frame = datetime.datetime.now() - datetime.timedelta(hours=1)
	last_processing = datetime.datetime.now() - datetime.timedelta(hours=1)
	sleep_msecs = 500
	pause_secs = 9
	non_image_minutes = 10
	same_image_minutes = 90
	prev_numbers = []
	frames1 = []
	frames2 = []
	prefix = (str(allowed) if len(allowed) == 1 else str(len(allowed))) + ": "
	prev_frame_filename = f"prev_frame_{cam1.pk}.npy"
	if os.path.exists(prev_frame_filename):
		prev_frame = np.load(prev_frame_filename)
	else:
		prev_frame: cv2.typing.MatLike = np.ndarray([])
	prev_frame_diff_min = 11
	try:
		while True:
			cam_cnt = 0
			cam_in, frame1 = src1.get_frame()
			cam_out, frame2 = src2.get_frame()
			if cam_in:
				frames1.append(frame1)
			if cam_out:
				frames2.append(frame2)
			if cam_in:
				cam_cnt += 1
				cam_in_bad = 0
			else:
				cam_in_bad += 1
			if cam_out:
				cam_cnt += 1
				cam_out_bad = 0
			else:
				cam_out_bad += 1
			log_text = ""
			if cam_cnt == 0 or cam_out_bad > 10 or cam_in_bad > 10:
				log_text += f"Cameras bads: {cam_in_bad} and {cam_out_bad}"
				break
			cnt += 1
			if pause:
				src1.paused = True
				src2.paused = True
				time.sleep(pause_secs)
				src1.paused = False
				src2.paused = False
				pause = False
			elif frames1 and frames2 and len(frames1 + frames2) == batch:
				frames_boxes_list = boxes(frames1 + frames2)
				frames_boxes_list1 = frames_boxes_list[:len(frames1)]
				frames_boxes_list2 = frames_boxes_list[len(frames1):]
				nums1 = []
				nums2 = []
				for boxes_list, frame_ in zip(frames_boxes_list1, frames1):
					nums1.extend(numbers(frame_, boxes_list, ocr))
					# logging.warning(f"boxes_list1={boxes_list} frame1_={frame_.shape} nums1={nums1}")
				for boxes_list, frame_ in zip(frames_boxes_list2, frames2):
					nums2.extend(numbers(frame_, boxes_list, ocr))
					# logging.warning(f"boxes_list2={boxes_list} frame2_={frame_.shape} nums2={nums2}")
				numbers_list1 = list(set(nums1))
				numbers_list2 = list(set(nums2))
				allow_nums1 = nums_allowed(numbers_list1, allowed)
				allow_nums2 = nums_allowed(numbers_list2, allowed)
				if len(allow_nums1) > 0:
					cam = cam1
					allow_nums = allow_nums1
					numbers_list = numbers_list1
					frame = frame1
				elif len(allow_nums2) > 0:
					cam = cam2
					allow_nums = allow_nums2
					numbers_list = numbers_list2
					frame = frame2
				else:
					allow_nums = []
					if len(numbers_list1) > 0 and any([x for x in numbers_list1]):
						numbers_list = numbers_list1
						cam = cam1
						frame = frame1
					elif len(numbers_list2) > 0 and any([x for x in numbers_list2]):
						numbers_list = numbers_list2
						cam = cam2
						frame = frame2
					else:
						numbers_list = numbers_list1 + numbers_list2
						cam = cam2 if len(numbers_list2) > 0 else cam1
						frame = frame2 if len(numbers_list2) > 0 else frame1
				if len(allow_nums) > 0:
					pause = True
					if last_open < datetime.datetime.now() - datetime.timedelta(seconds=10):
						open_close(cam, do_open=True, save_event=False)
						last_open = datetime.datetime.now()
				if len(numbers_list) > 0:
					same_nums = nums_allowed(numbers_list, prev_numbers, 0.8)
					empty_num = not any([len(x.strip()) > 6 for x in numbers_list])
					if (empty_num and last_num_save < datetime.datetime.now() - datetime.timedelta(minutes=1)) or (len(same_nums) == 0 and not empty_num and last_num_save < datetime.datetime.now() - datetime.timedelta(seconds=10)) or pause:
						event = Event(location=cam.location, camera=cam, inout=cam.inout, payload=f"{numbers_list} <> {same_nums} [{cnt}.{len(frames1)}.{len(frames2)}]", image="img.jpg", owner=cam.owner)
						if pause:
							event.status = "OPENING"
						if len(same_nums) == 0 or pause or (any([x for x in numbers_list]) and last_photo_save < datetime.datetime.now() - datetime.timedelta(minutes=non_image_minutes)):
							gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
							if len(prev_frame.shape):
								diff = np.sum(cv2.subtract(prev_frame, gray_frame) ** 2) / frame.shape[0] / frame.shape[1]
							else:
								diff = 100.0
							event.payload = event.payload + " %" + str(round(diff, 2))
							same_payload = len(same_nums) > 0 and diff <= prev_frame_diff_min/2 and last_photo_save > datetime.datetime.now() - datetime.timedelta(minutes=same_image_minutes)
							periods_non_image = max(min((datetime.datetime.now() - last_photo_save).seconds // 60 // non_image_minutes, 3), 1)
							if diff > (prev_frame_diff_min * ((3 / periods_non_image) if empty_num else 1)) or (pause and not same_payload):
								(flag, encodedImage) = cv2.imencode(".jpg", frame)
								event.image.save(
									os.path.basename(event.image.url),
									File(io.BytesIO(encodedImage.tobytes()))
								)
								last_photo_save = datetime.datetime.now()
								prev_frame = gray_frame.copy()
								np.save(prev_frame_filename, prev_frame)
							else:
								event.image = None
						else:
							event.image = None
						event.save()
						if not empty_num:
							prev_numbers = numbers_list
						last_num_save = datetime.datetime.now()
				log_text += f"cnt={cnt}, frames_boxes_list1={frames_boxes_list1}, frames_boxes_list2={frames_boxes_list2}, numbers_list1={numbers_list1}, numbers_list2={numbers_list2}"
				frames1 = []
				frames2 = []

			if is_preview and last_cam_frame < datetime.datetime.now() - datetime.timedelta(seconds=1) and frame1.shape == frame2.shape:
				frame = np.concatenate((frame1, frame2), axis=0)
				frame = cv2.resize(frame, (590, 290 * 2), interpolation=cv2.INTER_LINEAR)
				# frame = cv2.putText(frame, prefix + (" ! " if pause else "") + numbers_list.__str__(), (15, 35), cv2.FONT_HERSHEY_SIMPLEX,	fontScale=1, color=(255, 100, 0), thickness=2, lineType=cv2.LINE_AA)
				(flag, encodedImage) = cv2.imencode(".jpg", frame)
				jpeg_bytes = encodedImage.tobytes()
				yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
				last_cam_frame = datetime.datetime.now()
			else:
				yield

			sleep_secs = min(sleep_msecs, max(10, sleep_msecs - (datetime.datetime.now() - last_processing).microseconds // 1000)) / 1000
			time.sleep(sleep_secs)
			logging.warning(f"{log_text + ' | ' if log_text else ''}Sleeping {sleep_secs} s. Frames {frame1.shape} {frame2.shape}")
			last_processing = datetime.datetime.now()

	finally:
		src1.stop()
		src2.stop()


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
	if not request.user.is_superuser and not is_local:
		ids = LocationUser.objects.filter(Q(user=request.user) & Q(deleted__isnull=True)).values_list('location', flat=True)
		cam = Camera.objects.get(Q(id=id) & (Q(location_id__in=ids) | Q(owner=request.user) | Q(owner__isnull=True)))
		cam1 = Camera.objects.get(Q(location_id=cam.location_id) & Q(inout="IN") & Q(owner_id=request.user.id))
		cam2 = Camera.objects.get(Q(location_id=id) & Q(inout="OUT") & Q(owner_id=request.user.id))
	else:
		cam = Camera.objects.get(Q(id=id))
		cam1 = Camera.objects.get(Q(location_id=cam.location_id) & Q(inout="IN"))
		cam2 = Camera.objects.get(Q(location_id=cam.location_id) & Q(inout="OUT"))
	if not cam1 and not cam2:
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")
	from paddleocr import PaddleOCR
	ocr = PaddleOCR(use_angle_cls=False, lang="en")  # отключение распознавания перевёрнутых текстов для скорости
	loc = cam1.location
	logging.warning(f"ocr loaded cam={loc}")
	if loc.allowed:
		allowed = loc.allowed.replace("\r", "").split("\n")
		allowed = [x.strip().upper() for x in allowed]
	else:
		allowed = []
	src1_url = cam1.url or cam1.sample.path
	src2_url = cam2.url or cam2.sample.path
	src1 = Capture(cam1.pk, src1_url, 5, 2)
	src2 = Capture(cam2.pk, src2_url, 5, 2)
	token = ewelink_auth()
	loc.token = token
	loc.save()
	res = StreamingHttpResponse(generate(cam1, cam2, src1, src2, ocr, allowed, request.user.is_authenticated and is_local), content_type = "multipart/x-mixed-replace; boundary=frame")
	# res["Cache-Control"] = "no-cache"  # prevent client cache
	# res["X-Accel-Buffering"] = "no"  # Allow Stream over NGINX server
	return res


def images(src: Capture, url: str):
	cnt = 0
	last_cam_frame = datetime.datetime.now() - datetime.timedelta(hours=1)
	last_cam_msecs = 500
	cam_started = datetime.datetime.now()
	if not src:
		cam = cv2.VideoCapture(f"rtspsrc location={url} ! decodebin ! videoconvert ! appsink max-buffers=1 drop=true")
	else:
		cam = None
	try:
		while True:
			cam_bad = 0
			cam_ok, frame = cam.read() if cam else src.get_frame()
			last_frame_read = last_cam_frame < datetime.datetime.now() - datetime.timedelta(milliseconds=last_cam_msecs)
			if cam_ok:
				cam_bad = 0
			else:
				cam_bad += 1
			if cam_bad > 10:
				break
			cnt += 1
			if cam_ok and last_frame_read:
				frame = cv2.resize(frame, (590, 290), interpolation=cv2.INTER_LINEAR)
				(flag, encodedImage) = cv2.imencode(".jpg", frame)
				jpeg_bytes = encodedImage.tobytes()
				yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
				last_cam_frame = datetime.datetime.now()
				# time.sleep(last_cam_msecs * 0.7 / 1000)
			else:
				yield
			time.sleep(last_cam_msecs * 0.7 / 1000)
			if cam_started < datetime.datetime.now() - datetime.timedelta(seconds=30):
				if src:
					src.stop()
				break
	finally:
		if src:
			src.stop()


def image(request, id: int):
	is_local = get_client_ip(request)
	if not request.user.is_authenticated and not is_local:
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")
	if not request.user.is_superuser and not is_local:
		ids = LocationUser.objects.filter(Q(user=request.user) & Q(deleted__isnull=True)).values_list("location", flat=True)
		cam = Camera.objects.get(Q(id=id) & (Q(location_id__in=ids) | Q(owner=request.user) | Q(owner__isnull=True)))
	else:
		cam = Camera.objects.get(Q(id=id))
	if not cam:
		return redirect(f"{settings.LOGIN_URL}?next={request.path}")
	src_url = cam.url or cam.sample.path
	src = None if False else Capture(cam.pk, src_url, 10, 1)
	res = StreamingHttpResponse(images(src, src_url), content_type = "multipart/x-mixed-replace; boundary=frame")
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