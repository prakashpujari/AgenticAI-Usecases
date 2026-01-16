# AI/ML Job Search System Architecture

## System Workflow

```
START
  ↓
┌─────────────────────────────────────────────────────────────┐
│                   CREW INITIALIZATION                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  agents.yaml + tasks.yaml → AiJobSearch Crew          │ │
│  │  • Job Searcher Agent                                  │ │
│  │  • Job Analyzer Agent                                  │ │
│  │  • Report Curator Agent                                │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────────┐
│                   TASK 1: SEARCH_AI_JOBS                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Agent: Job Searcher                                   │ │
│  │  Tool: JobSearchTool                                   │ │
│  │                                                         │ │
│  │  Input: {job_title: "Machine Learning Engineer"}       │ │
│  │                                                         │ │
│  │  Searches:                                              │ │
│  │  • Google Jobs ──→ Job List 1                          │ │
│  │  • LinkedIn    ──→ Job List 2                          │ │
│  │  • Dice        ──→ Job List 3                          │ │
│  │                                                         │ │
│  │  Output: Combined JSON with 15-20 job opportunities   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────────┐
│               TASK 2: ANALYZE_JOB_REQUIREMENTS              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Agent: Job Analyzer                                   │ │
│  │  Tool: JobAnalyzerTool                                 │ │
│  │                                                         │ │
│  │  Input: JSON job listings from Task 1                  │ │
│  │                                                         │ │
│  │  Analysis:                                              │ │
│  │  • Extract Skills ────→ [Python, TensorFlow, ...]      │ │
│  │  • Experience Level ──→ [Junior, Mid, Senior]          │ │
│  │  • Job Type ──────────→ [Remote, On-site]              │ │
│  │                                                         │ │
│  │  Output: Analyzed jobs with extracted metadata         │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────────┐
│            TASK 3: GENERATE_MARKET_REPORT                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Agent: Report Curator                                 │ │
│  │  Tools: None (uses LLM reasoning)                       │ │
│  │                                                         │ │
│  │  Input: Analysis from Task 2                           │ │
│  │                                                         │ │
│  │  Report Sections:                                       │ │
│  │  • Market Overview                                      │ │
│  │  • Top Opportunities                                    │ │
│  │  • Required Skills Breakdown                            │ │
│  │  • Experience Level Distribution                        │ │
│  │  • Hiring Trends                                        │ │
│  │  • Recommendations                                      │ │
│  │                                                         │ │
│  │  Output: ai_ml_jobs_report.md                          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
  ↓
  ✓ COMPLETE
```

## Component Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    AI JOB SEARCH SYSTEM                      │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               CREW LAYER (crew.py)                 │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │    │
│  │  │ Job Searcher │  │ Job Analyzer │  │ Curator  │ │    │
│  │  └──────────────┘  └──────────────┘  └──────────┘ │    │
│  └─────────────────────────────────────────────────────┘    │
│                          ↓                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              TOOLS LAYER (custom_tool.py)          │    │
│  │                                                     │    │
│  │  ┌──────────────────────┐ ┌────────────────────┐  │    │
│  │  │ JobSearchTool        │ │ JobAnalyzerTool    │  │    │
│  │  │ • Google Jobs        │ │ • Skill Extraction │  │    │
│  │  │ • LinkedIn           │ │ • Level Detection  │  │    │
│  │  │ • Dice               │ │ • Type Detection   │  │    │
│  │  └──────────────────────┘ └────────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
│                          ↓                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           CONFIGURATION LAYER (YAML)               │    │
│  │  ┌────────────────────┐  ┌────────────────────┐   │    │
│  │  │ agents.yaml        │  │ tasks.yaml         │   │    │
│  │  │ • Roles            │  │ • Descriptions     │   │    │
│  │  │ • Goals            │  │ • Expected Outputs │   │    │
│  │  │ • Backstories      │  │ • Agent Mapping    │   │    │
│  │  └────────────────────┘  └────────────────────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow

```
┌─────────────────────────────────────────────────────────┐
│  INPUT: main.py                                        │
│  {                                                      │
│    'job_title': 'Machine Learning Engineer',           │
│    'current_year': '2026'                              │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│  SEARCH PHASE (JobSearchTool._run)                      │
│                                                        │
│  Query ────┬──→ Google Jobs API ──→ [Jobs]            │
│            ├──→ LinkedIn API      ──→ [Jobs]            │
│            └──→ Dice API          ──→ [Jobs]            │
│                                                        │
│  Output: JSON Array of Job Objects                      │
│  [                                                     │
│    {                                                   │
│      "source": "Google Jobs",                          │
│      "title": "ML Engineer",                           │
│      "company": "Company A",                           │
│      "url": "https://...",                             │
│      "location": "San Francisco"                       │
│    },                                                  │
│    ...                                                 │
│  ]                                                     │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│  ANALYSIS PHASE (JobAnalyzerTool._run)                 │
│                                                        │
│  For Each Job:                                          │
│  • Extract Skills ─────→ ["Python", "TensorFlow"]     │
│  • Detect Level ───────→ "Senior (5+ years)"          │
│  • Classify Type ──────→ "Remote"                      │
│                                                        │
│  Output: Analyzed Job Objects                           │
│  [                                                     │
│    {                                                   │
│      "title": "ML Engineer",                           │
│      "required_skills": ["Python", "TensorFlow"],      │
│      "experience_level": "Senior (5+ years)",          │
│      "job_type": "Remote",                             │
│      ...                                               │
│    },                                                  │
│    ...                                                 │
│  ]                                                     │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│  REPORTING PHASE (Report Curator Agent)                │
│                                                        │
│  LLM Reasoning:                                        │
│  • Identify Top Opportunities                          │
│  • Extract Skill Trends                                │
│  • Analyze Experience Distribution                     │
│  • Identify Market Patterns                            │
│  • Generate Recommendations                            │
│                                                        │
│  Output: ai_ml_jobs_report.md                          │
│  ─────────────────────────────────────────────────     │
│  # AI/ML Job Market Report                             │
│                                                        │
│  ## Executive Summary                                  │
│  ...                                                   │
│                                                        │
│  ## Top Opportunities                                  │
│  ...                                                   │
│                                                        │
│  ## Skills Demand                                      │
│  ...                                                   │
│                                                        │
│  ## Recommendations                                    │
│  ...                                                   │
└─────────────────────────────────────────────────────────┘
```

## Agent Interaction

```
┌─────────────────────────────────────────────────────────┐
│                  JOB SEARCHER AGENT                     │
│                                                        │
│  Role: AI/ML Job Search Specialist                    │
│  Goal: Find best opportunities                        │
│  Tools: JobSearchTool                                 │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Workflow:                                         │ │
│  │ 1. Receive job_title from main.py               │ │
│  │ 2. Activate JobSearchTool                        │ │
│  │ 3. Search all three boards                       │ │
│  │ 4. Compile results                               │ │
│  │ 5. Pass to Job Analyzer Agent                    │ │
│  └──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
           ↓ (Sequential)
┌─────────────────────────────────────────────────────────┐
│                  JOB ANALYZER AGENT                     │
│                                                        │
│  Role: AI/ML Job Analysis Expert                      │
│  Goal: Extract key requirements                       │
│  Tools: JobAnalyzerTool                               │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Workflow:                                         │ │
│  │ 1. Receive job listings from Job Searcher       │ │
│  │ 2. Activate JobAnalyzerTool                      │ │
│  │ 3. Analyze each job posting                      │ │
│  │ 4. Extract skills, levels, types                │ │
│  │ 5. Pass analysis to Report Curator               │ │
│  └──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
           ↓ (Sequential)
┌─────────────────────────────────────────────────────────┐
│                 REPORT CURATOR AGENT                    │
│                                                        │
│  Role: Job Market Report Curator                      │
│  Goal: Create comprehensive report                    │
│  Tools: None (uses reasoning)                         │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Workflow:                                         │ │
│  │ 1. Receive analysis from Job Analyzer            │ │
│  │ 2. Use reasoning to identify patterns             │ │
│  │ 3. Extract insights and trends                   │ │
│  │ 4. Generate recommendations                      │ │
│  │ 5. Write comprehensive report                    │ │
│  │ 6. Save to ai_ml_jobs_report.md                  │ │
│  └──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Tool Architecture

```
┌────────────────────────────────────────────────────────┐
│            JOBSEARCHTOOL                               │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Input Schema:                                         │
│  • job_query: str (required)                           │
│  • job_board: str (optional, default="all")            │
│                                                        │
│  Methods:                                              │
│  ┌─────────────────────────────────────────────────┐  │
│  │ _run(job_query, job_board)                      │  │
│  │ ├─ _search_google_jobs(query)                   │  │
│  │ ├─ _search_linkedin_jobs(query)                 │  │
│  │ └─ _search_dice_jobs(query)                     │  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
│  Output: JSON Array of Job Objects                    │
│  └─────────────────────────────────────────────────┐  │
│    [                                                  │  │
│      {                                                │  │
│        "source": "LinkedIn Jobs",                    │  │
│        "title": "ML Engineer",                       │  │
│        "company": "Tech Corp",                       │  │
│        "url": "https://...",                         │  │
│        "location": "Remote",                         │  │
│        "type": "Job Board"                           │  │
│      },                                              │  │
│      ...                                              │  │
│    ]                                                 │  │
│  └─────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
           ↓ (Output passed to JobAnalyzerTool)
┌────────────────────────────────────────────────────────┐
│            JOBANALYZERTOOL                             │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Input Schema:                                         │
│  • job_data: str (JSON string)                        │
│                                                        │
│  Methods:                                              │
│  ┌─────────────────────────────────────────────────┐  │
│  │ _run(job_data)                                  │  │
│  │ ├─ _extract_skills(job_title)                   │  │
│  │ └─ _determine_experience_level(job_title)       │  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
│  Output: JSON Array of Analyzed Jobs                  │
│  └─────────────────────────────────────────────────┐  │
│    [                                                  │  │
│      {                                                │  │
│        "title": "ML Engineer",                       │  │
│        "company": "Tech Corp",                       │  │
│        "required_skills": [                          │  │
│          "Python",                                   │  │
│          "Machine Learning",                         │  │
│          "TensorFlow"                                │  │
│        ],                                             │  │
│        "experience_level": "Senior (5+ years)",      │  │
│        "job_type": "Remote",                         │  │
│        "url": "https://..."                          │  │
│      },                                              │  │
│      ...                                              │  │
│    ]                                                 │  │
│  └─────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

## Configuration Structure

```
┌─────────────────────────────────────────────────────┐
│              YAML CONFIGURATION                     │
├─────────────────────────────────────────────────────┤
│                                                    │
│  agents.yaml:                                      │
│  ┌────────────────────────────────────────────┐   │
│  │ job_searcher:                              │   │
│  │   role: "AI/ML Job Search Specialist"     │   │
│  │   goal: "Find best opportunities"         │   │
│  │   backstory: "Expert in..."               │   │
│  │                                             │   │
│  │ job_analyzer:                              │   │
│  │   role: "AI/ML Job Analysis Expert"       │   │
│  │   goal: "Extract requirements"            │   │
│  │   backstory: "Detailed analyst..."        │   │
│  │                                             │   │
│  │ report_curator:                            │   │
│  │   role: "Report Curator"                  │   │
│  │   goal: "Create reports"                  │   │
│  │   backstory: "Skilled writer..."          │   │
│  └────────────────────────────────────────────┘   │
│                                                    │
│  tasks.yaml:                                       │
│  ┌────────────────────────────────────────────┐   │
│  │ search_ai_jobs:                            │   │
│  │   description: "Search for positions"     │   │
│  │   expected_output: "List of jobs"         │   │
│  │   agent: job_searcher                      │   │
│  │                                             │   │
│  │ analyze_job_requirements:                  │   │
│  │   description: "Analyze postings"         │   │
│  │   expected_output: "Analyzed data"        │   │
│  │   agent: job_analyzer                      │   │
│  │                                             │   │
│  │ generate_market_report:                    │   │
│  │   description: "Create report"            │   │
│  │   expected_output: "Report markdown"      │   │
│  │   agent: report_curator                    │   │
│  └────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Execution Timeline

```
Time  │  Activity
──────┼──────────────────────────────────────────────
 t=0  │  ├─ Start: uv run ai_job_search
      │  └─ Load crew configuration
──────┼──────────────────────────────────────────────
 t=1  │  ├─ Initialize agents and tools
      │  └─ Parse input parameters
──────┼──────────────────────────────────────────────
 t=2  │  ├─ Task 1: Search AI Jobs (RUNNING)
      │  │  ├─ Job Searcher Agent activated
      │  │  ├─ JobSearchTool called
      │  │  ├─ Search Google Jobs
      │  │  ├─ Search LinkedIn Jobs
      │  │  ├─ Search Dice Jobs
      │  │  └─ Compile results
──────┼──────────────────────────────────────────────
 t=3  │  ├─ Task 1 COMPLETED
      │  ├─ Task 2: Analyze Jobs (RUNNING)
      │  │  ├─ Job Analyzer Agent activated
      │  │  ├─ JobAnalyzerTool called
      │  │  ├─ Extract skills per job
      │  │  ├─ Detect experience levels
      │  │  ├─ Classify job types
      │  │  └─ Compile analysis
──────┼──────────────────────────────────────────────
 t=4  │  ├─ Task 2 COMPLETED
      │  ├─ Task 3: Generate Report (RUNNING)
      │  │  ├─ Report Curator Agent activated
      │  │  ├─ Analyze patterns
      │  │  ├─ Extract trends
      │  │  ├─ Generate insights
      │  │  └─ Write report
──────┼──────────────────────────────────────────────
 t=5  │  ├─ Task 3 COMPLETED
      │  ├─ Save ai_ml_jobs_report.md
      │  └─ End: Process complete ✓
──────┴──────────────────────────────────────────────
```

## Output Files Generated

```
ai_job_search/
├── ai_ml_jobs_report.md          ← Main Output
│   ├── Executive Summary
│   ├── Top Job Opportunities
│   ├── Required Skills Analysis
│   ├── Experience Level Distribution
│   ├── Market Trends
│   └── Recommendations
│
└── Console Output
    ├── Agent Activity Logs
    ├── Task Progress
    ├── Tool Execution Details
    └── Final Summary
```

---

This architecture ensures reliable, modular, and extensible job search automation.
