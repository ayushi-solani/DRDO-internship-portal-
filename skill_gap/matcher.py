"""
skill_gap/matcher.py
--------------------
Handles semantic similarity matching between candidate skills
and required skills using sentence-transformers.

Uses the same model already loaded in extractor.py but operates
on normalized skill strings (output of extractor.normalize_skills).

Main function:
  find_matches(candidate_skills, required_skills)
    Args:
      candidate_skills (list): normalized skills from candidate profile
                               or extracted from resume
      required_skills  (list): normalized skills from internship position

    Returns:
      tuple: (matched, missing)
        matched — required skills the candidate has
        missing — required skills the candidate is missing
"""

from sentence_transformers import SentenceTransformer, util

# Load model once at module level
# Same model as extractor.py — sentence-transformers caches it locally
# so no re-download happens
model = SentenceTransformer("all-MiniLM-L6-v2")

# Similarity threshold — above this = skill is considered matched
MATCH_THRESHOLD = 0.82


def find_matches(candidate_skills, required_skills):
    """
    Compares candidate skills against required skills using
    cosine similarity of sentence embeddings.

    For each required skill, checks if any candidate skill has
    similarity >= 0.82. If yes → matched. If no → missing.

    This handles variations like:
      "rest api"    ≈ "restful api"      → match
      "react.js"    ≈ "reactjs"          → match
      "deep learning" ≈ "neural networks" → match
      "postman"     ≠ "python"           → no match (correctly rejected)

    Args:
      candidate_skills (list): e.g. ["python", "spring boot", "rest api"]
      required_skills  (list): e.g. ["python", "rest api", "postman", "docker"]

    Returns:
      tuple:
        matched (list): required skills found in candidate skills
        missing (list): required skills not found in candidate skills
    """
    # Edge cases
    if not required_skills:
        return [], []

    if not candidate_skills:
        return [], required_skills

    # Encode both lists
    candidate_embeddings = model.encode(candidate_skills, convert_to_tensor=True)
    required_embeddings  = model.encode(required_skills,  convert_to_tensor=True)

    # Compute cosine similarity matrix
    # Shape: (len(required_skills), len(candidate_skills))
    cosine_scores = util.cos_sim(required_embeddings, candidate_embeddings)

    matched = []
    missing = []

    for i, req_skill in enumerate(required_skills):
        # Get best matching candidate skill for this required skill
        scores    = cosine_scores[i]
        max_score = float(scores.max())

        if max_score >= MATCH_THRESHOLD:
            matched.append(req_skill)
        else:
            missing.append(req_skill)

    return matched, missing


def similarity_score(skill_a, skill_b):
    """
    Utility function to get similarity score between two individual skills.
    Useful for debugging and testing.

    Args:
      skill_a (str): first skill
      skill_b (str): second skill

    Returns:
      float: cosine similarity score between 0.0 and 1.0
    """
    embeddings = model.encode([skill_a, skill_b], convert_to_tensor=True)
    score = util.cos_sim(embeddings[0], embeddings[1])
    return float(score)