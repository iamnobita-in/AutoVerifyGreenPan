import json
import os
from datetime import datetime

FILE_NAME = 'premium_users.json'
ADMIN_ID = "8734310359"  # <--- Yahan apni Telegram ID daalo

def load_premium():
    if not os.path.exists(FILE_NAME): return {}
    with open(FILE_NAME, 'r') as f: return json.load(f)

def save_premium(data):
    with open(FILE_NAME, 'w') as f: json.dump(data, f, indent=4)

def is_premium(chat_id):
    data = load_premium()
    expiry = data.get(str(chat_id))
    if expiry and datetime.now().strftime('%Y-%m-%d') <= expiry:
        return True
    return False

def is_admin(chat_id):
    return str(chat_id) == ADMIN_ID
