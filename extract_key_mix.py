#!/usr/bin/env python3
import sys, os, hashlib, json, argparse
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
            print("  skip %-20s no legacy label" % fn)
            continue
        body = raw[h:]
        n = len(body) // 256
        sec = np.frombuffer(body[:n * 256], dtype=np.uint8).reshape(n, 256)
        imgs.append({"name": fn, "sha": hashlib.sha256(raw).hexdigest(),
                     "sec": sec, "hdr": h, "raw": raw})
        print("  %-20s %10d bytes %7d sectors hdr=0x%X"
              % (fn, len(raw), n, h))
    return imgs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firmware-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    imgs = load(a.firmware_dir)
    if not imgs:
        sys.exit("no images")
    print("\nstage 1: T1 family")
    norms = {}
    for im in imgs:
        norm = ek.recover_family(im["sec"])
        if norm is None:
            sys.exit("error: %s has no constant-XOR sector family" % im["name"])
        norms.setdefault(norm, []).append(im["name"])
    if len(norms) != 1:
        print("groups:")
        for k, v in norms.items():
            print("  %s...  %s" % (k.hex()[:24], v))
        sys.exit("error: images disagree on T1 ^ T1[0]")
    norm = next(iter(norms))
    print("  all %d images agree: %s..." % (len(imgs), norm.hex()[:32]))

    print("\nstage 2: the global constant")
    t1, table = ek.fix_constant(imgs[0]["sec"], norm)
    if t1 is None:
        sys.exit("error: no global constant makes the table parse")
    print("  fixed from %s: %d entries" % (imgs[0]["name"], len(table)))
    for n, o, l in table[:6]:
        print("    %-20s off=0x%08x len=0x%08x" % (n, o, l))

    print("\nstage 3: padding observations")
    triple = [(i["name"], i["sha"], i["sec"]) for i in imgs]
    obs = ek.collect_observations(triple, t1)
    covered = {b for _, b in obs}
    print("  %d of 65536 cells observed, %d of 256 T3 blocks covered"
          % (len(obs), len(covered)))
    if len(covered) != 256:
        gaps = [b for b in range(256) if b not in covered]
        sys.exit("error: missing %d blocks: %s"
                 % (len(gaps), ", ".join(map(str, gaps[:40]))
                    + (" ..." if len(gaps) > 40 else "")))

    print("\nstage 4: solve")
    t2d, t3d = ek.solve_tables(obs)
    print("  T2 %d/256, T3 %d/256" % (len(t2d), len(t3d)))
    if len(t2d) != 256 or len(t3d) != 256:
        sys.exit("error: tables incomplete")
    t2 = np.array([t2d[i] for i in range(256)], dtype=np.uint8)
    t3 = np.array([t3d[i] for i in range(256)], dtype=np.uint8)

    print("\nstage 5: T3 correction")
    flipped = ek.correct_t3(triple, t1, t2, t3)
    print("  %d corrected" % len(flipped))

    print("\nvalidation")
    ok = True
    for im in imgs:
        old = fw.HDR
        fw.HDR = im["hdr"]
        plain = fw.decrypt(im["raw"], t1, t2, t3)
        fw.HDR = old
        try:
            mods = fw.validate_firmware(memoryview(plain)[im["hdr"]:])
            print("  %-20s ok, %d module CRCs + package CRC"
                  % (im["name"], len(mods)))
        except ValueError as e:
            print("  %-20s FAILED: %s" % (im["name"], e))
            ok = False
    if not ok:
        sys.exit("error: validation failed; no key written")

    tables = {"T1": t1.tobytes(), "T2": t2.tobytes(), "T3": t3.tobytes()}
    check = {k: hashlib.sha256(v).hexdigest() for k, v in tables.items()}
    key = {"scheme": "mixed legacy", "period_bytes": 1 << 24,
           "T1": tables["T1"].hex(), "T2": tables["T2"].hex(),
           "T3": tables["T3"].hex(),
           "sources": [{"file": i["name"], "sha256": i["sha"],
                        "header": i["hdr"]} for i in imgs],
           "self_check": check}
    if os.path.exists(a.out) and not a.force:
        sys.exit("%s exists; use --force" % a.out)
    open(a.out, "w").write(json.dumps(key, indent=1) + "\n")
    print("\nwrote %s" % a.out)

if __name__ == "__main__":
    main()
