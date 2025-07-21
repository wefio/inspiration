#人脸采集模块
import cv2
import os
import numpy as np

def detect_face(retval, image,count=0):
    if retval == True:
        face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(image)

        num = 0
        for (x, y, w, h) in faces:
            img_copied = image[y:y+h, x:x+w]
            img_resized = cv2.resize(img_copied, (200, 200))
            num += 1
            cv2.imwrite('faces/face'f'{count}'+'_'+f'{num}'+'.jpg', img_resized)
            cv2.rectangle(image, (x, y), (x + w, y + h), color=(255, 0, 0), thickness=2)
        print('faces/face'f'{count}'+'_'+f'{num}'+'.jpg')
        cv2.imshow("Face Detection", image)
        cv2.waitKey(2000)  # wait 2 seconds        
    else:          
        raise Exception("Could not read image")
    
#camera
def camera_open():
    camera = cv2.VideoCapture(0)
    # 检查摄像头是否打开
    if not camera.isOpened():
        raise Exception("Could not open video device")
    else:
        print("camera is opened")
        retval, image = camera.read()
        count = 0
        while count < 5:
            detect_face(retval, image, count)
            print(f"Captured {count} images")
            count += 1
        if count == 5:
            print("completed")
        camera.release()

# image
def file_open(folder='meixi'):
    if not os.path.exists(folder):
        raise FileNotFoundError(f"'{folder}' not found. Please provide a valid folder path.")
    
    os.makedirs('faces', exist_ok=True)
    processed = 0
    count = 0

    for filename in os.listdir(folder):
        if filename.lower().endswith(('.jpg')):
            filepath = os.path.join(folder, filename)
            image = cv2.imread(filepath)
            if image is not None:
                print(f"running: {filename}")
                detect_face(True, image,count)
                processed += 1
                count += 1
                print(f"Captured {processed} images")
            else:
                print(f"Could not read image: {filename}")

def main(function:str):
    if function == 'camera':
        camera_open()
    elif function == 'file':
        file_open()
    else:
        raise ValueError("Invalid function argument. Use 'camera' or 'file'.")

if __name__ == "__main__":
    main('file')    # 'camera' or 'file'
    cv2.destroyAllWindows()

