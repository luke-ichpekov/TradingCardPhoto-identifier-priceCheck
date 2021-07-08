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
    Returns the flattened, re-sized, grayed image."""
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
    #this just transforms and flattens the card
    
    #warp = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)
    return warp


def getcardPhoto(photo):

    img = cv2.imread(photo) #reads photo
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) #grayscales the image 
    img_w, img_h = np.shape(img)[:2] #gets height and width for image
    bkg_level = gray[int(img_h / 100)][int(img_w / 2)] #does some preprocessing to the image to deal with the background
    thresh_level = bkg_level + 60 #we get the threshold level for the image, threshold sets pixels below pixel value to 0. So this level makes sure we set the background to black, so its not picked up
    blurImg = cv2.GaussianBlur(gray, (5,5), 0) #applies some gaussian blur to the image to help fade out the background
    _, thresh = cv2.threshold(blurImg, thresh_level, 255, cv2.THRESH_BINARY) #returns a tupple, first return is threshold value which is not important and second is the thresholded image, the 255 is max values that the pixels can have after threshold
    #above is where the potential errors lie for this program, image preprocessing is hit or miss and needs a lot of trial and error    
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE) #gets the contours of the image

    contourValues = []
    for i in contours:
        contourValues.append(cv2.contourArea(i))
    contourValues.sort()
    #adds all contours in the image to an array of contours

    biggestContour = 0
    bigContourIndex = len(contourValues)-1

    for b in contours:
        if cv2.contourArea(b) == contourValues[-1]:
            biggestContour = b
    #This makes sure that the last contour of the array(the biggest one) is actually the contour around the card

    #once we have contours
    if len(contourValues) != 0:
        peri = cv2.arcLength(biggestContour, True) #defines a permiter around the card
        approx = cv2.approxPolyDP(biggestContour, 0.01 * peri, True) #helps identify the rectangle that is the card
        pts = np.float32(approx)  #gets the 4 points for the rectangle
        CardCornerPoints = pts
        x, y, w, h = cv2.boundingRect(biggestContour) #highights the card and returns the x,y away from origin and width/height values for the card.
        CardWidth, CardHeight = w, h #assigning width and height
        average = np.sum(pts, axis=0)/len(pts) #finds center of the card based on the average of 4 corner points
        cent_x = int(average[0][0]) #assigns x value for center
        cent_y = int(average[0][1]) #assigns y value for center
        CardCenter = [cent_x, cent_y] #makes an array with the center
        img = flattener(img, pts, w, h) #sends image to be preprocessed farther and then flattened to 200x300 pixel image
        cv2.imwrite('camImage.png', img) #saves the newly processed image
        hashForCamImg = imagehash.phash(Image.open('camImage.png')) #gets the perceptual hash for the saved image
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
        return 'busted' #otherwise we dont detect any contours and we just return
    cv2.drawContours(img, contours, -1, (0,255,0), 3)

    #cv2.imshow('image', img)


    key = cv2.waitKey(0) #for testing locally
    cv2.destroyAllWindows() #for local testing 


app = Flask(__name__, static_url_path='') #declaring the flask application

@app.after_request
def add_header(r):
    """
    program brakes if it caches because it will cache the previous post results and it wont update,
    this removes caching so that the program will run properly
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r

@app.route("/index.html") #renders home page when logo clicked
def topLeft():
    return render_template("index.html")

@app.route("/") #renders home page
def home():
    return render_template("index.html")

@app.route("/pokemon.html") #renders pokemon page
def poke():
    return render_template("pokemon.html")


@app.route("/pokemon.html", methods=['POST']) #user sends pokemon card image
def getIMG():
    userinputImage = request.files['user_group_logo'] #gets the image that the user inputted
    readyTorender = False
    buyCardURL =''
    if userinputImage.filename == '': #this is executed if no image is sent, should render a template that says no image was detected as input
        return render_template("pokemon.html", message='no file was uploaded') #kind of like sending a prop in react 
    if userinputImage.filename != '': #user inputted an actual image
        userinputImage.save('static/assets/img/inputImageName.png') #overwrites a default saved image
        print('<----got image---->') 
        print(userinputImage.filename) #this was just for testing, to make sure it was saving properly
        photo = 'static/assets/img/inputImageName.png' #full path
        photoPath = 'assets/img/inputImageName.png'
        camHash = getcardPhoto(photo)  # this is what to use when passing in a photo, this passes to a function that returns the perceptual hash for the pokemon card

        if type(camHash) == str: #this if statement is executed if the pokemon card is not picked up at all, and then no hash is sent back.
            print('try again')
            return render_template("pokemon.html", message='unable to identify the pokemon card please try again') #this should render a template that says take a better picture

        #opens up json file with all hashes and pokemon info and instantiates some variables to use later
        with open('backupForpokeJSONUpToBW10.json') as f:
            newFileData = json.load(f)
            first = newFileData[0]
            likelyPoke = ''
            likelyId = ''
            listOfSmallestDifsNames = []
            listOfSmallestDifsImages = []
            smallestDiff = abs(camHash - imagehash.hex_to_hash(first['hash'])) #sets the initial smallest hash to the first pokemon
            for i in newFileData: #loops through entire file, checks for the smallest differences between hashes, and then adds them to the array. also gets pokemon name, id, and images
                if abs(camHash - imagehash.hex_to_hash(i['hash'])) < smallestDiff: #new info about closest match is added to the end of the array
                    likelyPoke = i['name']
                    likelyId = i['id']
                    imageForlikelyPoke = i['images']
                    imageForlikelyPoke = imageForlikelyPoke['small']
                    smallestDiff = abs(camHash - imagehash.hex_to_hash(i['hash'])) #gets the value of the closest match by substracting the input image hash-the image hash of the current pokemon in the file
                    listOfSmallestDifsNames.append(likelyPoke)
                    listOfSmallestDifsImages.append(imageForlikelyPoke)

            print(f'name: {likelyPoke}, image: {imageForlikelyPoke}, id: {likelyId}') #prings the pokemon that were most similar to the input image
            try: #gets pokemon price data
                headers = {'X-Api-Key': 'apiKeyGoesHere'}
                urlWithId = 'https://api.pokemontcg.io/v2/cards/' + likelyId
                pokePriceresponse = requests.get(urlWithId, headers=headers)
                pokemonPriceData = pokePriceresponse.json()['data']['tcgplayer']
                buyCardURL = pokemonPriceData['url']
                ActualPrices = pokemonPriceData['prices']['normal']['market']
                ActualPrices= f'market price is : {ActualPrices}$'
    
            except:
                try:
                    #incase of holofoil
                    ActualPrices= pokemonPriceData['prices']['holofoil']['market']
                    ActualPrices = f'holofoil price: {ActualPrices}$'

                except:
                    try:
                        #no price found
                        ActualPrices = 'unfortunately we could not detect a price'

                    except:
                        #no data at all found
                        ActualPrices = 'no data found on the card'



            probabilityCount = 1 #this was used when getting the most similar 5 pokemon cards, done locally but not implemented live on site
            listOfSmallestDifsNames = reversed(listOfSmallestDifsNames) #flips array to get most similar first
            listOfSmallestDifsImages = reversed(listOfSmallestDifsImages) #same thing but for images
            '''
            for probableCardName, probableCardImage in zip(listOfSmallestDifsNames, listOfSmallestDifsImages):
                print(f'choice number {probabilityCount} name : {probableCardName} ||'
                      f' image : {probableCardImage}')
                probabilityCount += 1
            '''
    readyTorender = True
    return render_template("pokemon.html", content=imageForlikelyPoke, content2=photoPath, readyTorender=readyTorender, pricing=ActualPrices, buyLink=buyCardURL) #updates all the information on the flask application

@app.route("/yugioh.html") #renders yugioh page
def yugioh():
    return render_template("yugioh.html")

@app.route("/magic.html") #renders the MTG page
def magic():
    return render_template("magic.html")

if __name__ == "__main__": #required for running flask application
    app.run()
