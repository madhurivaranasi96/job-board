"""Public matching profile — no phone, email, or resume document."""

PROFILE = {
    "name": "Madhuri Varanasi",
    "headline": "Senior Software Engineer · C# .NET · Angular · Agentic AI",
    "years_experience": 7,
    "location": "Hyderabad, India",
    "skills": [
        "C#", ".NET", "ASP.NET", "ASP.NET MVC", "Web API", "REST", "Angular",
        "AngularJS", "JavaScript", "TypeScript", "Debugging", "Root Cause Analysis",
        "Production Support", "Code Review", "Agile", "Git", "Jenkins",
        "GitHub Actions", "Agentic AI", "LLM", "Multi-Agent Workflows", "AI Automation",
    ],
    "preferred_titles": [
        "Senior Software Engineer", "Software Engineer", "Full Stack Engineer",
        ".NET Developer", "C# Developer", "Backend Engineer", "Frontend Engineer",
        "Angular Developer", "Software Developer", "Application Engineer",
        "Production Support Engineer", "Technical Support Engineer",
        "AI Engineer", "AI Software Engineer", "Agentic AI Engineer",
    ],
    "preferred_technologies": [
        "C#", ".NET", "ASP.NET", "Web API", "Angular", "AngularJS",
        "JavaScript", "TypeScript", "REST", "SQL", "Azure", "AWS", "AI", "LLM",
    ],
    "domain_keywords": [
        "banking", "atm", "payments", "fintech", "financial", "ndc", "ndce",
        "enterprise", "production support", "customer support", "transaction",
    ],
    "preferred_industries": [
        "Banking", "Financial Services", "ATM / Payments", "FinTech",
        "Enterprise Software", "Technology",
    ],
    "preferred_countries": [
        "United States", "Canada", "United Kingdom", "Ireland", "Germany",
        "Netherlands", "France", "Switzerland", "Sweden", "Norway", "Denmark",
        "Finland", "Belgium", "Austria", "Spain", "Portugal", "Poland",
        "Czech Republic", "Australia", "New Zealand", "Singapore",
        "United Arab Emirates", "Saudi Arabia", "Qatar", "Japan",
        "South Korea", "India",
    ],
    "relocation": True,
    "visa_preference": "sponsorship",
    "remote_preference": "any",
}

TITLE_KEEP = [
    "software engineer", "software developer", "full stack", "fullstack", "full-stack",
    ".net", "dotnet", "c#", "csharp", "angular", "backend", "back-end", "frontend",
    "front-end", "application engineer", "production support", "technical support engineer",
    "ai engineer", "ai software", "agentic", "llm", "web api", "asp.net",
    "typescript", "javascript engineer", "platform engineer", "application developer",
    "site reliability",  # keep a few SRE if stack matches later
    "staff software", "principal software", "lead software", "lead engineer",
    "senior engineer", "senior developer", "senior full", "net developer",
]

TITLE_DROP = [
    "account executive", "sales manager", "sales development", "recruiter",
    "talent acquisition", "talent partner", "sourcing recruiter",
    "marketing manager", "content writer", "copywriter",
    "general counsel", "attorney", "paralegal",
    "registered nurse", "physician", "warehouse", "forklift",
    "account manager", "customer success manager",
    "hardware engineer", "mechanical engineer", "electrical engineer",
    "civil engineer", "chef", "barista", "driver",
    "data entry", "receptionist", "security guard",
]
