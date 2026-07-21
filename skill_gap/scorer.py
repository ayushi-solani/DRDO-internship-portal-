"""
skill_gap/scorer.py
-------------------
Main entry point for the skill gap module.
Ties extractor and matcher together and returns the final result.

Main function:
  compute_skill_gap(candidate_skills_str, required_skills_str)
    Args:
      candidate_skills_str (str): comma-separated skills from candidate
                                  (either manual or extracted from resume)
      required_skills_str  (str): comma-separated skills from position

    Returns:
      dict:
        {
          "matched": ["python", "spring boot"],
          "missing": ["rest api", "postman"],
          "score":   50.0
        }
"""

import json

from skill_gap.extractor import normalize_skills
from skill_gap.matcher import find_matches


def build_candidate_skill_string(profile):
    """
    Combines a candidate's self-declared skills, resume-verified skills,
    and any resume-unverified skills the candidate has manually confirmed
    into one comma-separated string ready for compute_skill_gap().

    Args:
      profile (dict): a candidate_profiles row (as returned by query()).
        Reads profile["skills"] (freetext), profile["extracted_skills"]
        (JSON array, resume-verified), and
        profile["confirmed_unverified_skills"] (JSON array, candidate-confirmed).

    Returns:
      str: comma-separated skills, e.g. "Python, Flask, Keil MDK"
    """
    parts = []

    if profile.get("skills"):
        parts.append(profile["skills"])

    if profile.get("extracted_skills"):
        try:
            parts.extend(json.loads(profile["extracted_skills"]))
        except (TypeError, ValueError):
            pass

    if profile.get("confirmed_unverified_skills"):
        try:
            parts.extend(json.loads(profile["confirmed_unverified_skills"]))
        except (TypeError, ValueError):
            pass

    return ", ".join(p for p in parts if p and p.strip())


def compute_skill_gap(candidate_skills_str, required_skills_str):
    """
    Computes skill gap between candidate skills and required skills.

    Steps:
      1. Normalize both skill strings using spaCy lemmatizer
      2. Find matched and missing skills using semantic similarity
      3. Calculate match percentage score
      4. Return result dict

    Args:
      candidate_skills_str (str): e.g. "Python, Spring Boot, REST APIs"
      required_skills_str  (str): e.g. "Python, REST API, Postman, Docker"

    Returns:
      dict with matched, missing and score
    """
    # Step 1 — Normalize both skill strings
    candidate_skills = normalize_skills(candidate_skills_str)
    required_skills  = normalize_skills(required_skills_str)

    # Step 2 — Find matched and missing
    matched, missing = find_matches(candidate_skills, required_skills)

    # Step 3 — Calculate match percentage
    total = len(required_skills)
    if total == 0:
        score = 0.0
    else:
        score = round((len(matched) / total) * 100, 1)

    # Step 4 — Return result
    return {
        "matched": matched,
        "missing": missing,
        "score":   score
    }