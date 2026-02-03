import cv2 as cv
import sys

img = cv.imread("./resources/1.png")
print(img.shape) 

if img is None:
    sys.exit("Could not read the image.")

cv.namedWindow("Display window", cv.WINDOW_NORMAL)
cv.resizeWindow("Display window", 800, 600)

cv.imshow("Display window", img)
k = cv.waitKey(0)

resized_image = cv.resize(img, (640, 480), interpolation=cv.INTER_LINEAR)
filename = "./resources/1-640x480.png"
cv.imwrite(filename, resized_image)

success = cv.imwrite(filename, resized_image)
print(f"Save successful: {success}")