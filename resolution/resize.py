import cv2 as cv
import sys

for i in range(1, 9):
    filepath = f"./resources/{i}.png"
    img = cv.imread(filepath)

    if img is None:
        sys.exit(f"Could not read the image: {filepath}")

    resized_image = cv.resize(img, (640, 480), interpolation=cv.INTER_LINEAR)

    output_path = f"./resolution/{i}-640x480.png"
    success = cv.imwrite(output_path, resized_image)

    print(f"{filepath} -> 640x480 | Saved: {success}")