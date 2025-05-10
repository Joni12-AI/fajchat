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

load_dotenv()

class CustomOpenAIClient(OpenAI):
    def __init__(self, *args, **kwargs):
        kwargs.pop('proxies', None)  
        super().__init__(*args, **kwargs)
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=None,          
)

# Flask setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Function to get chatbot response from OpenAI
def get_response(user_input):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for FAJ Technical Services. Only answer queries related to FAJ services like AC repair, appliances, AMC, plumbing, etc. If the query is not related, respond politely that you can only assist with FAJ Technical Services."},
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

# Save chat to CSV (Updated to include email)
# File paths
REGISTRATIONS_FILE = "registrations.csv"
CHAT_HISTORY_FILE = "chat_history.csv"

def save_registration(name, phone, email):
    """Save registration data to separate file"""
    fieldnames = ["Name", "Phone", "Email", "Timestamp"]
    row = {
        "Name": name,
        "Phone": phone,
        "Email": email,
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Check if file exists to determine if header is needed
    file_exists = os.path.exists(REGISTRATIONS_FILE)
    
    with open(REGISTRATIONS_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
# savings chats in csv file
def save_chat_to_csv(name, phone, email, chat_history):
    """Save chat history with duplicate prevention (modified from your original)"""
    existing_entries = set()

    # Load existing entries if file exists
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            for row in reader:
                if len(row) >= 6:  # Check for all columns
                    entry = (row[0], row[1], row[2], row[3], row[4], row[5])
                    existing_entries.add(entry)

    # Write to chat history file
    with open(CHAT_HISTORY_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if os.path.getsize(CHAT_HISTORY_FILE) == 0:
            writer.writerow(["Name", "Phone", "Email", "Sender", "Message", "Timestamp"])

        for item in chat_history:
            if len(item) == 3:
                sender, message, timestamp = item
            elif len(item) == 2:
                sender, message = item
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                continue
            
            # Clean HTML from messages
            clean_msg = ' '.join(str(message).split())  # Basic cleaning
            if '<' in clean_msg and '>' in clean_msg:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(clean_msg, 'html.parser')
                clean_msg = soup.get_text(separator=' ', strip=True)
            
            row = (name, phone, email, sender, clean_msg, timestamp)
            if row not in existing_entries:
                writer.writerow(row)

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
        time_now = datetime.now().strftime("%I:%M %p")
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

        chat_history.append(("Bot", response, datetime.now().strftime("%I:%M %p")))
        session["chat_history"] = chat_history

        # Save with email (FIXED)
        save_chat_to_csv(
            f"{user['first_name']} {user['last_name']}",
            user["phone"],
            user["email"],
            chat_history
        )

    # Date header handling
    fixed_chat_history = []
    current_date = datetime.now().strftime("%A, %d %B %Y")
    last_date_header = session.get("last_date_header")

    if last_date_header != current_date:
        fixed_chat_history.append(("HEADER", current_date, ""))
        session["last_date_header"] = current_date

    # Reconstruct chat history with timestamps
    for item in session.get("chat_history", []):
        if len(item) == 2:
            sender, message = item
            timestamp = datetime.now().strftime("%I:%M %p")
        else:
            sender, message, timestamp = item
        fixed_chat_history.append((sender, message, timestamp))

    session["chat_history"] = fixed_chat_history
    return render_template("index.html", chat_history=fixed_chat_history)

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
        save_registration(full_name, phone, email)

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

    return render_template("user_form.html")

@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    return jsonify(success=True)


def generate_chat_pdf(chat_history, user_info):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Add header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="FAJ Technical Services - Chat History", ln=1, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"User: {user_info['name']}", ln=1)
    pdf.cell(200, 10, txt=f"Phone: {user_info['phone']}", ln=1)
    pdf.cell(200, 10, txt=f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1)
    pdf.ln(10)
    
    # Add chat messages
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Chat Transcript:", ln=1)
    pdf.set_font("Arial", size=10)
    
    for sender, message, timestamp in chat_history:
        # Clean HTML tags from message
        clean_msg = ' '.join(message.replace('<br>', '\n').split())
        if '<' in clean_msg and '>' in clean_msg:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(clean_msg, 'html.parser')
            clean_msg = soup.get_text(separator='\n')
        
        pdf.set_fill_color(200, 220, 255) if sender == "Bot" else pdf.set_fill_color(255, 255, 255)
        pdf.multi_cell(0, 8, txt=f"{sender} ({timestamp}):\n{clean_msg}", border=1, fill=True)
        pdf.ln(2)
    
    # Save to memory buffer
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer
@app.route('/download_chat')
def download_chat():
    if not session.get('user_details'):
        return redirect(url_for('user_form'))
    
    user = session['user_details']
    name = f"{user['first_name']} {user['last_name']}"
    
    # Get chat history from CSV
    chat_history = []
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if row[0] == name and row[1] == user['phone']:
                    chat_history.append((row[3], row[4], row[5]))  # (sender, message, timestamp)
    
    # Generate PDF
    user_info = {
        'name': name,
        'phone': user['phone'],
        'email': user.get('email', '')
    }
    pdf_buffer = generate_chat_pdf(chat_history, user_info)
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"FAJ_Chat_{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
        mimetype='application/pdf'
    )

if __name__ == "__main__":
    app.run(debug=True)
