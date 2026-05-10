import re
from fastapi import HTTPException

# A comprehensive list of keywords and substrings that violate typical app store policies.
# This covers sexual content, severe violence, self-harm, hate speech, and illegal acts.
FORBIDDEN_WORDS = {
    # Nudity & Sexual Content
    "nude", "naked", "sex", "porn", "nsfw", "erotica", "penetration", "masturbation", 
    "orgasm", "ejaculation", "cum", "pussy", "dick", "cock", "vagina", "penis",
    "boobs", "tits", "breasts", "nipples", "asshole", "blowjob", "handjob", 
    "incest", "pedophile", "rape", "nonconsensual", "slut", "whore", "escort",
    "undress", "strip", "unclothe", "remove clothes", "take off clothes", "without clothes", "no clothes", "remove cloths",
    "lingerie", "bikini", "cleavage", "cameltoe", "see-through", "transparent clothes", "bdsm", "bondage", "fetish", "milf", "thong", "panties", "underwear", "jailbait", "loli", "shota",
    
    # Violence & Gore
    "gore", "dismemberment", "decapitation", "mutilation", "blood spill", 
    "gushing blood", "guts", "intestines", "torture", "massacre", "slaughter",
    "snuff", "execution", "lynching", "cruelty", "blood bath", "decapitate", "stabbing", "shooting", "murder", "assassinate",
    
    # Self-Harm
    "suicide", "kill myself", "cut myself", "self-harm", "anorexia", "bulimia",
    
    # Hate Speech & Harassment
    "nigger", "faggot", "dyke", "tranny", "chink", "spic", "gook", "kike", 
    "retard", "supremacist", "nazism", "hitler", "kkk", "holocaust", "terrorist",
    
    # Illegal Acts
    "child abuse", "cp", "child porn", "meth", "heroin", "cocaine", "fentanyl", "bomb making", 
    "how to make a bomb", "assassination", "weed", "marijuana", "lsd", "acid", "shrooms", "magic mushrooms"
}

def check_prompt_safety(prompt: str):
    """
    Checks the prompt against a predefined blacklist of forbidden words.
    Raises an HTTP 400 Exception if a violation is found.
    """
    if not prompt:
        return
        
    # Convert to lowercase and strip special characters to prevent simple bypasses
    # e.g. "n*ked" or "n u d e"
    # To keep it performant and simple for now, we just lower and regex remove punctuation
    clean_prompt = re.sub(r'[^\w\s]', '', prompt.lower())
    
    # Split by whitespace to check exact word boundaries, 
    # but also do a simple substring check for very severe words.
    words = set(clean_prompt.split())
    
    for word in FORBIDDEN_WORDS:
        # If the forbidden word is in the set of words
        if word in words:
            raise HTTPException(
                status_code=400, 
                detail="Safety Violation: Your prompt contains inappropriate content that violates our community guidelines."
            )
            
        # Or if it's a multi-word phrase that is inside the clean_prompt
        if " " in word and word in clean_prompt:
            raise HTTPException(
                status_code=400, 
                detail="Safety Violation: Your prompt contains inappropriate content that violates our community guidelines."
            )
