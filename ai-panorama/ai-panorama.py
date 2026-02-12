#!/usr/bin/env python3
"""
Sequential stitching with a simple fallback window.

Behavior:
- Stitch in order (1,2,3,...).
- Primary attempt: stitch [current_pano, next_image]
- If that fails: stitch a small RAW window [prev_raw, next_raw, nextnext_raw]
  and then stitch [current_pano, window_pano]
- If still fails: skip and continue.

Run:
  cd ai-panorama
  python ai-panorama.py --pano-conf 0.1 --resize 0.85 images/*.png
"""

import re
import sys
import argparse
from pathlib import Path
import cv2 as cv


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def make_stitcher(mode, pano_conf):
    s = cv.Stitcher_create(mode)
    if hasattr(s, "setPanoConfidenceThresh"):
        s.setPanoConfidenceThresh(pano_conf)
    return s


def stitch_pair(mode, pano_conf, a, b):
    stitcher = make_stitcher(mode, pano_conf)
    status, pano = stitcher.stitch([a, b])
    return status, pano


def stitch_batch(mode, pano_conf, imgs):
    stitcher = make_stitcher(mode, pano_conf)
    status, pano = stitcher.stitch(imgs)
    return status, pano


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("img", nargs="+")
    parser.add_argument("--mode", choices=("panorama", "scans"), default="panorama")
    parser.add_argument("--pano-conf", type=float, default=0.1)
    parser.add_argument("--resize", type=float, default=0.85)
    args = parser.parse_args()

    mode = cv.Stitcher_PANORAMA if args.mode == "panorama" else cv.Stitcher_SCANS

    paths = sorted([Path(p) for p in args.img], key=lambda p: natural_key(p.name))
    print("Order:")
    for p in paths:
        print(" ", p.name)

    imgs = []
    for p in paths:
        im = cv.imread(str(p))
        if im is None:
            print(f"Can't read {p}")
            sys.exit(1)
        if args.resize != 1.0:
            im = cv.resize(im, None, fx=args.resize, fy=args.resize, interpolation=cv.INTER_AREA)
        imgs.append(im)

    result = imgs[0]
    used = [paths[0].name]

    for i in range(1, len(imgs)):
        print(f"Stitching next: {paths[i].name} ...")

        # Primary: pano + next
        status, pano = stitch_pair(mode, args.pano_conf, result, imgs[i])
        if status == cv.Stitcher_OK:
            result = pano
            used.append(paths[i].name)
            print(f"  [ok] now used {len(used)} images")
            continue

        print(f"  [warn] primary failed (status={status}). Trying fallback window...")

        # Fallback: stitch small raw window (prev_raw, next_raw, nextnext_raw)
        # We use imgs[i-1] (the raw previous image) as an anchor.
        window = [imgs[i-1], imgs[i]]
        if i + 1 < len(imgs):
            window.append(imgs[i+1])

        wstatus, wpano = stitch_batch(mode, args.pano_conf, window)
        if wstatus != cv.Stitcher_OK:
            print(f"  [skip] fallback window failed (status={wstatus})")
            continue

        # Merge: pano + window pano
        mstatus, mpano = stitch_pair(mode, args.pano_conf, result, wpano)
        if mstatus != cv.Stitcher_OK:
            print(f"  [skip] merge fallback failed (status={mstatus})")
            continue

        result = mpano
        used.append(paths[i].name)  # count the "next" image as used
        print(f"  [ok] fallback succeeded, now used {len(used)} images")

    out_path = Path("ai-panorama.jpg")
    cv.imwrite(str(out_path), result)
    print("✅ Saved:", out_path)

    print("\n✅ Saved:", out_path)
    print("Used images:")
    for name in used:
        print(" ", name)


if __name__ == "__main__":
    main()
    cv.destroyAllWindows()
