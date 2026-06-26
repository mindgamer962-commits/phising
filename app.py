from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from logic.detector import analyze_url, analyze_email, analyze_file
from logic.database import (
    init_db, store_email_scan, store_scan_log, store_feedback, 
    create_user, verify_user_login, get_all_model_history, 
    get_user_scan_history, get_user, get_dashboard_stats
)
import time
import os
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24) # Strong random key for sessions

# Initialize database
init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template('register.html')
            
        status = create_user(username, email, password)
        if status == "SUCCESS":
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        elif status == "ALREADY_EXISTS":
            flash("Registration failed. Email or username already exists.", "danger")
        elif status == "CONNECTION_ERROR":
            flash("Database connection error. Please ensure your local MySQL server is running (port 3306).", "danger")
        else:
            flash("An unexpected error occurred during registration.", "danger")
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        status, user = verify_user_login(email, password)
        if status == "SUCCESS":
            # Full login
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for('home'))
        elif status == "CONNECTION_ERROR":
            flash("Database connection error. Please ensure your local MySQL server is running.", "danger")
        else:
            flash("Invalid email or password.", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    history = get_all_model_history()
    user_scans = get_user_scan_history(session['user_id'])
    stats = get_dashboard_stats(session['user_id'])
    return render_template('dashboard.html', 
                          history=history, 
                          user_scans=user_scans,
                          stats=json.dumps(stats) if stats else None)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/what-is-phishing')
def what_is_phishing():
    return render_template('what_is_phishing.html')

@app.route('/feedback')
def feedback():
    return render_template('feedback.html')

@app.route('/api/scan/url', methods=['POST'])
def scan_url():
    data = request.json
    url = data.get('url', '')
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    # Simulate processing time
    time.sleep(1.5)
    result = analyze_url(url)
    
    # Store in database logs
    user_id = session.get('user_id')
    risk_score = float(result['score']) / 100.0
    store_scan_log('url', risk_score, result['risk_level'], identifier=url, user_id=user_id)
    
    return jsonify(result)

@app.route('/api/scan/email', methods=['POST'])
def scan_email():
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({"error": "No email content provided"}), 400
    
    # Simulate processing time
    time.sleep(1.5)
    result = analyze_email(text)
    
    # Store in database
    user_id = session.get('user_id')
    store_email_scan({
        "subject": "Email Scan", # Subject is not provided in text-only scan
        "sender": "Web Interface",
        "body": text,
        "phishing_probability": result['phishing_probability'],
        "emotional_deception_score": result['emotional_deception_score'],
        "verdict": result['risk_level'],
        "confidence": result['confidence']
    }, result['eds_breakdown'], user_id=user_id)
    
    return jsonify(result)

@app.route('/api/scan/email-file', methods=['POST'])
def scan_email_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    filename = file.filename.lower()
    content = ""
    
    try:
        if filename.endswith('.txt'):
            content = file.read().decode('utf-8', errors='ignore')
        elif filename.endswith('.eml'):
            import email
            raw_eml = file.read().decode('utf-8', errors='ignore')
            msg = email.message_from_string(raw_eml)
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
            else:
                content = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        elif filename.endswith('.msg'):
            try:
                import extract_msg
                msg = extract_msg.Message(file.read())
                content = msg.body
            except ImportError:
                return jsonify({"error": "MSG file support is not enabled. Please contact administrator to install extract-msg."}), 400
        else:
            return jsonify({"error": "Unsupported file format"}), 400
            
    except Exception as e:
        return jsonify({"error": f"Failed to parse file: {str(e)}"}), 500

    if not content.strip():
        return jsonify({"error": "Could not extract text from email file"}), 400

    # Simulate processing time
    time.sleep(1.5)
    result = analyze_email(content)
    
    # Store in database
    user_id = session.get('user_id')
    store_email_scan({
        "subject": f"File: {file.filename}",
        "sender": "Web Upload",
        "body": content[:500] + "...", # Store snippet
        "phishing_probability": result['phishing_probability'],
        "emotional_deception_score": result['emotional_deception_score'],
        "verdict": result['risk_level'],
        "confidence": result['confidence']
    }, result['eds_breakdown'], user_id=user_id)
    
    return jsonify(result)

@app.route('/api/scan/file', methods=['POST'])
def scan_file():
    # In a real app we'd handle the file upload, 
    # but based on the JS version it's just analyzing the filename
    file_name = request.json.get('fileName', '')
    if not file_name:
        return jsonify({"error": "No file name provided"}), 400
        
    # Simulate processing time
    time.sleep(1.5)
    result = analyze_file(file_name)
    
    # Store in database logs
    user_id = session.get('user_id')
    try:
        risk_score = float(result['score']) / 100.0
        store_scan_log('file', risk_score, result['risk_level'], identifier=file_name, user_id=user_id)
    except Exception as e:
        print(f"Database logging error: {e}")
    
    return jsonify(result)

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    data = request.json
    name = data.get('name', 'Anonymous')
    message = data.get('message', '')
    rating = data.get('rating', 5)
    
    if not message:
        return jsonify({"success": False, "error": "Message is required"}), 400
        
    success = store_feedback(name, message, int(rating))
    if success:
        return jsonify({"success": True, "message": "Feedback stored successfully"})
    else:
        return jsonify({"success": False, "error": "Failed to store feedback"}), 500

@app.route('/api/retrain', methods=['POST'])
def retrain_models():
    # Hidden route for triggering AI retraining
    from train_model import train_email_model, train_file_model
    try:
        e_acc, e_f1 = train_email_model()
        f_acc, f_f1 = train_file_model()
        return jsonify({
            "success": True, 
            "message": "Models retrained successfully",
            "email_accuracy": e_acc,
            "file_accuracy": f_acc
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
