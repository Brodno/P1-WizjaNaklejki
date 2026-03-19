import time
import os
import sys

print("--- START TEST IMPORTOW ---")

def test():
    t_start = time.time()
    
    print("1. Streamlit...")
    import streamlit as st
    print(f"   OK")
    
    print("2. OpenCV (cv2)...")
    import cv2
    print(f"   OK")
    
    print("3. PyAutoGUI...")
    import pyautogui
    print(f"   OK")
    
    print("4. Vision Engine...")
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from vision_engine import AOPVision
    v = AOPVision()
    print(f"   OK")
    
    print("5. DB Manager...")
    from db_manager import VisionPrintSystem
    db = VisionPrintSystem("test_temp.db")
    print(f"   OK")
    
    print("--- WSZYSTKO OK ---")

if __name__ == "__main__":
    try:
        test()
    except Exception as e:
        print(f"BLAD: {e}")
    if os.path.exists("test_temp.db"): os.remove("test_temp.db")
