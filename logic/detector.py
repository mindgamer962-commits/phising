import re
import time
import joblib
import os
import logging

# Configure logging
log_handlers = [logging.StreamHandler()]
if not (os.getenv('VERCEL') or os.getenv('VERCEL_ENV')):
    try:
        log_handlers.append(logging.FileHandler("scan_logs.log"))
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger("PhishingDetector")

# Load ML models
try:
    email_model = joblib.load('models/email_model.joblib')
    file_model = joblib.load('models/file_model.joblib')
    ML_AVAILABLE = True
    logger.info("ML models loaded successfully.")
except Exception as e:
    ML_AVAILABLE = False
    logger.warning(f"ML models not found: {e}. Falling back to rule-based detection.")

def get_risk_level(score: float) -> str:
    """
    Maps score (0-100) to 4-level risk classification strictly based on prompt rules.
    0-10: Safe, 11-40: Low Risk, 41-70: Medium Risk, 71-100: High Risk
    """
    if score >= 71: return "High Risk"
    elif score >= 41: return "Medium Risk"
    elif score >= 11: return "Low Risk"
    else: return "Safe"

def generate_recommendation(verdict: str, type: str) -> str:
    if verdict == "Safe": return "No action needed. The content appears safe."
    elif verdict == "Low Risk": return "Exercise mild caution. Do not share sensitive information unless fully verified."
    elif verdict == "Medium Risk": return "Proceed with caution. Verify the sender/domain independently before clicking links."
    else: return f"DO NOT OPEN OR INTERACT. Delete this {type} immediately."

def analyze_url(url: str) -> dict:
    risk_score = 0.0 # Strict: start at 0
    reasons = []
    red_flags = []
    safe_signals = []
    
    lower_url = url.lower()
    logger.info(f"Analyzing URL: {url}")

    # 1. Strong High-Risk Indicators
    ip_regex = r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}"
    if re.search(ip_regex, lower_url):
        risk_score += 40
        red_flags.append("URL uses a direct IP address instead of a domain name.")
        reasons.append("Legitimate services use domains, not raw IPs.")

    if "@" in lower_url:
        risk_score += 40
        red_flags.append("Contains '@' symbol designed to hide the true destination.")
        reasons.append("Use of '@' in URLs is a common obfuscation technique.")

    phish_keywords = ["login", "verify", "account", "update", "bank", "confirm", "signin", "secure-login", "auth", "billing"]
    lure_keywords = ["mod", "apk", "extra", "free", "working", "cracked", "bonus", "winner", "reward", "link", "download"]
    
    matched_phish = [kw for kw in phish_keywords if kw in lower_url]
    if matched_phish:
        risk_score += 25
        red_flags.append(f"Suspicious credential harvesting keywords: {', '.join(matched_phish)}.")
        reasons.append("URL contains words often used in phishing attacks to steal credentials.")

    domain_match = re.search(r"https?://(?:www\.)?([^/]+)", lower_url)
    domain_only = domain_match.group(1) if domain_match else ""
    
    lures_in_domain = [kw for kw in lure_keywords if kw in domain_only]
    if len(lures_in_domain) >= 2:
        risk_score += 35
        red_flags.append(f"Domain is exclusively composed of lure keywords: {', '.join(lures_in_domain)}.")
    elif [kw for kw in lure_keywords if kw in lower_url]:
        risk_score += 15
        red_flags.append("URL contains generic lures to attract victims.")

    look_alikes = ['g00gle', 'paypa1', 'micros0ft', 'rnicrosoft', 'amaz0n', 'faceb00k', 'happym0d', 'netf1ix']
    if any(variant in lower_url for variant in look_alikes):
        risk_score += 50
        red_flags.append("Spoofed or exact-match typosquatted domain identity.")
        reasons.append("The domain name mimics a known brand.")

    zero_width_pattern = r"[\u200b-\u200d\ufeff]"
    if re.search(zero_width_pattern, lower_url):
        risk_score += 50
        red_flags.append("Indiscernible zero-width characters detected (Stealth Phishing).")
        
    if "xn--" in lower_url:
        risk_score += 40
        red_flags.append("Punycode detected, likely a homograph attack.")

    if lower_url.count(".") > 4:
        risk_score += 15
        reasons.append("Excessive subdomains detected, often used to bypass filters.")

    suspicious_tlds = [".xyz", ".top", ".tk", ".ml", ".ga", ".cf", ".gq", ".site", ".work", ".shop", ".online"]
    if any(lower_url.endswith(tld) or (tld + "/") in lower_url for tld in suspicious_tlds):
        risk_score += 15
        reasons.append("Uses a high-risk Top-Level Domain (TLD).")

    # Safe Indicators
    if not lower_url.startswith("https://"):
        risk_score += 20
        reasons.append("Insecure HTTP connection.")
    elif not red_flags:
        safe_signals.append("Uses secure HTTPS connection.")
        
    if domain_match and domain_only.count(".") == 1 and not any(kw in domain_only for kw in phish_keywords + lure_keywords):
        if not red_flags:
            safe_signals.append("Clean, standard domain structure.")

    final_score = max(0, min(100, risk_score))
    # Strict rule: safe default is 0-5%
    if final_score == 0 and not red_flags and not reasons:
        final_score = 5.0
        reasons.append("No suspicious patterns detected.")
        safe_signals.append("URL appears completely standard.")

    verdict_level = get_risk_level(final_score)
    summary = f"This URL is categorized as {verdict_level}."

    return {
        "risk_score": float(f"{final_score:.2f}"),
        "risk_level": verdict_level,
        "verdict": summary,
        "reasons": reasons,
        "red_flags": red_flags,
        "safe_signals": safe_signals,
        "recommendation": generate_recommendation(verdict_level, "link"),
        "score": float(f"{final_score:.2f}") 
    }

def analyze_email(text: str, sender_domain: str = "") -> dict:
    risk_score = 0.0
    reasons = []
    red_flags = []
    safe_signals = []
    
    lower_text = text.lower()
    
    trusted_domains = ["amazon.in", "google.com", "microsoft.com", "apple.com", "github.com"]
    if sender_domain and any(sender_domain.lower().endswith(td) for td in trusted_domains):
        safe_signals.append(f"Sender domain ({sender_domain}) is a known trusted organization.")

    ml_confidence = 0.0
    if ML_AVAILABLE:
        try:
            label = email_model.predict([text])[0]
            probs = email_model.predict_proba([text])[0]
            ml_confidence = float(max(probs))
            if label == 'phishing':
                risk_score += 50 * ml_confidence
                red_flags.append(f"AI identified phishing linguistic patterns ({ml_confidence:.1%} confidence).")
            elif label == 'suspicious':
                risk_score += 25 * ml_confidence
                reasons.append(f"AI flagged content as mildly suspicious.")
            else:
                safe_signals.append(f"AI classifies this content as natural/legitimate.")
        except: pass

    urgent_pattern = r'\b(urgent|immediately|24 hours|suspended|action required)\b'
    if re.search(urgent_pattern, lower_text):
        risk_score += 25
        red_flags.append("Creates artificial urgency or fear (e.g., account suspension).")
    
    lure_pattern = r'\b(winner|prize|refund|bonus|lottery)\b'
    if re.search(lure_pattern, lower_text):
        risk_score += 20
        reasons.append("Email contains deceptive lures like prizes or bonuses.")
        
    fin_pattern = r'\b(password|otp|ssn|social security|credit card|wire transfer)\b'
    if re.search(fin_pattern, lower_text):
        risk_score += 30
        red_flags.append("Requests highly sensitive personal or financial information.")

    if safe_signals and not red_flags and risk_score < 40:
        risk_score = min(risk_score, 10.0)

    final_score = max(0, min(100, risk_score))
    
    if final_score == 0 and not red_flags and not reasons:
        final_score = 2.0
        reasons.append("Normal conversational or professional language without threats.")
        safe_signals.append("No obvious malicious signals found.")

    verdict_level = get_risk_level(final_score)
    summary = f"This email is categorized as {verdict_level} based on analysis."

    eds_breakdown = {
        "fear": 0.45 if re.search(r'\b(suspended|block|close)\b', lower_text) else 0.0,
        "urgency": 0.85 if re.search(r'\b(urgent|immediately)\b', lower_text) else 0.0,
        "trust": 0.30 if re.search(r'\b(verify|secure)\b', lower_text) else 0.0,
        "greed": 0.70 if re.search(r'\b(winner|bonus|refund)\b', lower_text) else 0.0,
        "authority": 0.50 if re.search(r'\b(official|admin|support)\b', lower_text) else 0.0
    }
    eds_score = sum(eds_breakdown.values()) / len(eds_breakdown)

    return {
        "risk_score": float(f"{final_score:.2f}"),
        "risk_level": verdict_level,
        "verdict": summary,
        "reasons": reasons,
        "red_flags": red_flags,
        "safe_signals": safe_signals,
        "recommendation": generate_recommendation(verdict_level, "email"),
        "phishing_probability": round(final_score / 100.0, 4),
        "emotional_deception_score": round(eds_score, 4),
        "confidence": round(ml_confidence or 0.85, 4),
        "eds_breakdown": eds_breakdown,
        "score": float(f"{final_score:.2f}")
    }

def analyze_file(file_name: str) -> dict:
    risk_score = 0.0
    reasons = []
    red_flags = []
    safe_signals = []
    
    lower_name = file_name.lower()

    dangerous_exts = [".exe", ".bat", ".vbs", ".js", ".cmd", ".ps1", ".jar", ".scr"]
    if any(lower_name.endswith(ext) for ext in dangerous_exts):
        risk_score += 80
        red_flags.append("Dangerous, highly-executable file extension detected.")
        reasons.append(f"Files like this can infect the system with malware.")
    else:
        safe_signals.append("Standard file type (not immediately dangerous).")

    if lower_name.count(".") > 1:
        risk_score += 30
        red_flags.append("Double extension detected (e.g., summary.pdf.exe).")
        reasons.append("Often used to disguise malicious scripts as innocuous documents.")

    final_score = max(0, min(100, risk_score))
    if final_score == 0 and not red_flags:
        final_score = 0.0
        reasons.append("Filename structure appears completely normal.")

    verdict_level = get_risk_level(final_score)
    summary = f"This file is categorized as {verdict_level}."

    return {
        "risk_score": float(f"{final_score:.2f}"),
        "risk_level": verdict_level,
        "verdict": summary,
        "reasons": reasons,
        "red_flags": red_flags,
        "safe_signals": safe_signals,
        "recommendation": generate_recommendation(verdict_level, "file"),
        "score": float(f"{final_score:.2f}")
    }
