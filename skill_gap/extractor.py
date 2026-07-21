"""
skill_gap/extractor.py
----------------------
Handles two things:
  1. normalize_skills(skills_str)
     Cleans and normalizes a comma-separated skill string.
     Used by scorer.py for skill gap calculation.

  2. extract_skills_from_resume(pdf_path)
     Extracts skills from a PDF resume using Hybrid Approach 3:
       - pypdf    → extract raw text from PDF
       - spaCy    → extract noun phrases from text
       - sentence-transformers → match noun phrases against master skill list
       - rules    → catch skills not in master list (unverified)

Returns:
  {
    "verified":   ["python", "java", "spring boot"],   # matched against master list
    "unverified": ["keil mdk", "altium designer"]      # look like skills but not in master list
  }
"""

import re
import spacy
import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer, util
from skill_gap.skills_list import MASTER_SKILLS, STOPWORDS_FOR_SKILLS

# ── Load models once at module level (avoids reloading on every request) ──
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise OSError(
        "spaCy model not found. Run: python -m spacy download en_core_web_sm"
    )

model = SentenceTransformer("all-MiniLM-L6-v2")

# Pre-compute master skill embeddings once
_master_lower     = [s.lower() for s in MASTER_SKILLS]
_master_embeddings = model.encode(_master_lower, convert_to_tensor=True)

# Similarity threshold — above this = verified skill match
VERIFIED_THRESHOLD   = 0.82
# Lower threshold for unverified candidates
UNVERIFIED_THRESHOLD = 0.55


# ══════════════════════════════════════════════════════════════
#  1. NORMALIZE SKILLS STRING
# ══════════════════════════════════════════════════════════════
def normalize_skills(skills_str):
    """
    Cleans a comma-separated skill string and returns a normalized list.

    Args:
        skills_str (str): e.g. "Python, REST APIs, Spring Boot"

    Returns:
        list: e.g. ["python", "rest api", "spring boot"]
    """
    if not skills_str:
        return []

    tokens = [s.strip() for s in skills_str.split(",") if s.strip()]
    normalized = []

    for token in tokens:
        doc = nlp(token.lower())
        # Lemmatize each word in the token and rejoin
        lemmatized = " ".join([t.lemma_ for t in doc if not t.is_punct])
        if lemmatized:
            normalized.append(lemmatized)

    return normalized


# ══════════════════════════════════════════════════════════════
#  2. EXTRACT TEXT FROM PDF
# ══════════════════════════════════════════════════════════════
def _extract_text_from_pdf(pdf_path):
    """
    Extracts raw text from a PDF file using pypdf.

    Args:
        pdf_path (str): path to the PDF file

    Returns:
        str: full text content of the PDF
    """
    try:
        reader = PdfReader(pdf_path)
        text   = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"Could not read PDF: {e}")


# ══════════════════════════════════════════════════════════════
#  3. EXTRACT NOUN PHRASES FROM TEXT
# ══════════════════════════════════════════════════════════════
def _extract_noun_phrases(text):
    """
    Extracts noun phrases from text using spaCy.
    Filters out stopwords, dates, proper nouns that are not skills.

    Args:
        text (str): raw resume text

    Returns:
        list: cleaned candidate phrases that could be skills
    """
    doc      = nlp(text[:100000])  # limit to 100k chars for performance
    phrases  = set()

    # Get noun chunks (multi-word noun phrases)
    for chunk in doc.noun_chunks:
        phrase = chunk.text.lower().strip()
        phrase = re.sub(r'[^a-z0-9\.\+\#\s]', '', phrase).strip()
        if phrase and len(phrase) > 1:
            phrases.add(phrase)

    # Also get individual tokens that look technical
    for token in doc:
        if token.pos_ in ("NOUN", "PROPN") and not token.is_stop:
            word = token.text.lower().strip()
            word = re.sub(r'[^a-z0-9\.\+\#]', '', word).strip()
            if word and len(word) > 1:
                phrases.add(word)

    # Filter out stopwords
    stopwords_lower = [s.lower() for s in STOPWORDS_FOR_SKILLS]
    filtered = [
        p for p in phrases
        if not any(sw in p for sw in stopwords_lower)
        and len(p.split()) <= 4      # skills are rarely more than 4 words
        and not p.isdigit()          # filter out pure numbers
        and len(p) >= 2              # filter out single characters
    ]

    return filtered


# ══════════════════════════════════════════════════════════════
#  4. MATCH PHRASES AGAINST MASTER SKILL LIST
# ══════════════════════════════════════════════════════════════
def _match_against_master(phrases):
    """
    Matches extracted phrases against MASTER_SKILLS using
    sentence-transformers cosine similarity.

    Args:
        phrases (list): noun phrases extracted from resume

    Returns:
        tuple: (verified_skills, unverified_skills)
          verified   — matched against master list with similarity > 0.82
          unverified — look like skills but not in master list (0.55 < sim < 0.82)
    """
    if not phrases:
        return [], []

    phrase_embeddings = model.encode(phrases, convert_to_tensor=True)
    cosine_scores     = util.cos_sim(phrase_embeddings, _master_embeddings)

    verified   = []
    unverified = []

    for i, phrase in enumerate(phrases):
        scores     = cosine_scores[i]
        max_score  = float(scores.max())
        best_match = _master_lower[int(scores.argmax())]

        if max_score >= VERIFIED_THRESHOLD:
            # High confidence — use the master list label (normalized form)
            if best_match not in verified:
                verified.append(best_match)

        elif max_score >= UNVERIFIED_THRESHOLD:
            # Medium confidence — looks like a skill but not in master list
            # Apply extra rules to reduce false positives
            if _looks_like_skill(phrase) and phrase not in unverified:
                unverified.append(phrase)

    return verified, unverified


# ══════════════════════════════════════════════════════════════
#  5. RULES CHECK FOR UNVERIFIED SKILLS
# ══════════════════════════════════════════════════════════════
def _looks_like_skill(phrase):
    """
    Applies simple rules to check if a phrase looks like a technical skill.
    Used for unverified candidates that didn't match the master list.

    Rules:
      - 1 to 3 words only
      - Not a common English word
      - Not purely lowercase common words
      - Contains digit or special char (like C++, .NET, ESP32) OR
        is short and capitalized in original context
    """
    words = phrase.split()

    # Too long to be a skill
    if len(words) > 3:
        return False

    # Too short to be meaningful
    if len(phrase) < 2:
        return False

    # Check if it contains technical indicators
    has_special = bool(re.search(r'[\+\#\.\d]', phrase))
    is_short    = len(words) <= 2

    return has_special or is_short


# ══════════════════════════════════════════════════════════════
#  6. MAIN FUNCTION
# ══════════════════════════════════════════════════════════════
def extract_skills_from_resume(pdf_path):
    """
    Full pipeline: PDF → text → noun phrases → verified + unverified skills.

    Args:
        pdf_path (str): path to uploaded resume PDF

    Returns:
        dict:
          {
            "verified":   ["python", "machine learning", "flask"],
            "unverified": ["keil mdk", "altium designer"]
          }

    Raises:
        ValueError: if PDF cannot be read or has no extractable text
    """
    # Step 1 — Extract text from PDF
    text = _extract_text_from_pdf(pdf_path)

    if len(text.split()) < 10:
        raise ValueError(
            "Could not extract meaningful text from this PDF. "
            "It may be a scanned image — please upload a text-based PDF."
        )

    # Step 2 — Extract noun phrases
    phrases = _extract_noun_phrases(text)

    if not phrases:
        return {"verified": [], "unverified": []}

    # Step 3 — Match against master list
    verified, unverified = _match_against_master(phrases)

    return {
        "verified":   verified,
        "unverified": unverified
    }