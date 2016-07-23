# import the necessary packages
import requests
import time
from collections import deque

import cv2
import imutils
from picamera import PiCamera
from picamera.array import PiRGBArray

# call constructors
from fish_stream import FishStream

fish_stream = FishStream()

# output bitstream to binary file
out = open('fishData/fishBits.bin', 'wb')
out.truncate()

# define the lower and upper boundaries of the "pink"
# fish in the HSV color space, then initialize the
# list of tracked points
orangeLower = (0, 215, 37)
orangeUpper = (255, 255, 255)
pts = deque(maxlen=64)

# init pi camera
camera = PiCamera()
camera.vflip = True
camera.hflip = True
camera.resolution = (640, 368)
camera.framerate = 60
camera.exposure_mode='verylong'
rawCapture = PiRGBArray(camera, size=(640, 368))
    
# allow camera warmup
time.sleep(0.3)

# how many bits per file. 32768 bits = 4kb
totalBits = 32768

# capture frames from the camera
for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
   
    # grab the raw NumPy array representing the image 
    frame = frame.array

    # resize the frame, blur it, and convert it to the HSV color space
    frame = imutils.resize(frame, width=640)
    # blurred = cv2.GaussianBlur(frame, (11, 11), 0)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # construct a mask for the color "green", then perform
    # a series of dilations and erosions to remove any small
    # blobs left in the mask
    mask = cv2.inRange(hsv, orangeLower, orangeUpper)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)

    # find contours in the mask and initialize the current
    # (x, y) center of the ball
    cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL,
                            cv2.CHAIN_APPROX_SIMPLE)[-2]
    center = None

    # only proceed if at least one contour was found
    if len(cnts) > 0:
        # lets count the fishies on the screen
        fish_count = 0    
        x_compare = -1
        y_compare = -1

        first_bit = 0
        second_bit = 0
        
        # loop through all the contours in the mask
        for c in cnts:
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

            # only proceed if the radius meets a minimum  and max size
            if radius > 10: 
                # if a video path was not supplied, grab the reference:
                # draw the circle and centroid on the frame,
                # then update the list of tracked points
                cv2.circle(frame, (int(x), int(y)), int(radius),
                           (0, 255, 255), 2)
                cv2.circle(frame, center, 5, (255, 0, 255), -1)

                # where are the fish at now?
                fish_count += 1
                fish_stream.add_position(fish_count, x, y)

            # update the points queue
            pts.appendleft(center)

    # show the frame to our screen
    # cv2.imshow("Frame", frame)
    key = cv2.waitKey(1) & 0xFF

    # clear the stream in prep for next frame
    rawCapture.truncate(0)

    # sweet, we got enough bits from the fish
    if fish_stream.get_length() > totalBits:
        # first write to file
        out.write(fish_stream.get_bits(totalBits))

        # now lets make a packet with 'requests'
        url = 'http://127.0.0.1:5000/add-bits'
        data = {'token': 'auth_token'}
        headers = {'Content-type': 'multipart/form-data'}
        files = {'document': open('fishData/fishBits.bin', 'rb')}

        # now ship it
        response = requests.post(url, files=files, data=data, headers=headers)

        # how did we do?
        print "POST to", url
        print "response code:", response.status_code
        print "--------------------------------------------------"

        # nuke the file
        out.truncate()

    # if the 'q' key is pressed, stop the loop
    if key == ord("q"):
        out.write(str(fish_stream.stream))
        break

    # if the 'o' key is pressed output current contents of BitStream
    if key == ord("q"):
        fish_stream.print_stream()
        print "--------------------------------------------------"

    # if the 'p' print out stats of the stream
    if key == ord("p"):
        zero, one = fish_stream.get_probabilities()
        print "0:", zero
        print "1:", one
        print "total bits:", fish_stream.get_length(), "/", totalBits
        print "--------------------------------------------------"

# cleanup the camera and close any open windows
cv2.destroyAllWindows()