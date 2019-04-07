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
<title>Waterboarding Plant v2</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
<link rel="stylesheet" href="https://code.getmdl.io/1.3.0/material.indigo-pink.min.css">
<script defer src="https://code.getmdl.io/1.3.0/material.min.js"></script>
<style>

h1 {
    margin: 0px 20px;
}

object {
    font-family: "Roboto","Helvetica","Arial",sans-serif;
}

.cam_card.mdl-card {
  width: 620px;
  height: 610px;
  margin:20px;
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
<div><h1>Waterboarding Plant V2</h1></header></div>

<div class="cam_card mdl-card mdl-shadow--2dp">
  <div class="mdl-card__title mdl-card--expand">
    <h2 class="mdl-card__title-text">PlantCam</h2>
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

def get_info():
    light_on = GPIO.input(4)==0
    if not light_on:
        pixels.fill(( 200, 0, 200))
    else:
        pixels.fill((0, 0, 0))
    pixels.show()


    adc_value = readadc(photo_ch, SPICLK, SPIMOSI, SPIMISO, SPICS)

    if adc_value < 50:
        forward(1)


    light = "On" if light_on else "Off"
    humidity, temperature = Adafruit_DHT.read_retry(11, 3)
    return "Light: " + light + "</br>" + \
           "Temperature: " + str(temperature) + "</br>" + \
           "Humidity: " + str(humidity) + "</br>" + \
           "Water level: " + str("%.1f" % (adc_value / 200. * 100))



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


with picamera.PiCamera(resolution='640x480', framerate=16) as camera:
    output = StreamingOutput()
    camera.start_recording(output, format='mjpeg')
    try:
        address = ('', 8000)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        camera.stop_recording()