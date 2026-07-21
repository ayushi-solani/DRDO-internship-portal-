# skill_gap/__init__.py
# Makes skill_gap a Python package.

from skill_gap.scorer import compute_skill_gap, build_candidate_skill_string
from skill_gap.extractor import extract_skills_from_resume, normalize_skills
from skill_gap.matcher import find_matches