import requests
import aiohttp
import asyncio
import time
import os
import json
from dotenv import load_dotenv
from pathlib import Path
import mimetypes
from typing import Union
load_dotenv()

# WP_ACCESS_TOKEN = os.getenv("WP_ACCESS_TOKEN")
WP_ACCESS_TOKEN = "EAAIw9doZA4gkBOyw4ysCrtBu3dUkfskwDcUdLrtsWzgCO0Ht5aNfCI8LGvfJgwFBuOnCJpHW67KDWnTw2kA6UYdCxZBZCRibuODcBmRCfdnguA98dqEXRLLeh5DrpchNnzhDVW5dTXyFauj25FJD2r4pibZBl5dzCjPu7VbjJrSTYUnZADP7QGacRbSDaioknizK57bpLc8csxEdgGHyvrZBAZD"
WP_PHONE_ID = os.getenv("WP_PHONE_ID")
WP_BID = os.getenv("WP_BID")
API_VERSION = os.getenv("API_VERSION")

async def send_whatsapp_message(recipient_number: str, template_name: str, language_code: str = "en_US") -> dict:
    """
    Send a WhatsApp message using a template through the Cloud API.
    
    Args:
        recipient_number (str): The recipient's WhatsApp number
        template_name (str): Name of the pre-approved template
        language_code (str): Language code for the template (default: en_US)
    
    Returns:
        dict: API response
    """
    url = f"https://graph.facebook.com/v21.0/{WP_PHONE_ID}/messages"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WP_ACCESS_TOKEN}"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            return await response.json()

# Example synchronous version if needed
def send_whatsapp_message_sync(recipient_number: str, template_name: str, language_code: str = "en_US") -> dict:
    """Synchronous version of send_whatsapp_message"""
    url = f"https://graph.facebook.com/v21.0/{WP_PHONE_ID}/messages"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WP_ACCESS_TOKEN}"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def upload_media(media_path: Union[str, Path]) -> str:
        """
        Upload media to WhatsApp servers and get the media ID.
        Media files are encrypted and persist for 30 days unless deleted earlier.
        
        Args:
            media_path: Path to the media file to upload
        
        Returns:
            str: The media ID returned by WhatsApp
        
        Raises:
            FileNotFoundError: If the media file doesn't exist
            ValueError: If the file type is not supported or file size exceeds limits
            requests.exceptions.HTTPError: If the upload fails
        """
        media_path = Path(media_path)
        if not media_path.exists():
            raise FileNotFoundError(f"Media file not found: {media_path}")

        # Get mime type and validate
        mime_type = mimetypes.guess_type(media_path)[0]
        if not mime_type:
            raise ValueError(f"Could not determine MIME type for file: {media_path}")

        # Check file size limits based on mime type
        file_size = media_path.stat().st_size
        size_limit = None
        
        if mime_type.startswith('audio/') or mime_type.startswith('video/'):
            size_limit = 16 * 1024 * 1024  # 16MB
        elif mime_type.startswith('image/'):
            size_limit = 5 * 1024 * 1024   # 5MB
        elif mime_type == 'image/webp':  # Sticker
            size_limit = 100 * 1024      # 100KB for static stickers
        elif mime_type.startswith('application/') or mime_type == 'text/plain':
            size_limit = 100 * 1024 * 1024  # 100MB

        if size_limit and file_size > size_limit:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds the limit "
                f"({size_limit} bytes) for type {mime_type}"
            )

        # Prepare the upload URL
        upload_url = f"https://graph.facebook.com/{API_VERSION}/{WP_PHONE_ID}/media"

        # Prepare the multipart form data
        with open(media_path, 'rb') as media_file:
            files = {
                'file': (media_path.name, media_file, mime_type)
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'type': mime_type
            }
            
            try:
                response = requests.post(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {WP_ACCESS_TOKEN}"
                    },
                    files=files,
                    data=data
                )
                response.raise_for_status()
                
                result = response.json()
                media_id = result.get('id')
                if not media_id:
                    raise ValueError("No media ID in response")
                    
                print(f"Successfully uploaded media file: {media_path.name} (ID: {media_id})")
                return media_id
                
            except requests.exceptions.HTTPError as http_err:
                print(
                    f"HTTP error occurred while uploading media: {http_err} - Response: {response.text}"
                )
                raise
            except Exception as err:
                print(f"Unexpected error occurred while uploading media: {err}")
                raise



# Example usage
if __name__ == "__main__":

    # recipient_number = "573168227670"
    # template_name = "sample_movie_ticket_confirmation"
    # language_code = "en_US"
    # response = send_whatsapp_message_sync(recipient_number, template_name, language_code)
    # print(json.dumps(response, indent=4))
    test_path = Path("/mnt/c/Users/Lenovo/Downloads/141153441343.pdf")
    print(f"Path exists: {test_path.exists()}")
    media_id = upload_media(test_path)
    print(media_id)
    print ("Probango Git")
