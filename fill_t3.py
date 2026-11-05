#!/usr/bin/env python3
import sys, os, json, hashlib, argparse
from itertools import product
import numpy as np
import extract_key as ek
import decrypt_firmware as fw

def detect(raw):
    if raw[0:32] == b" " * 32:
        return 0
    if raw[0x20:0x40] == b" " * 32:
        return 0x20
    return None

def load(dirname):
    imgs = []
    for fn in sorted(os.listdir(dirname)):
        if not fn.lower().endswith(".bin"):
            continue
        raw = open(os.path.join(dirname, fn), "rb").read()
        h = detect(raw)
        if h is None:
            continue
        body = raw[h:]
        n = len(body) // 256
        sec = np.frombuffer(body[:n * 256], dtype=np.uint8).reshape(n, 256)
        imgs.append({"name": fn, "sha": hashlib.sha256(raw).hexdigest(),
                     "sec": sec, "hdr": h, "raw": raw})
        print("  %-20s %10d bytes %7d sectors hdr=0x%X"
              % (fn, len(raw), n, h))
    return imgs

def scores_for_block(imgs, b, t1, t2):
    acc = np.zeros(256, dtype=np.float64)
    cvec = np.arange(256, dtype=np.uint8)[:, None, None]
    for im in imgs:
        sec = im["sec"]
        n = sec.shape[0]
        start = b * 256
        while start + 256 <= n:
            block = sec[start:start + 256]                    # (256,256)
            base = block ^ t1[None, :] ^ t2[:, None]          # (256,256)
            vals = base[None, :, :] ^ cvec                    # (256,256,256)
            flat = vals.reshape(256, -1)
            zeros = np.count_nonzero(flat == 0, axis=1)
            ff = np.count_nonzero(flat == 255, axis=1)
            printable = np.count_nonzero((flat >= 0x20) & (flat < 0x7f), axis=1)
            words = flat.reshape(256, -1, 4).astype(np.uint32)
            arm = np.count_nonzero((words >> 28) == 0xE, axis=(1, 2))
            total = flat.shape[1]
            acc += (arm * 6.0 + printable * 0.8 + zeros * 1.5 + ff * 1.5) / total
            start += 65536
    return acc

def make_t3(t3d, missing, choice):
    t3 = np.zeros(256, dtype=np.uint8)
    for b, v in t3d.items():
        t3[b] = v
    for b, c in zip(missing, choice):
        t3[b] = c
    return t3

def validate_image(im, t1, t2, t3):
    old = fw.HDR
    fw.HDR = im["hdr"]
    plain = fw.decrypt(im["raw"], t1, t2, t3)
    fw.HDR = old
    try:
        fw.validate_firmware(memoryview(plain)[im["hdr"]:])
        return True, ""
    except ValueError as e:
        return False, str(e)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firmware-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    imgs = load(a.firmware_dir)
    norms = {}
    for im in imgs:
        norm = ek.recover_family(im["sec"])
        norms.setdefault(norm, []).append(im["name"])
    norm = next(iter(norms))
    print("stage 2: constant")
    t1, table = ek.fix_constant(imgs[0]["sec"], norm)
    print("  entries:", [x[0] for x in table])
    obs = ek.collect_observations([(i["name"], i["sha"], i["sec"]) for i in imgs], t1)
    covered = {b for _, b in obs}
    missing = [b for b in range(256) if b not in covered]
    print("missing:", missing)
    t2d, t3d = ek.solve_tables(obs)
    t2 = np.array([t2d[i] for i in range(256)], dtype=np.uint8)

    top = {}
    for b in missing:
        sc = scores_for_block(imgs, b, t1, t2)
        order = np.argsort(sc)[::-1]
        top[b] = [int(x) for x in order[:6]]
        print("\nblock %d top candidates:" % b)
        for c in top[b][:6]:
            print("   c=0x%02X  score=%.4f" % (c, sc[c]))

    rep = max(imgs, key=lambda i: len(i["raw"]))
    print("\nvalidating on", rep["name"])
    for combo in product(*[top[b][:4] for b in missing]):
        t3 = make_t3(t3d, missing, combo)
        ok, err = validate_image(rep, t1, t2, t3)
        if ok:
            print("FOUND:", [(b, "0x%02X" % c) for b, c in zip(missing, combo)])
            all_ok = True
            for im in imgs:
                ok2, err2 = validate_image(im, t1, t2, t3)
                print("  %-20s %s" % (im["name"], "ok" if ok2 else "FAILED: " + err2))
                all_ok &= ok2
            if not all_ok:
                sys.exit("some images failed validation")
            tables = {"T1": t1.tobytes(), "T2": t2.tobytes(), "T3": t3.tobytes()}
            check = {k: hashlib.sha256(v).hexdigest() for k, v in tables.items()}
            key = {"scheme": "mixed legacy", "period_bytes": 1 << 24,
                   "T1": tables["T1"].hex(), "T2": tables["T2"].hex(),
                   "T3": tables["T3"].hex(),
                   "sources": [{"file": i["name"], "sha256": i["sha"],
                                "header": i["hdr"]} for i in imgs],
                   "self_check": check}
            open(a.out, "w").write(json.dumps(key, indent=1) + "\n")
            print("wrote", a.out)
            return
    print("no candidate combo passed; send this output")

if __name__ == "__main__":
    main()
