import RPi.GPIO as GPIO
from time import sleep

GPIO.setmode(GPIO.BCM)
GPIO.setup(4, GPIO.IN)

while(True):
    sleep(0.5)
    print(GPIO.input(4))