from PIL import Image
import numpy as np


# Loading the provinces file
provincesPicture = Image.open("provinces.bmp")
width = provincesPicture.size[0]
height = provincesPicture.size[1]

print(provincesPicture.getpixel((150,150)))

def checkForXcrossings(pixelA, pixelB, pixelC, pixelToCheck):
    colorA = provincesPicture.getpixel(pixelA)
    colorB = provincesPicture.getpixel(pixelB)
    colorC = provincesPicture.getpixel(pixelC)
    colorD = provincesPicture.getpixel(pixelToCheck)
    color_set = [colorA, colorB, colorC, colorD]
    if len(set(color_set)) == len(color_set):
        return True
    else:
        return False

for widthIndex in range(width-2):
    for heightIndex in range(height-2):
        pixelToCheck = (widthIndex, heightIndex)
        pixelA = (widthIndex + 1, heightIndex)
        pixelB = (widthIndex, heightIndex + 1)
        pixelC = (widthIndex + 1, heightIndex + 1)
        if checkForXcrossings(pixelA, pixelB, pixelC, pixelToCheck):
            print("Xcrossing at coordinated {}, {}".format(widthIndex, heightIndex))
            provincesPicture.putpixel((widthIndex + 1, heightIndex + 1),provincesPicture.getpixel(pixelB))


provincesPicture.save("provinces_fixed.bmp")

