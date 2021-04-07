from flask import Flask, render_template, current_app, request, redirect, url_for, jsonify
import urllib
from urllib.request import Request, urlopen
import json
import imagehash
from PIL import Image
import cv2
import numpy as np
import os
import requests

def flattener(image, pts, w, h):
    """Flattens an image of a card into a top-down 200x300 perspective.
    Returns the flattened, re-sized, grayed image.
    See www.pyimagesearch.com/2014/08/25/4-point-opencv-getperspective-transform-example/"""
    temp_rect = np.zeros((4, 2), dtype="float32")

    s = np.sum(pts, axis=2)

    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]

    diff = np.diff(pts, axis=-1)
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]

    # Need to create an array listing points in order of
    # [top left, top right, bottom right, bottom left]
    # before doing the perspective transform

    if w <= 0.8 * h:  # If card is vertically oriented
        temp_rect[0] = tl
        temp_rect[1] = tr
        temp_rect[2] = br
        temp_rect[3] = bl

    if w >= 1.2 * h:  # If card is horizontally oriented
        temp_rect[0] = bl
        temp_rect[1] = tl
        temp_rect[2] = tr
        temp_rect[3] = br

    # If the card is 'diamond' oriented, a different algorithm
    # has to be used to identify which point is top left, top right
    # bottom left, and bottom right.

    if w > 0.8 * h and w < 1.2 * h:  # If card is diamond oriented
        # If furthest left point is higher than furthest right point,
        # card is tilted to the left.
        if pts[1][0][1] <= pts[3][0][1]:
            # If card is titled to the left, approxPolyDP returns points
            # in this order: top right, top left, bottom left, bottom right
            temp_rect[0] = pts[1][0]  # Top left
            temp_rect[1] = pts[0][0]  # Top right
            temp_rect[2] = pts[3][0]  # Bottom right
            temp_rect[3] = pts[2][0]  # Bottom left

        # If furthest left point is lower than furthest right point,
        # card is tilted to the right
        if pts[1][0][1] > pts[3][0][1]:
            # If card is titled to the right, approxPolyDP returns points
            # in this order: top left, bottom left, bottom right, top right
            temp_rect[0] = pts[0][0]  # Top left
            temp_rect[1] = pts[3][0]  # Top right
            temp_rect[2] = pts[2][0]  # Bottom right
            temp_rect[3] = pts[1][0]  # Bottom left

    maxWidth = 200
    maxHeight = 300

    # Create destination array, calculate perspective transform matrix,
    # and warp card image
    dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], np.float32)
    M = cv2.getPerspectiveTransform(temp_rect, dst)
    warp = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    #warp = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)
    return warp


def getcardPhoto(photo):

    img = cv2.imread(photo)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_w, img_h = np.shape(img)[:2]
    bkg_level = gray[int(img_h / 100)][int(img_w / 2)]
    thresh_level = bkg_level + 60
    blurImg = cv2.GaussianBlur(gray, (5,5), 0)

    _, thresh = cv2.threshold(blurImg, thresh_level, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    contourValues = []
    for i in contours:
        contourValues.append(cv2.contourArea(i))
    contourValues.sort()

    biggestContour = 0
    bigContourIndex = len(contourValues)-1

    for b in contours:
        if cv2.contourArea(b) == contourValues[-1]:
            biggestContour = b


    if len(contourValues) != 0:
        peri = cv2.arcLength(biggestContour, True)
        approx = cv2.approxPolyDP(biggestContour, 0.01 * peri, True)
        pts = np.float32(approx)
        CardCornerPoints = pts
        x, y, w, h = cv2.boundingRect(biggestContour)
        CardWidth, CardHeight = w, h
        average = np.sum(pts, axis=0)/len(pts)
        cent_x = int(average[0][0])
        cent_y = int(average[0][1])
        CardCenter = [cent_x, cent_y]
        img = flattener(img, pts, w, h)
        cv2.imwrite('camImage.png', img)
        hashForCamImg = imagehash.phash(Image.open('camImage.png'))
        return hashForCamImg
        #print(hashForCamImg)
        #hashForOnlineImg = imagehash.phash(Image.open('78.png'))
        #print(hashForOnlineImg)
        #print((hashForCamImg - hashForOnlineImg))


        #img = warpedIMG[0: 30, 0:int(w/2)]
        #print(pytesseract.image_to_string(img))
        #cv2.rectangle(img, (x, y), (x + w, y + h), (34, 65, 255), 3)
        #img = img[y:y+h, x:x+w]
        #cv2.imshow('image', img)


    else:
        return 'busted'
    cv2.drawContours(img, contours, -1, (0,255,0), 3)

    #cv2.imshow('image', img)


    key = cv2.waitKey(0)
    cv2.destroyAllWindows()


app = Flask(__name__, static_url_path='')

@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r

@app.route("/index.html")
def topLeft():
    return render_template("index.html")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/pokemon.html")
def poke():
    return render_template("pokemon.html")


@app.route("/pokemon.html", methods=['POST'])
def getIMG():

    userinputImage = request.files['user_group_logo']
    readyTorender = False
    buyCardURL =''
    if userinputImage.filename == '': #this is executed if no image is sent, should render a template that says no image was detected as input
        return render_template("pokemon.html", message='no file was uploaded')

    if userinputImage.filename != '':
        userinputImage.save('static/assets/img/inputImageName.png')
        print('<----got image---->')
        print(userinputImage.filename)
        photo = 'static/assets/img/inputImageName.png'
        photoPath = 'assets/img/inputImageName.png'
        camHash = getcardPhoto(photo)  # this is what to use when passing in a photo

        if type(camHash) == str: #this if statement is executed if the pokemon card is not picked up at all
            print('try again')
            return render_template("pokemon.html", message='unable to identify the pokemon card please try again') #this should render a template that says take a better picture

        with open('backupForpokeJSONUpToBW10.json') as f:
            newFileData = json.load(f)
            first = newFileData[0]
            likelyPoke = ''
            likelyId = ''
            listOfSmallestDifsNames = []
            listOfSmallestDifsImages = []
            smallestDiff = abs(camHash - imagehash.hex_to_hash(first['hash']))
            for i in newFileData:
                if abs(camHash - imagehash.hex_to_hash(i['hash'])) < smallestDiff:
                    likelyPoke = i['name']
                    likelyId = i['id']
                    imageForlikelyPoke = i['images']
                    imageForlikelyPoke = imageForlikelyPoke['small']
                    smallestDiff = abs(camHash - imagehash.hex_to_hash(i['hash']))
                    listOfSmallestDifsNames.append(likelyPoke)
                    listOfSmallestDifsImages.append(imageForlikelyPoke)

            print(f'name: {likelyPoke}, image: {imageForlikelyPoke}, id: {likelyId}')
            try:
                headers = {'X-Api-Key': '273629e6-4fc2-4777-8466-eeaae2157149'}
                urlWithId = 'https://api.pokemontcg.io/v2/cards/' + likelyId
                pokePriceresponse = requests.get(urlWithId, headers=headers)
                pokemonPriceData = pokePriceresponse.json()['data']['tcgplayer']
                buyCardURL = pokemonPriceData['url']
                ActualPrices = pokemonPriceData['prices']['normal']['market']
                ActualPrices= f'market price is : {ActualPrices}$'

            except:
                try:
                    ActualPrices= pokemonPriceData['prices']['holofoil']['market']
                    ActualPrices = f'holofoil price: {ActualPrices}$'

                except:
                    try:
                        ActualPrices = 'unfortunately we could not detect a price'

                    except:
                        ActualPrices = 'no data found on the card'



            probabilityCount = 1
            listOfSmallestDifsNames = reversed(listOfSmallestDifsNames)
            listOfSmallestDifsImages = reversed(listOfSmallestDifsImages)
            '''
            for probableCardName, probableCardImage in zip(listOfSmallestDifsNames, listOfSmallestDifsImages):
                print(f'choice number {probabilityCount} name : {probableCardName} ||'
                      f' image : {probableCardImage}')
                probabilityCount += 1
            '''
    readyTorender = True
    return render_template("pokemon.html", content=imageForlikelyPoke, content2=photoPath, readyTorender=readyTorender, pricing=ActualPrices, buyLink=buyCardURL)

@app.route("/yugioh.html")
def yugioh():
    return render_template("yugioh.html")

@app.route("/magic.html")
def magic():
    return render_template("magic.html")

if __name__ == "__main__":
    app.run()
