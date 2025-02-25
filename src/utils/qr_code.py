import qrcode
import hashlib
import asyncio
import cv2
import base64
import numpy as np

class QRCode:
    """
    This class is used to generate and read QR codes.
    """

    @staticmethod
    async def hash_generator(data: str) -> str:
        """
        Generate a hash from the given data and return the hash as a string.
        """
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    async def generate_qr_code(data: str) -> str:
        """
        Generate a QR code image from the given data and return the image as a base64 string.
        """
        qr = qrcode.QRCode(
            version=6,
            error_correction=qrcode.constants.ERROR_CORRECT_Q,
            box_size=10,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill="black", back_color="white")
        return img
       
    @staticmethod
    async def read_qr_code_(encoded_str: str) -> str:
        """
        Read a QR code from a Base64-encoded image string and return the data as a string.
        """
        # Step 1: Decode the Base64 string to bytes
        image_data = base64.b64decode(encoded_str)
        
        # Step 2: Convert bytes data into a NumPy array
        nparr = np.frombuffer(image_data, np.uint8)
        
        # Step 3: Decode the image from the NumPy array
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image from the provided Base64 string")
        
        # Step 4: Use OpenCV's QRCodeDetector to detect and decode QR codes
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)
        
        if not data:
            raise ValueError("No QR code found in the image")
        
        return data
