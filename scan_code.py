import sys, struct
import numpy as np

d = open(sys.argv[1], "rb").read()
BLOCK = 0x10000
rows = []

for off in range(0, len(d), BLOCK):
    b = d[off:off+BLOCK]
    n4 = len(b) // 4
    w = np.frombuffer(b[:n4*4], dtype="<u4")
    arm = int(np.count_nonzero((w & 0xFFFF0000) == 0xE92D0000))

    n2 = len(b) // 2
    h = np.frombuffer(b[:n2*2], dtype="<u2")
    thumb_push = int(np.count_nonzero((h & 0xFF00) == 0xB500))
    thumb_pop = int(np.count_nonzero((h & 0xFF00) == 0xBD00))
    thumb_bx = int(np.count_nonzero(h == 0x4770))

    score = arm * 3 + thumb_push * 2 + thumb_pop + thumb_bx
    if score > 20:
        rows.append((score, off, arm, thumb_push, thumb_pop, thumb_bx))

rows.sort(reverse=True)
print("score  offset    ARM   Tpush  Tpop   Tbx")
for score, off, arm, tp, tpo, tbx in rows[:40]:
    print("%5d  0x%06X  %5d  %5d  %5d  %5d"
          % (score, off, arm, tp, tpo, tbx))
