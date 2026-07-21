"""
skill_gap/skills_list.py
------------------------
Master list of known technical skills covering all DRDO research domains.
Used by extractor.py to match and verify skills extracted from resumes.

Domains covered:
  - Programming Languages
  - AI / Machine Learning
  - Web & Backend Development
  - Databases
  - Embedded Systems & Hardware
  - Cyber Security
  - Aerospace & Radar
  - Tools & DevOps
  - Core CS Fundamentals
"""

MASTER_SKILLS = [
    # ── Programming Languages ──
    "python", "java", "c", "c++", "c#", "javascript", "typescript",
    "r", "matlab", "scala", "go", "rust", "swift", "kotlin", "perl",
    "bash", "shell scripting", "assembly", "fortran",

    # ── AI / Machine Learning ──
    "machine learning", "deep learning", "neural networks",
    "natural language processing", "nlp", "computer vision",
    "reinforcement learning", "transfer learning",
    "convolutional neural network", "cnn", "recurrent neural network",
    "rnn", "lstm", "transformer", "bert", "gpt",
    "tensorflow", "pytorch", "keras", "scikit-learn", "opencv",
    "pandas", "numpy", "scipy", "matplotlib", "seaborn",
    "data science", "data analysis", "data visualization",
    "feature engineering", "model training", "model evaluation",
    "hyperparameter tuning", "random forest", "svm",
    "support vector machine", "xgboost", "gradient boosting",
    "decision tree", "k-means", "clustering", "regression",
    "classification", "object detection", "image segmentation",
    "yolo", "openai", "hugging face", "langchain",

    # ── Web & Backend Development ──
    "flask", "django", "fastapi", "spring boot", "spring",
    "node.js", "express.js", "react", "angular", "vue.js",
    "html", "css", "bootstrap", "tailwind css",
    "rest api", "restful api", "graphql", "soap",
    "microservices", "serverless", "websockets",
    "jwt", "oauth", "authentication", "authorization",

    # ── Databases ──
    "mysql", "postgresql", "sqlite", "mongodb", "redis",
    "cassandra", "oracle", "sql server", "firebase",
    "elasticsearch", "dynamodb", "sql", "nosql",
    "database design", "stored procedures", "indexing",

    # ── Embedded Systems & Hardware ──
    "embedded c", "embedded systems", "arm cortex", "rtos",
    "keil mdk", "fpga", "vhdl", "verilog", "arduino",
    "raspberry pi", "esp32", "stm32", "microcontroller",
    "uart", "spi", "i2c", "can bus", "pwm",
    "real time operating system", "freertos", "bare metal",
    "pcb design", "altium", "eagle", "circuit design",
    "oscilloscope", "logic analyzer", "jtag",

    # ── Cyber Security ──
    "network security", "cryptography", "ethical hacking",
    "penetration testing", "wireshark", "nmap", "metasploit",
    "burp suite", "kali linux", "cybersecurity",
    "firewall", "ids", "ips", "vpn", "ssl", "tls",
    "tcp/ip", "dns", "http", "https", "osi model",
    "vulnerability assessment", "malware analysis",
    "digital forensics", "siem", "soc", "zero trust",
    "owasp", "cve", "reverse engineering",

    # ── Aerospace & Radar ──
    "signal processing", "radar", "simulink", "control systems",
    "matlab simulink", "aerospace", "avionics", "navigation",
    "gnss", "gps", "inertial navigation", "kalman filter",
    "pid controller", "flight dynamics", "propulsion",
    "antenna design", "rf engineering", "microwave",
    "dsp", "digital signal processing", "fft",
    "image processing", "lidar", "sonar",

    # ── Tools & DevOps ──
    "git", "github", "gitlab", "bitbucket",
    "docker", "kubernetes", "jenkins", "ci/cd",
    "linux", "ubuntu", "centos", "bash scripting",
    "aws", "azure", "google cloud", "gcp",
    "terraform", "ansible", "nginx", "apache",
    "postman", "swagger", "jira", "confluence",
    "vs code", "intellij", "eclipse", "pycharm",

    # ── Core CS Fundamentals ──
    "data structures", "algorithms", "object oriented programming",
    "oop", "design patterns", "system design",
    "operating systems", "computer networks", "dbms",
    "compiler design", "software engineering",
    "agile", "scrum", "version control",
    "problem solving", "debugging", "unit testing",
    "test driven development", "tdd", "api testing",

    # ── Mathematics & Statistics ──
    "linear algebra", "calculus", "probability",
    "statistics", "discrete mathematics", "graph theory",
    "numerical methods", "optimization",
]

# Common non-skill words to filter out during extraction
# These are words spaCy might pick up as noun phrases but are not skills
STOPWORDS_FOR_SKILLS = [
    "university", "college", "institute", "school", "department",
    "experience", "project", "internship", "work", "team",
    "management", "communication", "leadership", "presentation",
    "bachelor", "master", "degree", "cgpa", "gpa", "grade",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "delhi", "mumbai", "bangalore", "hyderabad", "chennai", "pune",
    "india", "drdo", "company", "organization", "role", "position",
    "responsibility", "achievement", "objective", "summary",
    "reference", "hobby", "interest", "language", "english", "hindi",
]