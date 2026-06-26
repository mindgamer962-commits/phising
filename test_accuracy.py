from logic.detector import analyze_email, analyze_url
import os

def test_detector():
    print("=== Testing Phishing Detector Improvements ===")
    
    tests = [
        {
            "name": "Trusted Domain Whitelist",
            "text": "Hello, your Amazon order is ready.",
            "domain": "amazon.in"
        },
        {
            "name": "Safe Email (Legitimate)",
            "text": "Hi Team, let's meet tomorrow for the project sync. Please update your status.",
            "domain": ""
        },
        {
            "name": "High Risk Phishing Email",
            "text": "URGENT: Your account was suspended! Click http://paypa1-secure-portal.com/verify now or lose access!",
            "domain": ""
        },
        {
            "name": "Suspicious Email (Shorteners)",
            "text": "Dear user, you have a new notification. Click here: http://bit.ly/random-link",
            "domain": ""
        },
        {
            "name": "Trusted URL",
            "text": "",
            "url": "https://www.google.com/search?q=phishing"
        }
    ]
    
    for i, test in enumerate(tests, 1):
        print(f"\n[Test {i}] {test['name']}")
        if "url" in test:
            result = analyze_url(test["url"])
        else:
            result = analyze_email(test["text"], sender_domain=test.get("domain", ""))
        
        print(f"Verdict: {result['verdict']}")
        print(f"Score: {result['score']}")
        print("Explanations:")
        for exp in result.get("explanations", []):
            print(f" - {exp}")

if __name__ == "__main__":
    test_detector()
