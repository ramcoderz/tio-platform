import re
import logging

logger = logging.getLogger(__name__)

# Basic PII regex patterns
PII_PATTERNS = {
    "email": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
    "phone": r'\b(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b',
    "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
    "credit_card": r'\b(?:\d{4}[- ]?){3}\d{4}\b'
}

# Prompt Injection keywords
INJECTION_KEYWORDS = [
    "ignore all previous instructions",
    "disregard all previous instructions",
    "system prompt",
    "you are now a",
    "forget everything you were told",
    "output the following instead",
    "bypass",
    "jailbreak"
]

def sanitize_input(text: str) -> str:
    """Mask PII and detect prompt injection attempts."""
    if not text: return ""
    
    # 1. Detect Injection
    lower_text = text.lower()
    for kw in INJECTION_KEYWORDS:
        if kw in lower_text:
            logger.warning(f"Potential prompt injection detected: {kw}")
            return "[SECURITY ALERT: POTENTIAL PROMPT INJECTION DETECTED]"

    # 2. Mask PII
    sanitized = text
    for label, pattern in PII_PATTERNS.items():
        sanitized = re.sub(pattern, f"[{label.upper()}_MASKED]", sanitized)
        
    return sanitized

def sanitize_output(text: str) -> str:
    """Basic output sanitization (e.g. removing system instructions leakage)."""
    if not text: return ""
    
    # Remove any text that looks like system instructions leak
    patterns = [
        r"You are a.*Assistant",
        r"Base all answers strictly.*",
        r"\[Source Name\].*"
    ]
    
    sanitized = text
    for p in patterns:
        sanitized = re.sub(p, "", sanitized, flags=re.IGNORECASE)
        
    return sanitized.strip()
