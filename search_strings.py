import sys, re

d = open(sys.argv[1], "rb").read()
kws = ["movie", "video", "record", "bitrate", "hdmi", "liveview",
       "menu", "exposure", "iso", "shutter", "aperture", "limit",
       "usb", "firmware", "update", "version", "T-Kernel", "task",
       "EventFlag", "semaphore", "device", "driver", "uart", "sd",
       "card", "jpg", "nef", "raw", "mjpeg", "h264", "audio"]

seen = 0
for m in re.finditer(rb"[ -~]{4,}", d):
    s = m.group().decode("ascii", "ignore")
    low = s.lower()
    if any(k.lower() in low for k in kws):
        print("0x%08X  %s" % (m.start(), s))
        seen += 1
        if seen >= 200:
            break
