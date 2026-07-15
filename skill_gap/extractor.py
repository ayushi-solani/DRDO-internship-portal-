import spacy
import re

# Load the spaCy English model globally so it only loads once per worker
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("[Error] spaCy model 'en_core_web_sm' not found.")
    print("Please run: python -m spacy download en_core_web_sm")
    # Provide a fallback for gracefully failing if not installed
    nlp = None 

def extract_and_normalize_skills(skills_str: str) -> list[str]:
    """
    Takes a comma-separated string of skills, splits them, and normalizes 
    each token by lowercasing and lemmatizing (reducing to base form).
    
    Example: "Java, REST APIs, Spring Boot" -> ["java", "rest api", "spring boot"]
    """
    # 1. Edge Case: Empty string or None
    if not skills_str or not isinstance(skills_str, str):
        return []

    # 2. Split by comma
    raw_skills = skills_str.split(',')
    normalized_skills = []

    for skill in raw_skills:
        # Strip leading/trailing whitespaces
        skill = skill.strip()
        
        # 3. Edge Case: Ignore empty tokens (e.g., caused by trailing commas)
        if not skill:
            continue

        if nlp is None:
            # Fallback if spaCy isn't loaded; just lowercase it
            clean_skill = skill.lower()
        else:
            # 4. Normalization (spaCy lemmatization + lowercasing)
            doc = nlp(skill)
            
            # Extract lemmas, lowercase them, and ignore purely whitespace tokens
            lemmas = [token.lemma_.lower() for token in doc if token.text.strip()]
            
            # Join back into a single string
            clean_skill = " ".join(lemmas)

            # --- DOMAIN-SPECIFIC FIX ---
            # spaCy maps "data" to its singular form "datum", which breaks tech terms.
            clean_skill = clean_skill.replace("datum", "data")

            # 5. Edge Case: Remove extra internal spaces (e.g., "spring    boot" -> "spring boot")
            clean_skill = re.sub(r'\s+', ' ', clean_skill).strip()

        if clean_skill:
            normalized_skills.append(clean_skill)

    # 6. Edge Case: Remove duplicates while preserving order
    seen = set()
    unique_skills = []
    for s in normalized_skills:
        if s not in seen:
            seen.add(s)
            unique_skills.append(s)

    return unique_skills

# ==========================================
# UNIT TESTS
# ==========================================
if __name__ == "__main__":
    print("Running Extractor Unit Tests...\n")
    
    test_cases = [
        # Basic parsing & lemmatization
        ("Spring Boot, REST APIs, Machine Learning", ["spring boot", "rest api", "machine learning"]),
        
        # Spelling variations & casing
        ("ReactJS, Deep Learning, POSTMAN, C++", ["reactjs", "deep learning", "postman", "c++"]),
        
        # Edge Cases: Extra spaces, empty strings, trailing commas
        ("   Python  , , Java ,   Data   Structures  ,", ["python", "java", "data structure"]),
        
        # Edge Case: None or totally empty
        ("", []),
    ]

    all_passed = True
    for i, (input_str, expected) in enumerate(test_cases, 1):
        result = extract_and_normalize_skills(input_str)
        if result == expected:
            print(f"✅ Test {i} Passed")
        else:
            print(f"❌ Test {i} Failed")
            print(f"   Input:    {input_str}")
            print(f"   Expected: {expected}")
            print(f"   Got:      {result}")
            all_passed = False

    if all_passed:
        print("\nAll unit tests passed successfully! Task 1 is complete.")