import os
import cv2
import numpy as np


def detect_pennies(image_path, out_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {image_path}")

    output = img.copy()

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 2)

    # Hough circle detection
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=40,
        param1=100,
        param2=50,
        minRadius=20,
        maxRadius=80,
    )

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    detected = []
    penny_idxs = []

    if circles is not None:
        circles = np.uint16(np.around(circles[0]))

        # convert to list of tuples
        circle_list = [(int(x), int(y), int(r)) for (x, y, r) in circles]

        def merge_circles(circle_list, overlap_thresh=0.6):
            # Greedy NMS: sort by radius descending, keep circle if not overlapping kept ones
            sorted_c = sorted(circle_list, key=lambda c: c[2], reverse=True)
            kept = []
            for (x, y, r) in sorted_c:
                keep = True
                for (kx, ky, kr) in kept:
                    dist = np.hypot(x - kx, y - ky)
                    if dist < overlap_thresh * (r + kr):
                        keep = False
                        break
                if keep:
                    kept.append((x, y, r))
            return kept

        merged = merge_circles(circle_list, overlap_thresh=0.55)

        for i, (x, y, r) in enumerate(merged, start=1):
            # sample a small patch around the center to estimate color
            x1, x2 = max(0, x - 4), min(hsv.shape[1], x + 5)
            y1, y2 = max(0, y - 4), min(hsv.shape[0], y + 5)
            patch = hsv[y1:y2, x1:x2]
            if patch.size == 0:
                mean_hsv = np.array([0, 0, 0])
            else:
                mean_hsv = patch.reshape(-1, 3).mean(axis=0)

            h, s, v = mean_hsv

            # heuristics for penny color (copper/orange-brown)
            is_penny = (h >= 5 and h <= 30 and s >= 50 and v >= 40)

            detected.append(((x, y, r), is_penny))
            if is_penny:
                penny_idxs.append(i)

            # draw
            color = (0, 0, 255) if is_penny else (255, 0, 0)
            cv2.circle(output, (x, y), r, color, 2)
            cv2.circle(output, (x, y), 2, (0, 255, 0), 3)
            cv2.putText(output, str(i), (x - 10, y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    total = len(detected)
    pennies = sum(1 for _ in detected if _[1])

    # annotate counts on image
    cv2.putText(output, f"Detected: {total} coins", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(output, f"Pennies: {pennies}", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    cv2.imwrite(out_path, output)

    return total, pennies, detected


def main():
    script_dir = os.path.dirname(__file__)
    img_path = os.path.join(script_dir, "coins.png")
    out_path = os.path.join(script_dir, "coins_detected.png")

    total, pennies, detected = detect_pennies(img_path, out_path)
    print(f"Total detected circles: {total}")
    print(f"Pennies detected: {pennies}")
    print(f"Annotated image saved to: {out_path}")


if __name__ == "__main__":
    main()
