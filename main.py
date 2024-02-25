import json
import requests
import io
import base64
from PIL import Image
import re
import sqlite3
from TikTokLive import TikTokLiveClient
from TikTokLive.types.events import CommentEvent, GiftEvent
from googletrans import Translator, LANGUAGES
from datetime import datetime
from queue import Queue

gift_queue = Queue()

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('tiktok_live_chat.db')
cursor = conn.cursor()

# Create table
cursor.execute('''
CREATE TABLE IF NOT EXISTS live_chat_users (
    username TEXT NOT NULL,
    user_id TEXT PRIMARY KEY,
    last_message TEXT,
    sent_gift INTEGER,
    sent_time DATETIME
)
''')
conn.commit()

url = "http://127.0.0.1:7860"

def select_gift_sent(cur):

    cur.execute("SELECT * FROM live_chat_users WHERE sent_gift > 0")

    rows = cur.fetchall()

def sanitize_prompt(prompt):
    try:
        words_to_remove = []

        # Read words from 'wordsToRemove.txt'
        with open('wordsToRemove.txt', 'r') as file:
            words_to_remove.extend(map(str.strip, file.readlines()))

        # Check for 'child' word and read from 'wordsToRemoveChild.txt' if present
        if re.search(r'\bchild\b', prompt, flags=re.IGNORECASE):
            with open('wordsToRemoveChild.txt', 'r') as child_file:
                words_to_remove.extend(map(str.strip, child_file.readlines()))

        # Generate pattern to remove specified words from the prompt
        pattern = r'\b(?:' + '|'.join(re.escape(word) for word in words_to_remove) + r')\b'
        sanitized_prompt = re.sub(pattern, '', prompt, flags=re.IGNORECASE)

        return sanitized_prompt
    except Exception as e:
        print(f'Error: {e}')
        return prompt


class CustomTikTokLiveClient(TikTokLiveClient):
    def __init__(self, unique_id: str):
        super().__init__(unique_id=unique_id)
        self.gift_sender_id = None  # Track the ID of the user who sent the gift

    def log_user_activity(self, username, user_id, message, sent_gift, sent_time):
        cursor.execute('''
        INSERT INTO live_chat_users (username, user_id, last_message, sent_gift, sent_time)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            last_message = excluded.last_message,
            sent_gift = excluded.sent_gift,
            sent_time = excluded.sent_time
        ''', (username, user_id, message, sent_gift, sent_time))
        conn.commit()

    def on_comment(self, event: CommentEvent):
        print(f"{event.user.unique_id}: {event.comment}")

        # Log every comment in the database
        current_time = datetime.now()
        self.log_user_activity(event.user.unique_id, event.user.unique_id, event.comment, False, current_time)

        # Check if the comment is from the user who last sent a gift
        if self.gift_sender_id and self.gift_sender_id == event.user.unique_id:

            # Use this comment as a prompt, as it's from the same user who sent the gift
            print(f"Using {event.comment} as prompt for gift sender: {event.user.unique_id}")
            self.gift_sender_id = None  # Reset after using the message as a prompt
            sanitized = sanitize_prompt(event.comment)

            translator = Translator()
            translatedprompt = translator.translate(sanitized, dest="en", src="tr")

            print(translatedprompt.text)

            payload = {
                "prompt": translatedprompt.text,
                "steps": 20,
                "negative_prompt": "",
                "sampler_index": "DPM++ 2M Karras",
                "width": 512,
                "height": 768
            }

            option_payload = {
                "sd_model_checkpoint": "dreamshaper_8.safetensors [879db523c3]",
                "nudenet_nsfw_censor_pixelation_factor": 6,
                "nudenet_nsfw_censor_nms_threshold": 0.5,
                "nudenet_nsfw_censor_gen_filter_type": "Fill color",
                "nudenet_nsfw_censor_live_preview_filter_type": "Fill color",
            }

            responseop = requests.post(url=f'{url}/sdapi/v1/options', json=option_payload)

            response = requests.post(url=f'{url}/sdapi/v1/txt2img', json=payload)

            r = response.json()

            image = Image.open(io.BytesIO(base64.b64decode(r['images'][0])))
            image.save('output.png')

    def on_gift(self, event: GiftEvent):
        print(f"Gift from {event.user.unique_id} and {event.gift.info.name} count as {event.gift.info.diamond_count}")
        # Store the user ID of the person who sent the gift
        self.gift_sender_id = event.user.unique_id
        # Log the gift event as true, without storing a message
        current_time = datetime.now()
        self.log_user_activity(event.user.unique_id, event.user.unique_id, "", event.gift.info.diamond_count, current_time)

# Instantiate and run the client
if __name__ == "__main__":
    a = "b"
    with open('user.txt', 'r') as file:
        a = "@" + file.read()
    client = CustomTikTokLiveClient(unique_id="gordeewa__13")
    client.on('comment', client.on_comment)
    client.on('gift', client.on_gift)
    client.run()