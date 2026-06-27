import os
import sqlite3
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

load_dotenv()

# Conditional import for MySQL
try:
    import mysql.connector
    from mysql.connector import errorcode
    MYSQL_AVAILABLE = True
    DB_ERRORS = (sqlite3.Error, mysql.connector.Error)
except ImportError:
    MYSQL_AVAILABLE = False
    errorcode = None
    DB_ERRORS = (sqlite3.Error,)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def parse_datetime(val):
    if not isinstance(val, str):
        return val
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d'):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return val

class SQLiteCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        
    def execute(self, query, params=None):
        # Translate placeholder %s to ? for SQLite
        query = query.replace('%s', '?')
        if params is not None:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
            
    def fetchone(self):
        row = self.cursor.fetchone()
        if not row:
            return None
        return self._process_row(row)
        
    def fetchall(self):
        rows = self.cursor.fetchall()
        return [self._process_row(r) for r in rows]
        
    def _process_row(self, row):
        desc = self.cursor.description
        if not desc:
            return row
            
        if isinstance(row, dict):
            new_row = {}
            for col_name, val in row.items():
                if col_name in ('created_at', 'training_date', 'uploaded_at') or col_name.endswith('_at') or col_name.endswith('_date'):
                    new_row[col_name] = parse_datetime(val)
                else:
                    new_row[col_name] = val
            return new_row
        else:
            new_row = []
            for i, val in enumerate(row):
                col_name = desc[i][0]
                if col_name in ('created_at', 'training_date', 'uploaded_at') or col_name.endswith('_at') or col_name.endswith('_date'):
                    new_row.append(parse_datetime(val))
                else:
                    new_row.append(val)
            return tuple(new_row)
            
    def close(self):
        self.cursor.close()
        
    @property
    def lastrowid(self):
        return self.cursor.lastrowid

class SQLiteConnection:
    def __init__(self, conn):
        self.conn = conn
        
    def cursor(self, dictionary=False):
        if dictionary:
            self.conn.row_factory = dict_factory
        else:
            self.conn.row_factory = None
        return SQLiteCursor(self.conn.cursor())
        
    def commit(self):
        self.conn.commit()
        
    def rollback(self):
        self.conn.rollback()
        
    def close(self):
        self.conn.close()

def get_db_connection():
    """Establishes and returns a connection to the database (SQLite or MySQL)."""
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    
    if db_type == 'sqlite':
        import sqlite3
        db_name = os.getenv('DB_NAME', 'database.db')
        # Vercel filesystem is read-only except for /tmp.
        # Redirect sqlite database to /tmp/database.db when running on Vercel.
        if os.getenv('VERCEL') or os.getenv('VERCEL_ENV'):
            db_name = '/tmp/database.db'
            
        try:
            conn = sqlite3.connect(db_name)
            conn.execute("PRAGMA foreign_keys = ON")
            return SQLiteConnection(conn)
        except sqlite3.Error as err:
            print(f"DEBUG: SQLite connection failed: {err}")
            return None
            
    # MySQL Database Connection
    if not MYSQL_AVAILABLE:
        print("ERROR: mysql-connector-python is not installed, but DB_TYPE is set to mysql.")
        return None
        
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'ped_eds_db')
        )
        return conn
    except mysql.connector.Error as err:
        print(f"DEBUG: get_db_connection failed: {err}")
        if errorcode and err.errno == errorcode.ER_BAD_DB_ERROR:
            # Create database if it doesn't exist
            print("DEBUG: Database not found, creating...")
            return create_database()
        else:
            print(f"DEBUG: Critical Connection Error: {err}")
            return None

def create_database():
    """Creates the MySQL database and returns a connection."""
    if not MYSQL_AVAILABLE:
        return None
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '')
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {os.getenv('DB_NAME', 'ped_eds_db')}")
        conn.database = os.getenv('DB_NAME', 'ped_eds_db')
        return conn
    except mysql.connector.Error as err:
        print(f"Failed creating database: {err}")
        return None

def init_db():
    """Initializes the database schema."""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    tables = {}
    
    if db_type == 'sqlite':
        tables['emails'] = (
            "CREATE TABLE IF NOT EXISTS emails ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  user_id INTEGER,"
            "  subject TEXT,"
            "  sender TEXT,"
            "  body TEXT,"
            "  phishing_probability REAL,"
            "  emotional_deception_score REAL,"
            "  verdict TEXT,"
            "  confidence REAL,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        tables['emotion_scores'] = (
            "CREATE TABLE IF NOT EXISTS emotion_scores ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  email_id INTEGER,"
            "  fear REAL,"
            "  urgency REAL,"
            "  trust REAL,"
            "  greed REAL,"
            "  authority REAL,"
            "  FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE"
            ")"
        )
        tables['training_data'] = (
            "CREATE TABLE IF NOT EXISTS training_data ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  text TEXT,"
            "  label TEXT,"
            "  dataset_version TEXT,"
            "  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        tables['scan_logs'] = (
            "CREATE TABLE IF NOT EXISTS scan_logs ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  user_id INTEGER,"
            "  scan_type TEXT,"
            "  identifier TEXT,"
            "  risk_score REAL,"
            "  verdict TEXT,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        tables['feedback'] = (
            "CREATE TABLE IF NOT EXISTS feedback ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  name TEXT,"
            "  message TEXT,"
            "  rating INTEGER,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        tables['users'] = (
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  email TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        tables['model_history'] = (
            "CREATE TABLE IF NOT EXISTS model_history ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  model_type TEXT,"
            "  version TEXT,"
            "  accuracy REAL,"
            "  f1_score REAL,"
            "  training_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "  active_status BOOLEAN DEFAULT 1"
            ")"
        )
    else:
        # Updated emails table with user_id
        tables['emails'] = (
            "CREATE TABLE IF NOT EXISTS emails ("
            "  id INT AUTO_INCREMENT PRIMARY KEY,"
            "  user_id INT NULL,"
            "  subject TEXT,"
            "  sender VARCHAR(255),"
            "  body LONGTEXT,"
            "  phishing_probability FLOAT,"
            "  emotional_deception_score FLOAT,"
            "  verdict VARCHAR(50),"
            "  confidence FLOAT,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "  INDEX idx_sender (sender),"
            "  INDEX idx_verdict (verdict),"
            "  INDEX idx_user_id (user_id)"
            ") ENGINE=InnoDB"
        )
        
        tables['emotion_scores'] = (
            "CREATE TABLE IF NOT EXISTS emotion_scores ("
            "  id INT AUTO_INCREMENT PRIMARY KEY,"
            "  email_id INT,"
            "  fear FLOAT,"
            "  urgency FLOAT,"
            "  trust FLOAT,"
            "  greed FLOAT,"
            "  authority FLOAT,"
            "  FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE"
            ") ENGINE=InnoDB"
        )
        
        tables['training_data'] = (
            "CREATE TABLE IF NOT EXISTS training_data ("
            "  id INT AUTO_INCREMENT PRIMARY KEY,"
            "  text LONGTEXT,"
            "  label VARCHAR(50),"
            "  dataset_version VARCHAR(50),"
            "  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ") ENGINE=InnoDB"
        )
        
        # Updated scan_logs with user_id and identifier
        tables['scan_logs'] = (
            "CREATE TABLE IF NOT EXISTS scan_logs ("
            "  id INT AUTO_INCREMENT PRIMARY KEY,"
            "  user_id INT NULL,"
            "  scan_type VARCHAR(50),"
            "  identifier TEXT NULL,"
            "  risk_score FLOAT,"
            "  verdict VARCHAR(50),"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "  INDEX idx_scan_type (scan_type),"
            "  INDEX idx_created_at (created_at),"
            "  INDEX idx_user_id (user_id)"
            ") ENGINE=InnoDB"
        )
        
        tables['feedback'] = (
            "CREATE TABLE IF NOT EXISTS feedback ("
            "  id INT AUTO_INCREMENT PRIMARY KEY,"
            "  name VARCHAR(255),"
            "  message TEXT,"
            "  rating INT,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ") ENGINE=InnoDB"
        )

        # Basic users table without MFA
        tables['users'] = (
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INT AUTO_INCREMENT PRIMARY KEY,"
            "  username VARCHAR(255) NOT NULL UNIQUE,"
            "  email VARCHAR(255) NOT NULL UNIQUE,"
            "  password_hash VARCHAR(255) NOT NULL,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ") ENGINE=InnoDB"
        )

        tables['model_history'] = (
            "CREATE TABLE IF NOT EXISTS model_history ("
            "  id INT AUTO_INCREMENT PRIMARY KEY,"
            "  model_type VARCHAR(50),"
            "  version VARCHAR(50),"
            "  accuracy FLOAT,"
            "  f1_score FLOAT,"
            "  training_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "  active_status BOOLEAN DEFAULT TRUE"
            ") ENGINE=InnoDB"
        )
        
    for table_name in tables:
        table_description = tables[table_name]
        try:
            print(f"Creating table {table_name}: ", end='')
            cursor.execute(table_description)
            print("OK")
        except Exception as err:
            if errorcode and hasattr(err, 'errno') and err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                # Check if we need to update existing tables (Simple approach)
                if table_name == 'emails':
                    try:
                        cursor.execute("ALTER TABLE emails ADD COLUMN IF NOT EXISTS user_id INT NULL")
                        cursor.execute("ALTER TABLE emails ADD INDEX IF NOT EXISTS idx_user_id (user_id)")
                    except: pass
                if table_name == 'scan_logs':
                    try:
                        cursor.execute("ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS user_id INT NULL")
                        cursor.execute("ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS identifier TEXT NULL")
                        cursor.execute("ALTER TABLE scan_logs ADD INDEX IF NOT EXISTS idx_user_id (user_id)")
                    except: pass
                print("already exists/updated.")
            else:
                print(f"already exists/updated or error: {err}")

    cursor.close()
    conn.close()
    return True

def store_email_scan(data, emotion_breakdown, user_id=None):
    """Stores email scan results and emotion scores with user association."""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    
    # Store email
    add_email = (
        "INSERT INTO emails "
        "(user_id, subject, sender, body, phishing_probability, emotional_deception_score, verdict, confidence) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )
    email_data = (
        user_id,
        data.get('subject', 'Unknown Subject'),
        data.get('sender', 'Unknown Sender'),
        data.get('body', ''),
        data.get('phishing_probability', 0.0),
        data.get('emotional_deception_score', 0.0),
        data.get('verdict', 'safe'),
        data.get('confidence', 0.0)
    )
    
    try:
        cursor.execute(add_email, email_data)
        email_id = cursor.lastrowid
        
        # Store emotion scores
        add_emotions = (
            "INSERT INTO emotion_scores "
            "(email_id, fear, urgency, trust, greed, authority) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        emotion_data = (
            email_id,
            emotion_breakdown.get('fear', 0.0),
            emotion_breakdown.get('urgency', 0.0),
            emotion_breakdown.get('trust', 0.0),
            emotion_breakdown.get('greed', 0.0),
            emotion_breakdown.get('authority', 0.0)
        )
        cursor.execute(add_emotions, emotion_data)
        
        conn.commit()
        return email_id
    except DB_ERRORS as err:
        print(f"Error storing email scan: {err}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()

def store_scan_log(scan_type, risk_score, verdict, identifier=None, user_id=None):
    """Stores a log of a URL or File scan with user association."""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    add_log = (
        "INSERT INTO scan_logs "
        "(user_id, scan_type, identifier, risk_score, verdict) "
        "VALUES (%s, %s, %s, %s, %s)"
    )
    log_data = (user_id, scan_type, identifier, risk_score, verdict)
    
    try:
        cursor.execute(add_log, log_data)
        conn.commit()
        return True
    except DB_ERRORS as err:
        print(f"Error storing scan log: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

def store_feedback(name, message, rating):
    """Stores user feedback."""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    add_feedback = (
        "INSERT INTO feedback "
        "(name, message, rating) "
        "VALUES (%s, %s, %s)"
    )
    feedback_data = (name, message, rating)
    
    try:
        cursor.execute(add_feedback, feedback_data)
        conn.commit()
        return True
    except DB_ERRORS as err:
        print(f"Error storing feedback: {err}")
        return False
    finally:
        cursor.close()
        conn.close()


def create_user(username, email, password):
    """Creates a new user account with a hashed password. Returns status code."""
    conn = get_db_connection()
    if not conn:
        return "CONNECTION_ERROR"
    
    # Hash the password
    password_hash = generate_password_hash(password)
    
    cursor = conn.cursor()
    add_user = (
        "INSERT INTO users "
        "(username, email, password_hash) "
        "VALUES (%s, %s, %s)"
    )
    data = (username, email, password_hash)
    
    try:
        cursor.execute(add_user, data)
        conn.commit()
        return "SUCCESS"
    except DB_ERRORS as err:
        print(f"Error creating user: {err}")
        err_msg = str(err).lower()
        if "duplicate" in err_msg or "unique constraint failed" in err_msg or (errorcode and hasattr(err, 'errno') and err.errno == errorcode.ER_DUP_ENTRY):
            return "ALREADY_EXISTS"
        return "ERROR"
    finally:
        cursor.close()
        conn.close()

def get_user(email):
    """Retrieves a user by email."""
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM users WHERE email = %s"
    
    try:
        cursor.execute(query, (email,))
        user = cursor.fetchone()
        return user
    except DB_ERRORS as err:
        print(f"Error fetching user: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

def verify_user_login(email, password):
    """Verifies user credentials. Returns (status, user_object)."""
    user = get_user(email)
    if user is None:
        # Check if specifically a connection error or just user not found
        conn = get_db_connection()
        if not conn:
            return "CONNECTION_ERROR", None
        return "INVALID_CREDENTIALS", None
        
    if check_password_hash(user['password_hash'], password):
        return "SUCCESS", user
    return "INVALID_CREDENTIALS", None


def get_all_model_history():
    """Retrieves all AI model performance records."""
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM model_history ORDER BY training_date DESC"
    
    try:
        cursor.execute(query)
        return cursor.fetchall()
    except DB_ERRORS as err:
        print(f"Error fetching model history: {err}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_user_scan_history(user_id):
    """Retrieves personalized scan history for a user."""
    conn = get_db_connection()
    if not conn:
        return []
    
    cursor = conn.cursor(dictionary=True)
    # Combine emails and scan_logs (simplified approach)
    query = (
        "SELECT 'email' as type, id, subject as identifier, verdict, created_at, phishing_probability as score "
        "FROM emails WHERE user_id = %s "
        "UNION ALL "
        "SELECT scan_type as type, id, identifier as identifier, verdict, created_at, risk_score as score "
        "FROM scan_logs WHERE user_id = %s "
        "ORDER BY created_at DESC"
    )
    
    try:
        cursor.execute(query, (user_id, user_id))
        return cursor.fetchall()
    except DB_ERRORS as err:
        print(f"Error fetching scan history: {err}")
        return []
    finally:
        cursor.close()
        conn.close()

def log_model_performance(model_type, version, accuracy, f1_score):
    """Logs a new AI model performance record."""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    add_history = (
        "INSERT INTO model_history "
        "(model_type, version, accuracy, f1_score, training_date) "
        "VALUES (%s, %s, %s, %s, %s)"
    )
    
    # Deactivate previous versions for this model type
    try:
        cursor.execute("UPDATE model_history SET active_status = FALSE WHERE model_type = %s", (model_type,))
        
        data = (model_type, version, accuracy, f1_score, datetime.now())
        cursor.execute(add_history, data)
        conn.commit()
        return True
    except DB_ERRORS as err:
        print(f"Error logging model history: {err}")
        return False
    finally:
        cursor.close()
        conn.close()


def get_dashboard_stats(user_id):
    """Aggregates statistics for dashboard charts."""
    conn = get_db_connection()
    if not conn:
        return None
    
    stats = {
        'kpis': {
            'total_scans': 0,
            'threats_blocked': 0,
            'avg_risk': 0,
            'system_accuracy': 0.94 
        },
        'phishing_vs_legitimate': {'phishing': 0, 'legitimate': 0},
        'scan_distribution': {'url': 0, 'email': 0, 'file': 0},
        'scans_over_time': {'labels': [], 'data': []},
        'risk_distribution': {'low': 0, 'medium': 0, 'high': 0},
        'top_indicators': {'labels': ['Fear', 'Urgency', 'Trust', 'Greed', 'Authority'], 'data': [0, 0, 0, 0, 0]}
    }
    
    cursor = conn.cursor(dictionary=True)
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    
    try:
        # Fetch current system accuracy from model history
        cursor.execute("SELECT accuracy FROM model_history WHERE active_status = TRUE LIMIT 1")
        model_row = cursor.fetchone()
        if model_row:
            stats['kpis']['system_accuracy'] = round(float(model_row['accuracy']), 4)

        # 1. Combined Scans Data
        query_combined = (
            "SELECT type, verdict, score, created_at FROM ("
            "  SELECT 'email' as type, verdict, phishing_probability as score, created_at FROM emails WHERE user_id = %s "
            "  UNION ALL "
            "  SELECT scan_type as type, verdict, risk_score as score, created_at FROM scan_logs WHERE user_id = %s"
            ") as combined"
        )
        cursor.execute(query_combined, (user_id, user_id))
        rows = cursor.fetchall()
        
        total_risk_sum = 0
        for row in rows:
            stats['kpis']['total_scans'] += 1
            score = float(row['score'])
            if score > 1.0: # Normalize legacy 0-100 scores
                score = score / 100.0
                
            total_risk_sum += (score * 100)
            
            # Phishing vs Legitimate
            if row['verdict'] in ['danger', 'phishing', 'High Risk', 'high']:
                stats['phishing_vs_legitimate']['phishing'] += 1
                stats['kpis']['threats_blocked'] += 1
            elif row['verdict'] in ['safe', 'Safe']:
                stats['phishing_vs_legitimate']['legitimate'] += 1
                
            # Scan Distribution
            s_type = row['type']
            if s_type in stats['scan_distribution']:
                stats['scan_distribution'][s_type] += 1
                
            # Risk Distribution
            display_score = score * 100
            if display_score < 30:
                stats['risk_distribution']['low'] += 1
            elif display_score < 70:
                stats['risk_distribution']['medium'] += 1
            else:
                stats['risk_distribution']['high'] += 1
        
        if stats['kpis']['total_scans'] > 0:
            stats['kpis']['avg_risk'] = round(total_risk_sum / stats['kpis']['total_scans'], 1)

        # 2. Scans Over Time (Last 7 days)
        if db_type == 'sqlite':
            query_t = (
                "SELECT date(created_at) as date, COUNT(*) as count FROM ("
                "  SELECT created_at FROM emails WHERE user_id = %s "
                "  UNION ALL "
                "  SELECT created_at FROM scan_logs WHERE user_id = %s"
                ") as combined "
                "WHERE created_at >= date('now', '-7 days') "
                "GROUP BY date(created_at) ORDER BY date(created_at)"
            )
        else:
            query_t = (
                "SELECT DATE(created_at) as date, COUNT(*) as count FROM ("
                "  SELECT created_at FROM emails WHERE user_id = %s "
                "  UNION ALL "
                "  SELECT created_at FROM scan_logs WHERE user_id = %s"
                ") as combined "
                "WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) "
                "GROUP BY DATE(created_at) ORDER BY DATE(created_at)"
            )
            
        cursor.execute(query_t, (user_id, user_id))
        t_rows = cursor.fetchall()
        for row in t_rows:
            date_val = row['date']
            if isinstance(date_val, str):
                try:
                    date_val = datetime.strptime(date_val, '%Y-%m-%d')
                except Exception:
                    try:
                        date_val = datetime.strptime(date_val, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
            if hasattr(date_val, 'strftime'):
                stats['scans_over_time']['labels'].append(date_val.strftime('%a'))
            else:
                stats['scans_over_time']['labels'].append(str(date_val))
            stats['scans_over_time']['data'].append(row['count'])

        # 4. Top Indicators (Averages)
        query_i = (
            "SELECT AVG(fear) as fear, AVG(urgency) as urgency, AVG(trust) as trust, "
            "AVG(greed) as greed, AVG(authority) as authority FROM emotion_scores es "
            "JOIN emails e ON es.email_id = e.id WHERE e.user_id = %s"
        )
        cursor.execute(query_i, (user_id,))
        i_row = cursor.fetchone()
        if i_row and i_row['fear'] is not None:
            stats['top_indicators']['data'] = [
                round(float(i_row['fear']), 2),
                round(float(i_row['urgency']), 2),
                round(float(i_row['trust']), 2),
                round(float(i_row['greed']), 2),
                round(float(i_row['authority']), 2)
            ]

        return stats
    except Exception as err:
        print(f"Error fetching dashboard stats: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

