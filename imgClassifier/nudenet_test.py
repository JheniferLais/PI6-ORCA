from nudenet import NudeDetector
detector = NudeDetector()
# the 320n model included with the package will be used


detector.censor('testImages/homi.jpg') # Censors the image and saves it to mrbeast_censored.jpg


# detector.detect_batch(['image_1.jpg', 'image_2.jpg']) # Returns list of [list of detections]