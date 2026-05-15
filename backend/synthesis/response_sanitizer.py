import re
import logging

logger = logging.getLogger(__name__)

class ResponseSanitizer:
    """
    Implements the Response Humanization Layer.
    Removes robotic filler, passive phrasing, and AI disclaimers.
    """

    ROBOTIC_PATTERNS = [
        r"i['']d be happy to help",
        r"i['']m happy to assist",
        r"as an ai",
        r"as a language model",
        r"based on the (?:retrieved )?context",
        r"according to the (?:provided )?information",
        r"certainly!",
        r"of course!",
        r"i understand your question",
        r"thank you for asking",
        r"let me help you with that",
        r"here is the information i found",
    ]

    def __init__(self):
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.ROBOTIC_PATTERNS]

    def humanize(self, text: str) -> str:
        # 1. Remove specific robotic phrases
        for pattern in self.patterns:
            text = pattern.sub("", text)

        # 2. Fix punctuation and spacing after removals
        text = re.sub(r"^\s*[,.:!]\s*", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        # 3. Capitalize first letter if it became lowercase
        if text and text[0].islower():
            text = text[0].upper() + text[1:]

        # 4. Remove bracketed placeholders if any escaped the prompt constraints
        text = re.sub(r'\[[A-Z][^\]]{2,40}\]', 'relevant details', text)

        # 5. Passive to Active (Basic heuristic)
        # "Information can be found here" -> "Find information here"
        text = re.sub(r"information can be found", "find information", text, flags=re.IGNORECASE)

        return text
