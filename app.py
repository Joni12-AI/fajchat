from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_session import Session
import os
from openai import OpenAI
from datetime import datetime
from flask import send_file
from io import BytesIO
from fpdf import FPDF
from dotenv import load_dotenv
import requests 
import json
import re 
from zoneinfo import ZoneInfo
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

load_dotenv()



client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# Your Assistant ID
ASSISTANT_ID = os.getenv("ASSISTANT_ID")

# Flask setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Categories for the chat interface
CATEGORIES = {
    "Air Conditioning": ["AC Repair", "AC Maintenance", "AC Cleaning Services", "AC Maintenance Contract"],
    "Coffee Machine": ["Commercial Coffee Machine Service", "Coffee Machine Service"],
    "Home Appliances": ["Hob Repair", "Washing Machine", "Dishwasher", "Oven", "Refrigerator", "Gas Range", "Vacuum Cleaner", "Integrated Appliances", "Appliances Maintenance Contract"],
    "Kitchen Appliances": ["Oven", "Hot Plate", "Pizza Oven", "Deep Fryer", "Meat Grinder", "Dough Mixer", "Food Warmer", "Kitchen Appliances AMC"],
    "Refrigeration Appliance Services": ["Ice Maker", "Freezer & Chiller", "Commercial Refrigerator", "Walk in Refrigeration Services", "Refrigeration AMC"],
    "Commercial Dishwasher": ["Commercial Dishwasher Repair"],
    "Commercial Laundry Equipments": ["Washing Machine", "Laundry Equipment Service"],
    "Small Appliances": ["Microwave", "Home Toaster", "Commercial Toaster", "Steam Iron", "Hanger Iron", "Water Heater", "Water Dispenser", "Hair Dryer", "Juicer Blender", "Electric Kettle"],
    "Other": ["General Information"]
}

def save_registration(name, phone, email):
    """Save registration data to Redis using Upstash REST API"""
    try:
        redis_key = f"user:{phone}:info"
        user_data = {
            "name": name,
            "phone": phone,
            "email": email,
            "timestamp": datetime.now(ZoneInfo("Asia/Dubai")).isoformat()
        }
        
        response = requests.post(
            f"{os.getenv('UPSTASH_REDIS_REST_URL')}/set/{redis_key}",
            headers={
                "Authorization": f"Bearer {os.getenv('UPSTASH_REDIS_REST_TOKEN')}",
                "Content-Type": "application/json"
            },
            data=json.dumps(user_data)
        )
        
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Redis registration error: {e}")
        return False

def save_chat_to_redis(name, phone, email, chat_history):
    """Save chat history to Redis using Upstash REST API"""
    try:
        redis_key = f"chat:{phone}:history"
        chat_data = {
            "name": name,
            "phone": phone,
            "email": email,
            "history": chat_history,
            "last_updated": datetime.now(ZoneInfo("Asia/Dubai")).isoformat()
        }
        
        response = requests.post(
            f"{os.getenv('UPSTASH_REDIS_REST_URL')}/set/{redis_key}",
            headers={
                "Authorization": f"Bearer {os.getenv('UPSTASH_REDIS_REST_TOKEN')}",
                "Content-Type": "application/json"
            },
            data=json.dumps(chat_data)
        )
        
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Redis save error: {e}")
        return False

def get_assistant_response(thread_id, user_input):
    """Get response from OpenAI Assistant"""
    try:
        # Add user message to the thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID
        )

        # Wait for completion
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            
            if run_status.status == "completed":
                break
            elif run_status.status in ["failed", "cancelled", "expired"]:
                raise Exception(f"Run failed with status: {run_status.status}")
            
            time.sleep(1)

        # Get the assistant's response
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        assistant_messages = [
            msg for msg in messages.data 
            if msg.role == "assistant" and msg.run_id == run.id
        ]
        
        return assistant_messages[0].content[0].text.value if assistant_messages else "No response received"

    except Exception as e:
        print(f"Assistant error: {e}")
        return "Sorry, I encountered an error. Please try again."

def get_or_create_thread():
    """Get or create a new thread for the conversation"""
    if 'thread_id' not in session:
        thread = client.beta.threads.create()
        session['thread_id'] = thread.id
    return session['thread_id']

@app.route("/", methods=["GET", "POST"])
def home():
    if not session.get("user_details"):
        return redirect(url_for("user_form"))

    user = session.get("user_details")
    if not all([user.get("first_name"), user.get("last_name"), user.get("phone"), user.get("email")]):
        return redirect(url_for("user_form"))
    
    chat_history = session.get("chat_history", [])
    thread_id = get_or_create_thread()

    if request.method == "POST":
        message = request.form["message"]
        time_now = datetime.now(ZoneInfo("Asia/Dubai")).strftime("%I:%M %p")
        chat_history.append(("You", message, time_now))

        # Category handling
        if message in CATEGORIES:
            items = CATEGORIES[message]
            is_main_menu = False
            title = f"You selected <span class='selected-item'>{message}</span>"
            prompt = "Choose a sub-category:"
        elif message == "main_menu":
            items = list(CATEGORIES.keys())
            is_main_menu = True
            title = "FAJ Technical Services"
            prompt = "Please select a service category:"
        else:
            items = None

        if items:
            response = f"""
            <div class="menu-container {'main-menu' if is_main_menu else 'sub-menu'}">
                <div class="menu-header">
                    <p class="menu-title">{title}</p>
                    <p class="menu-prompt">{prompt}</p>
                </div>
                
                <div class="menu-grid">
                    {"".join(
                        f'<button class="menu-btn" onclick="sendCategory(\'{item}\')">'
                        f'{item}'
                        f'</button>'
                        for item in items
                    )}
                </div>
                
                {'' if is_main_menu else '''
                <button class="back-btn" onclick="sendCategory(\'main_menu\')">
                    <i class="fas fa-arrow-left"></i> Back to Main Categories
                </button>
                '''}
            </div>
            """
        elif any(message in sublist for sublist in CATEGORIES.values()):
            response = f"""
            <div class="confirmation-container">
                <div class="confirmation-header">
                    <i class="fas fa-check-circle"></i>
                    <span>Service selected:</span>
                </div>
                <p class="selected-service">{message}</p>
                <p class="followup-prompt">How can we help further?</p>
                <button class="back-btn" onclick="sendCategory(\'main_menu\')">
                    <i class="fas fa-arrow-left"></i> Back to Main Categories
                </button>
            </div>
            """
        else:
            response = get_assistant_response(thread_id, message)

        chat_history.append(("Bot", response, datetime.now(ZoneInfo("Asia/Dubai")).strftime("%I:%M %p")))
        session["chat_history"] = chat_history

        save_chat_to_redis(
            f"{user['first_name']} {user['last_name']}",
            user["phone"],
            user["email"],
            chat_history
        )

    # Date header handling
    fixed_chat_history = []
    current_date = datetime.now(ZoneInfo("Asia/Dubai")).strftime("%A, %d %B %Y")
    last_date_header = session.get("last_date_header")

    if last_date_header != current_date:
        fixed_chat_history.append(("HEADER", current_date, ""))
        session["last_date_header"] = current_date

    for item in session.get("chat_history", []):
        if len(item) == 2:
            sender, message = item
            timestamp = datetime.now(ZoneInfo("Asia/Dubai")).strftime("%I:%M %p")
        else:
            sender, message, timestamp = item
        fixed_chat_history.append((sender, message, timestamp))

    session["chat_history"] = fixed_chat_history
    return render_template("chatbot-widget.html", chat_history=fixed_chat_history)

@app.route("/user_form", methods=["GET", "POST"])
def user_form():
    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        phone = request.form["phone"]
        email = request.form["email"]

        if not all([first_name, last_name, phone, email]):
            return "Please fill all required fields", 400
        
        full_name = f"{first_name} {last_name}"
        success = save_registration(full_name, phone, email)

        if success:
            subject = "New Chat Registration"
            body = f"Hello FAJ Technical Team,\n\nThe details are under as: \n{full_name}\n{phone}\n{email}\nNew chat is active Please follow up."
            send_email(subject, body, email)

        session["user_details"] = {
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "email": email
        }

        categories = list(CATEGORIES.keys())
        category_buttons = f"""
        <div class="main-categories-container">
            <p class="main-categories-header">Welcome to FAJ Technical Services</p>
            <p class="main-categories-prompt">Please select a service category:</p>
        
            <div class="main-categories-buttons">
                {"".join(
                    f'<button class="main-categories-btn" onclick="sendCategory(\'{cat}\')">{cat}</button>'
                    for cat in categories
                )}
            </div>
        </div>
        """
        session["chat_history"] = [("Bot", category_buttons)]
        return redirect(url_for("home"))

    return render_template("chatbot-widget.html")

@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    return jsonify(success=True)

def send_email(subject, body, user_email):
    smtp_server = os.getenv("SMTP_SERVER")  
    smtp_port = int(os.getenv("SMTP_PORT", 465))  
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    company_mail = "info@fajservices.ae"
    
    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = company_mail
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, company_mail, msg.as_string())
        server.quit()
        print(f"Email sent to {company_mail}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
@app.route('/download_chat')
def download_chat():
    if not session.get('user_details'):
        return redirect(url_for('user_form'))

    try:
        user = session['user_details']
        phone = user['phone']
        chat_history = session.get('chat_history', [])

        if not chat_history:
            return "No chat history available", 404

        # User Info
        user_info = {
            "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            "phone": phone,
            "email": user.get('email', '')
        }

        pdf = FPDF()
        pdf.add_page()

        # Load Unicode font
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pdf.set_font('DejaVu', '', 16)
        pdf.cell(0, 10, 'FAJ Technical Services - Chat History', 0, 1, 'C')
        pdf.ln(5)

        pdf.set_font('DejaVu', '', 12)
        pdf.cell(0, 8, f"Customer: {user_info['name']}", 0, 1)
        pdf.cell(0, 8, f"Phone: {user_info['phone']}", 0, 1)
        if user_info['email']:
            pdf.cell(0, 8, f"Email: {user_info['email']}", 0, 1)
        pdf.cell(0, 8, f"Generated on: {datetime.now(ZoneInfo('Asia/Dubai')).strftime('%Y-%m-%d %H:%M')}", 0, 1)
        pdf.ln(10)

        # Chat Transcript Header
        pdf.set_font('DejaVu', '', 14)
        pdf.cell(0, 10, 'Chat Transcript:', 0, 1)
        pdf.ln(5)

        pdf.set_font('DejaVu', '', 10)
        for entry in chat_history:
            if len(entry) < 3:
                continue
            sender, content, timestamp = entry[:3]
            if sender == "HEADER":
                continue

            clean_content = re.sub(r'<[^>]+>', '', str(content)).replace('\n', ' ').strip()
            pdf.set_font('DejaVu', '', 10)
            pdf.multi_cell(0, 6, f"{sender} ({timestamp}):\n{clean_content}")
            pdf.ln(2)

        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', user_info['name'])
        filename = f"FAJ_Chat_{safe_name}_{datetime.now(ZoneInfo('Asia/Dubai')).strftime('%Y%m%d_%H%M')}.pdf"

        pdf_bytes = pdf.output(dest='S')
        pdf_buffer = BytesIO(pdf_bytes)
        pdf_buffer.seek(0)

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        print(f"Error generating PDF: {e}")
        return "Failed to generate chat history", 500

if __name__ == "__main__":
    app.run(debug=True)
