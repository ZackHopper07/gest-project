import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import webbrowser
import ctypes
import time
import tkinter as tk
from tkinter import messagebox
import os
import subprocess

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


landmark_drawing_spec = mp_draw.DrawingSpec(color=(0, 255, 0), thickness=3, circle_radius=4)
connection_drawing_spec = mp_draw.DrawingSpec(color=(255, 0, 0), thickness=3)


hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,  
    min_tracking_confidence=0.5  
)

screen_width, screen_height = pyautogui.size()
print(f"Screen size: {screen_width}x{screen_height}")
camera = cv2.VideoCapture(0)
x1 = y1 = x2 = y2 = 0
if not camera.isOpened():
    print("Error: Could not open camera")
    exit()
else:
    print("Camera opened successfully")

prev_x, prev_y = 0, 0
smooth_factor = 0.5
v_sign_detected = False
v_sign_cooldown = 0
l_sign_detected = False
l_sign_cooldown = 0
five_finger_detected = False
five_finger_cooldown = 0
sleep_confirmed = False
sleep_confirmation_time = 0
prev_index_y = 0
prev_middle_y = 0
swipe_cooldown = 0

def show_sleep_confirmation():
    root = tk.Tk()
    root.withdraw() 
    root.attributes('-topmost', True)  
    result = messagebox.askyesno("Sleep Mode", "Do you want to put the computer to sleep?")
    root.destroy()
    return result

def put_pc_to_sleep():
    try:
        print("Attempting to put PC to sleep...")
      
        try:
         
            subprocess.run(['shutdown', '/h'], shell=True)
            print("Sleep command executed successfully")
        except Exception as e1:
            print(f"First sleep attempt failed: {e1}")
            try:
                ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
                print("Sleep command executed using powrprof")
            except Exception as e2:
                print(f"Second sleep attempt failed: {e2}")
                try:
                    subprocess.run(['rundll32.exe', 'powrprof.dll,SetSuspendState', '0,1,0'], shell=True)
                    print("Sleep command executed using rundll32")
                except Exception as e3:
                    print(f"Third sleep attempt failed: {e3}")
    except Exception as e:
        print(f"All sleep attempts failed: {e}")

def draw_gesture_info(image, gesture_name, confidence):
    overlay = image.copy()
    cv2.rectangle(overlay, (10, 10), (400, 120), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, image, 0.3, 0, image)
    
    cv2.putText(image, f"Gesture: {gesture_name}", (20, 35), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(image, f"Confidence: {confidence:.2f}", (20, 55), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(image, f"Cooldown: {v_sign_cooldown}", (20, 75), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(image, "Make sure your hand is clearly visible", (20, 95), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

def print_gesture_debug(landmarks, gesture_name):
    print(f"\n=== {gesture_name} Debug Info ===")
    print(f"Index finger: {landmarks[8].y:.3f}")
    print(f"Middle finger: {landmarks[12].y:.3f}")
    print(f"Ring finger: {landmarks[16].y:.3f}")
    print(f"Pinky finger: {landmarks[20].y:.3f}")
    print(f"Thumb: {landmarks[4].y:.3f}")
    print("===========================\n")

def get_finger_state(landmarks, finger_tip_id, finger_base_id):
    tip = landmarks[finger_tip_id].y
    base = landmarks[finger_base_id].y
    return tip < base - 0.1


def is_five_fingers_open(landmarks):
    thumb_tip = landmarks[4].y
    index_tip = landmarks[8].y
    middle_tip = landmarks[12].y
    ring_tip = landmarks[16].y
    pinky_tip = landmarks[20].y
    
    thumb_base = landmarks[2].y
    index_base = landmarks[6].y
    middle_base = landmarks[10].y
    ring_base = landmarks[14].y
    pinky_base = landmarks[18].y

    
    thumb_up = thumb_tip < thumb_base - 0.05 
    index_up = index_tip < index_base - 0.05  
    middle_up = middle_tip < middle_base - 0.05  
    ring_up = ring_tip < ring_base - 0.05  
    pinky_up = pinky_tip < pinky_base - 0.05  
    
    
    fingers_spread = (
        abs(landmarks[8].x - landmarks[12].x) > 0.05 and  
        abs(landmarks[12].x - landmarks[16].x) > 0.05 and  
        abs(landmarks[16].x - landmarks[20].x) > 0.05  
    )
    
    return thumb_up and index_up and middle_up and ring_up and pinky_up and fingers_spread

def is_thumbs_up(landmarks):
    thumb_tip = landmarks[4].y
    index_tip = landmarks[8].y
    middle_tip = landmarks[12].y
    ring_tip = landmarks[16].y
    pinky_tip = landmarks[20].y
    
    thumb_base = landmarks[2].y
    index_base = landmarks[6].y
    middle_base = landmarks[10].y
    ring_base = landmarks[14].y
    pinky_base = landmarks[18].y

    thumb_up = thumb_tip < thumb_base - 0.1  
    index_down = index_tip > index_base + 0.05
    middle_down = middle_tip > middle_base + 0.05
    ring_down = ring_tip > ring_base + 0.05
    pinky_down = pinky_tip > pinky_base + 0.05
    
    thumb_angle = abs(landmarks[4].x - landmarks[2].x) < 0.3  
    thumb_height = landmarks[4].y < landmarks[2].y - 0.2  
    
    thumb_above_others = (
        thumb_tip < index_tip and
        thumb_tip < middle_tip and
        thumb_tip < ring_tip and
        thumb_tip < pinky_tip
    )
    
    return (thumb_up and index_down and middle_down and ring_down and pinky_down and 
            thumb_angle and thumb_height and thumb_above_others)

def is_v_sign(landmarks):
 
    index_tip = landmarks[8].y
    middle_tip = landmarks[12].y
    ring_tip = landmarks[16].y
    pinky_tip = landmarks[20].y
    
    index_base = landmarks[6].y
    middle_base = landmarks[10].y
    ring_base = landmarks[14].y
    pinky_base = landmarks[18].y

    
    index_up = index_tip < index_base - 0.05 
    middle_up = middle_tip < middle_base - 0.05  
    ring_down = ring_tip > ring_base + 0.05  
    pinky_down = pinky_tip > pinky_base + 0.05  
    
   
    v_angle = abs(landmarks[8].x - landmarks[12].x) > 0.05 
    fingers_height = abs(landmarks[8].y - landmarks[12].y) < 0.2  
    
    return index_up and middle_up and ring_down and pinky_down and v_angle and fingers_height

def is_l_sign(landmarks):
    thumb_tip = landmarks[4].y
    index_tip = landmarks[8].y
    middle_tip = landmarks[12].y
    ring_tip = landmarks[16].y
    pinky_tip = landmarks[20].y
    
    thumb_base = landmarks[2].y
    index_base = landmarks[6].y
    middle_base = landmarks[10].y
    ring_base = landmarks[14].y
    pinky_base = landmarks[18].y

    
    thumb_up = thumb_tip < thumb_base - 0.05  
    index_up = index_tip < index_base - 0.05 
    middle_down = middle_tip > middle_base + 0.05  
    ring_down = ring_tip > ring_base + 0.05  
    pinky_down = pinky_tip > pinky_base + 0.05  
    

    l_angle = abs(landmarks[4].x - landmarks[8].x) > 0.05 
    fingers_height = abs(landmarks[4].y - landmarks[8].y) < 0.2  
    
    return thumb_up and index_up and middle_down and ring_down and pinky_down and l_angle and fingers_height

def is_four_fingers_up(landmarks):
    thumb_tip = landmarks[4].y
    index_tip = landmarks[8].y
    middle_tip = landmarks[12].y
    ring_tip = landmarks[16].y
    pinky_tip = landmarks[20].y
    
    thumb_base = landmarks[2].y
    index_base = landmarks[6].y
    middle_base = landmarks[10].y
    ring_base = landmarks[14].y
    pinky_base = landmarks[18].y

    thumb_down = thumb_tip > thumb_base + 0.02 
    index_up = index_tip < index_base - 0.02  
    middle_up = middle_tip < middle_base - 0.02
    ring_up = ring_tip < ring_base - 0.02     
    pinky_up = pinky_tip < pinky_base - 0.02   
  
    fingers_spread = (
        abs(landmarks[8].x - landmarks[12].x) > 0.02 and
        abs(landmarks[12].x - landmarks[16].x) > 0.02 and
        abs(landmarks[16].x - landmarks[20].x) > 0.02
    )
    
  
    fingers_height = (
        abs(landmarks[8].y - landmarks[12].y) < 0.1 and
        abs(landmarks[12].y - landmarks[16].y) < 0.1 and
        abs(landmarks[16].y - landmarks[20].y) < 0.1
    )
    
    return (thumb_down and index_up and middle_up and ring_up and pinky_up and 
            fingers_spread and fingers_height)

while True:
    ret, image = camera.read()
    image_height, image_width, _ = image.shape
    
    if not ret:
        print("Error: Could not read frame from camera")
        break
        
    image = cv2.flip(image, 1)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    output_hands = hands.process(image_rgb)
    all_hands = output_hands.multi_hand_landmarks
    
    cv2.rectangle(image, (0, 0), (image_width, image_height), (0, 255, 0), 2)
    
    if all_hands: 
        for hand in all_hands:
            mp_draw.draw_landmarks(
                image=image,
                landmark_list=hand,
                connections=mp_hands.HAND_CONNECTIONS,
                landmark_drawing_spec=landmark_drawing_spec,
                connection_drawing_spec=connection_drawing_spec
            )
            
            one_hand_landmarks = hand.landmark
            
            cv2.putText(image, "Hand Detected", (image_width - 200, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            if is_v_sign(one_hand_landmarks):
                print_gesture_debug(one_hand_landmarks, "V Sign")
                if not v_sign_detected and v_sign_cooldown == 0:
                    v_sign_detected = True
                    v_sign_cooldown = 70
                    print("V sign detected! Opening YouTube...")
                    webbrowser.open('https://www.youtube.com')
                    draw_gesture_info(image, "V Sign", 1.0)
            else:
                v_sign_detected = False
                
            if is_l_sign(one_hand_landmarks):
                print_gesture_debug(one_hand_landmarks, "L Sign")
                if not l_sign_detected and l_sign_cooldown == 0:
                    l_sign_detected = True
                    l_sign_cooldown = 70
                    print("L sign detected! Opening Tinkercad...")
                    webbrowser.open('https://www.tinkercad.com/dashboard')
                    draw_gesture_info(image, "L Sign", 1.0)
            else:
                l_sign_detected = False
            #if is_1_hand_sign(one_hand_landmarks:
                #print_gesture_debug(one_hand_landmarks)
                #if not 1_hand_detected and 1_hand_cooldown ==0:
                    #1_hand_detected = True
                    #1_hand_cooldown = 70 
                    #print("1 hand detected! ")

            if is_five_fingers_open(one_hand_landmarks):
                print_gesture_debug(one_hand_landmarks, "Five Fingers")
                if not five_finger_detected and five_finger_cooldown == 0:
                    five_finger_detected = True
                    five_finger_cooldown = 70
                    print("Five fingers detected! Showing sleep confirmation dialog...")
                    draw_gesture_info(image, "Five Fingers - Sleep Confirmation", 1.0)
                    if show_sleep_confirmation():
                        print("Sleep confirmed! Putting computer to sleep...")
                        put_pc_to_sleep()
                    else:
                        print("Sleep cancelled by user")
            else:
                five_finger_detected = False

    else:
        cv2.putText(image, "No Hand Detected", (image_width - 200, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    if v_sign_cooldown > 0:
        v_sign_cooldown -= 1
    if l_sign_cooldown > 0:
        l_sign_cooldown -= 1
    if five_finger_cooldown > 0:
        five_finger_cooldown -= 1
    if swipe_cooldown > 0:
        swipe_cooldown -= 1
    
    cv2.imshow("Gesture Control", image)
    key = cv2.waitKey(100)
    if key == 27:
        break

camera.release()
cv2.destroyAllWindows()