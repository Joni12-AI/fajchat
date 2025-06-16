from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_session import Session
import csv
import os
from openai import OpenAI
from datetime import datetime
from flask import send_file
from io import BytesIO
from fpdf import FPDF
from dotenv import load_dotenv
import requests 
import json
import redis
from flask import current_app
from io import BytesIO
import re 
from zoneinfo import ZoneInfo
from pytz import timezone 

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

load_dotenv()

class CustomOpenAIClient(OpenAI):
    def __init__(self, *args, **kwargs):
        kwargs.pop('proxies', None)  
        super().__init__(*args, **kwargs)
client = CustomOpenAIClient(
    api_key=os.getenv("OPENAI_API_KEY")
)

# Flask setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
#app.config['SESSION_TYPE'] = 'filesystem'
#Session(app)
UPSTASH_REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL") 
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

# Function to get chatbot response from OpenAI
def get_response(user_input):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages = [
    {
            "role": "system",
            "content": """You are a professional, well-informed customer support representative for FAJ Technical Services. Your role is to offer structured, accurate, and courteous assistance related to all FAJ services. Always maintain a helpful, brand-aligned tone. 

            ---

            ##Core Focus

            You specialize in the following categories:

            ### 1. Air Conditioning
            - AC Repair | AC Maintenance | Deep Cleaning | AMC (Annual Maintenance Contracts)

            ### 2. Coffee Machines
            - Commercial Coffee Machine Service | Home Coffee Machine Repair

            ### 3. Home Appliances
            - Hob | Washing Machine | Dishwasher | Oven | Refrigerator  
            - Gas Range | Vacuum Cleaner | Integrated Appliances | AMC

            ### 4. Kitchen Equipment
            - Oven | Hot Plate | Pizza Oven | Deep Fryer | Meat Grinder  
            - Dough Mixer | Food Warmer | Kitchen Equipment AMC

            ### 5. Refrigeration Equipment
            - Ice Maker | Freezer | Chiller | Commercial Refrigerator  
            - Walk-in Freezer | Refrigeration AMC

            ### 6. Commercial Equipment
            - Commercial Dishwasher | Laundry Equipment Service

            ### 7. Small Appliances
            - Microwave | Toaster | Steam Iron | Hanger Iron  
            - Water Heater | Water Dispenser | Hair Dryer  
            - Juicer | Blender | Electric Kettle

            ---

            ##Service Coverage & Availability

            - **Locations**: Dubai | Sharjah | Ajman  
            - **Timings**:  
            - Mon to Sat: 8:00 AM to 6:30 PM  
            - Sunday: 12:00 PM to 6:30 PM  

            ---

            ##Interaction Guidelines

            ### 1. Tone & Style
            - Always use complete, formal sentences.  
            - Never use emojis, slang, or casual phrases.  
            - Maintain calm, solution-oriented language.

            **Example**:  
            "Thank you for reaching out. I’ll help you with this. May I know the appliance you’re referring to?"

            ### 2. Query Handling – Step by Step 
            - **Step 1**: Ask for specific issue or symptoms.  
            - **Step 2**: Get model/brand (if unknown: "No problem, the brand will help.")
            - **Step 3**: After user provides model and issue, ask for their location (Emirate + Area).
            - **Step 4**: Once location is confirmed, ask if they prefer an on-site visit or to drop off at the service center.
            - **Step 5**: Ask if they need help with anything else before closing.


            ### 3. Pricing Policy
            Always state clearly:
            - **On-site visit**: AED 248 (includes visit + issue diagnosis)  
            - **Service center**: AED 145 (diagnostic only, drop-off required)

            ### 4. Out-of-Scope Queries
            Politely decline and redirect:

            **Response**:  
            "I handle only FAJ Technical Services support. For unrelated questions, kindly contact us at +971507464712 or via WhatsApp here: [direct link]"

            ### 5. Ending Every Interaction
            Always close with a clear action or next step:

            Examples:
            - "Would you like me to schedule a technician for you?"  
            - "Shall I share our service center address?"  
            - "May I take your location to check availability?"

            ---

            Keep interactions professional, focused, and helpful at all times.
            """
            },

            {"role": "user", "content": user_input}
        ]
    )
    return response.choices[0].message.content.strip()

CATEGORIES = {
    "Air Conditioning": ["Ac Repair", "AC Maintenance", "AC Cleaning Services", "AC Maintenace Contract"],
    "Coffee Machnine": ["Commercial Coffee Machine service", "Coffee Machine Service"],
    "Home Appliances": ["Hob Repair","Washing Machine", "Dishwasher", "Oven", "Refrigerator","Gas Range","Vaccum Cleaner","Integrated Appliances","Appliances Maintenance Contract"],
    "Kitchen Appliances": ["Oven", "Hot Plate", "Pizza Oven", "Deep Fryer", "Meat Grinder", "Dough Mixer", "Food Warmer", "Kitchen Appliances AMC"],
    "Refrigeration Appliance Services": ["Ice Maker", "Freezer & Chiller", "Commercial Refrigerator", "Walk in Refrigeration Services", "Refrigeration AMC"],
    "Commercial Dishwasher": ["Commercial Dishwasher Repair"],
    "Commercial Laundry Equipments": ["Washing Machine", "Laundry Equipment Service"],
    "Small Appliances": ["Microwave", "Home Toaster", "Commercial Toaster", "Steam Iron", "Hanger Iron", "Water Heater", "Water Dispenser", "Hair Dryer", "Juicer Blender", "Electric Kettle"],
    "Other": ["General Information"]
}

# setting time of Dubai 

# Set Dubai time
dubai_time = datetime.now(ZoneInfo("Asia/Dubai"))



redis_client = redis.Redis(
    host=UPSTASH_REDIS_URL,
    port=19563,  # Your port number from Upstash dashboard
    password=UPSTASH_TOKEN,
    ssl=True  # Required for Upstash
)


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
        
        # Use SET command via Upstash REST API
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
# savings chats in csv file
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
        
        # Use SET command via Upstash REST API
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
    
@app.route("/", methods=["GET", "POST"])
def home():
    if not session.get("user_details"):
        return redirect(url_for("user_form"))

    user = session.get("user_details")
    if not all([user.get("first_name"), user.get("last_name"), user.get("phone"), user.get("email")]):
        return redirect(url_for("user_form"))
    chat_history = session.get("chat_history", [])

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
            response = get_response(message)

        chat_history.append(("Bot", response, datetime.now(ZoneInfo("Asia/Dubai")).strftime("%I:%M %p")))
        session["chat_history"] = chat_history

        # Save with email (FIXED)
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

    # Reconstruct chat history with timestamps
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

        if not all([first_name, last_name, phone,email]):
            return "Please fill all required fields", 400
        
        full_name = f"{first_name} {last_name}"
        success = save_registration(full_name, phone, email)

        if success:
            subject = "New Chat Registration"
            body = f"Hello!! FAJ Technical Services Team,\n\nThe details are under as: \n{full_name}\n{phone}\n{email}\nNew chat is active Please follow up."
            send_email(subject, body, email)

        # Store user details with combined name
        session["user_details"] = {
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "email": email
        }

        # Initialize chat with categories
        # In your Flask code for main categories:
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

def remove_emojis(text):
    # Remove emojis
    emoji_pattern = re.compile(
        "[" 
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\U00002500-\U00002BEF"  # chinese
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    text = emoji_pattern.sub(r'', text)

    # Replace smart quotes, dashes, ellipsis etc.
    replacements = {
        "’": "'", "‘": "'",
        "“": '"', "”": '"',
        "–": "-", "—": "-", "…": "...",
        "\u00A0": " ",  # non-breaking space
        "\u200B": "",   # zero-width space
        "\u2011": "-",  # non-breaking hyphen
        "\u202F": " "   # narrow no-break space
    }

    for smart, normal in replacements.items():
        text = text.replace(smart, normal)

    return text

def generate_chat_pdf(chat_history, user_info):
    """Enhanced PDF generation with better formatting"""
    pdf = FPDF()
    pdf.add_page()
    
    # Set document properties
    pdf.set_title(f"FAJ Chat History - {user_info['name']}")
    pdf.set_author("FAJ Technical Services")
    
    # Add header
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'FAJ Technical Services - Chat History', 0, 1, 'C')
    pdf.ln(5)
    
    # User information
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f"Customer: {user_info['name']}", 0, 1)
    pdf.cell(0, 8, f"Phone: {user_info['phone']}", 0, 1)
    if user_info.get('email'):
        pdf.cell(0, 8, f"Email: {user_info['email']}", 0, 1)
    pdf.cell(0, 8, f"Generated on: {datetime.now(ZoneInfo("Asia/Dubai")).strftime('%Y-%m-%d %H:%M')}", 0, 1)
    pdf.ln(10)
    
    # Chat transcript header
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Chat Transcript:', 0, 1)
    pdf.ln(5)
    
    # Process chat messages
    pdf.set_font('Arial', '', 10)
    
    for entry in chat_history:
        if len(entry) < 3:
            continue
            
        sender, content, timestamp = entry[:3]
        if sender == "HEADER":
            continue
            
        clean_content = re.sub(r'<[^>]+>', '', str(content))
        clean_content = clean_content.replace('\n', ' ').strip()
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, f"{sender} ({timestamp}):", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, clean_content)
        pdf.ln(3)
    
    # Generate PDF in memory
    pdf_output_str = pdf.output(dest='S')  # This returns a string
    if isinstance(pdf_output_str, str):
        pdf_bytes = pdf_output_str.encode('latin1')  # Convert str to bytes
    else:
        pdf_bytes = pdf_output_str  # Already bytes in newer FPDF versions

    pdf_buffer = BytesIO(pdf_bytes)
    pdf_buffer.seek(0)
    return pdf_buffer

@app.route('/download_chat')
def download_chat():
    if not session.get('user_details'):
        return redirect(url_for('user_form'))
    
    try:
        user = session['user_details']
        phone = user['phone']
        
        # Validate phone number format
        if not phone or not isinstance(phone, str):
            raise ValueError("Invalid phone number format")
        
        # URL encode the phone number for Redis key
        encoded_phone = requests.utils.quote(phone)
        
        # Fetch chat history from Redis
        response = requests.get(
            f"{UPSTASH_REDIS_URL}/get/chat:{encoded_phone}:history",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=10  # Add timeout
        )
        
        # Handle response status
        if response.status_code == 404:
            return "No chat history found for this user", 404
        response.raise_for_status()
        
        # Parse response
        redis_data = response.json()
        if not redis_data.get('result'):
            return "No chat history available", 404
            
        try:
            chat_data = json.loads(redis_data['result'])
            chat_history = chat_data.get('history', [])
            
            if not chat_history:
                return "Empty chat history", 404
        except (json.JSONDecodeError, KeyError) as e:
            current_app.logger.error(f"Error parsing chat data: {str(e)}")
            return "Invalid chat data format", 500
        
        # Generate PDF with improved formatting
        user_info = {
            "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            "phone": phone,
            "email": user.get('email', '')
        }
        
        pdf_buffer = generate_chat_pdf(chat_history, user_info)
        
        # Create filename with sanitized user name
        safe_name = "".join(c if c.isalnum() else "_" for c in user_info['name'])
        filename = f"FAJ_Chat_{safe_name}_{datetime.now(ZoneInfo("Asia/Dubai")).strftime('%Y%m%d_%H%M')}.pdf"
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Redis connection error: {str(e)}")
        return "Failed to connect to chat storage", 503
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return "Failed to generate chat history", 500

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
        # Use SMTP_SSL for port 465
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, company_mail, msg.as_string())
        server.quit()
        print(f"Email sent to {company_mail}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

if __name__ == "__main__":
    app.run(debug=True)   
