import datetime
import picamera
import time


date = datetime.datetime.now().strftime("%m_%d_%Y_%H_%M_%S")


with picamera.PiCamera() as camera:
    camera.start_preview()
    camera.start_recording("/home/pi/" + date + "video.h264")
    camera.wait_recording(30)
    camera.stop_recording()
    camera.stop_preview()
