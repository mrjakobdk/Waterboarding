import io
import picamera
import logging
import socketserver
import time
import RPi.GPIO as GPIO
import Adafruit_DHT
import board
import neopixel


from threading import Condition
from http import server
from water_sensor import readadc

# for water sensor
SPICLK = 11
SPIMISO = 9
SPIMOSI = 10
SPICS = 8

GPIO.setwarnings(False)
GPIO.cleanup()  # clean up at the end of your script
GPIO.setmode(GPIO.BCM)  # to specify whilch pin numbering system
# set up the SPI interface pins
GPIO.setup(SPIMOSI, GPIO.OUT)
GPIO.setup(SPIMISO, GPIO.IN)
GPIO.setup(SPICLK, GPIO.OUT)
GPIO.setup(SPICS, GPIO.OUT)

#dc motor
StepPinForward=23
StepPinBackward=24
GPIO.setup(StepPinForward, GPIO.OUT)
GPIO.setup(StepPinBackward, GPIO.OUT)

def reverse(x):
    GPIO.output(StepPinBackward, GPIO.HIGH)
    print("backwarding running motor")
    time.sleep(x)
    GPIO.output(StepPinBackward, GPIO.LOW)

def forward(x):
    GPIO.output(StepPinForward, GPIO.HIGH)
    print("forwarding running  motor ")
    time.sleep(x)
    GPIO.output(StepPinForward, GPIO.LOW)

#4, 18, 3

#GPIO.setmode(GPIO.BCM)
GPIO.setup(4, GPIO.IN)

pixel_pin = board.D18
num_pixels = 23
ORDER = neopixel.GRB
pixels = neopixel.NeoPixel(pixel_pin, num_pixels, brightness=0.1, auto_write=False,
                           pixel_order=ORDER)

# photoresistor connected to adc #0
photo_ch = 0


PAGE="""\
<html>
<head>
<title>Waterboarding Plant</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
<link rel="stylesheet" href="https://code.getmdl.io/1.3.0/material.indigo-pink.min.css">
<script defer src="https://code.getmdl.io/1.3.0/material.min.js"></script>
<style>

h1 {
    margin: 0px auto;
    display:inline-block;
}

object {
    font-family: "Roboto","Helvetica","Arial",sans-serif;
}

.cam_card.mdl-card {
  width: 620px;
  height: 590px;
  margin:20px auto;
}

.cam_card > .mdl-card__supporting-text {
  height: 80px;
}
.cam_card > .mdl-card__title {
  color: #fff;
  background:
    url('stream.mjpg') bottom right 15% no-repeat #46B6AC;
}
</style>
<script>
function readTextFile(file)
{
    var rawFile = new XMLHttpRequest();
    var allText
    rawFile.open("GET", file, false);
    rawFile.onreadystatechange = function ()
    {
        if(rawFile.readyState === 4)
        {
            if(rawFile.status === 200 || rawFile.status == 0)
            {
                allText = rawFile.responseText;
                console.log(allText);
            }
        }
    }
    rawFile.send(null);
    return allText;
}
</script>
</head>
<body>
"""

PAGE += """\
<header class="mdl-layout__header mdl-color--blue-grey-900 mdl-color-text--blue-grey-50">
<h1>Waterboarding Plant</h1></header>

<div class="cam_card mdl-card mdl-shadow--2dp">
  <div class="mdl-card__title mdl-card--expand">
    <h2 class="mdl-card__title-text">Spoiled Plant Cam</h2>
  </div>
  <div class="mdl-card__supporting-text">
    <p id="info"></p>
  </div>
</div>

</body>
<script src="//code.jquery.com/jquery-1.12.4.js"></script>
<script src="//code.jquery.com/ui/1.12.1/jquery-ui.js"></script> 
<script>
window.setInterval(function(){
    $('#info').html(readTextFile("file.txt"));
}, 500);
</script>
</html> 
"""

#<img src="stream.mjpg" width="640" height="480" />
# $('object').each(function(index,el){
#         $(el).attr('data', $(el).attr('data'));
#     });

counter = 0

def get_info():
    global counter

    light_on = GPIO.input(4)==0
    if not light_on:
        pixels.fill(( 200, 0, 200))
    else:
        pixels.fill((0, 0, 0))
    pixels.show()


    adc_value = readadc(photo_ch, SPICLK, SPIMOSI, SPIMISO, SPICS)

    if adc_value <= 30:
        counter += 1
        if counter > 3:
            reverse(1)
            #forward(1)
    else:
        counter -=1
    if counter < 0 or counter > 7:
        counter = 0
    print("counter",counter)
    print("adc",adc_value)

    light = "On" if light_on else "Off"
    humidity, temperature = Adafruit_DHT.read_retry(11, 3)
    return "<b>Light:</b> " + light + "</br>" + \
           "<b>Temperature:</b> " + str(temperature) + "C</br>" + \
           "<b>Humidity:</b> " + str(humidity) + "%</br>" + \
           "<b>Water level:</b>" + str(" %.1f" % (adc_value / 400. * 100)) + '%'



class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/file.txt':
            #text = str(time.time()) + "s"
            content = get_info().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            print("hej")
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


with picamera.PiCamera(resolution='640x480', framerate=10) as camera:
    output = StreamingOutput()
    camera.rotation = 90
    camera.start_recording(output, format='mjpeg')
    try:
        address = ('', 8000)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        camera.stop_recording()