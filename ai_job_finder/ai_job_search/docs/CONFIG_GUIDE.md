# AI/ML Job Search Configuration Guide

## Overview

This guide explains how to configure the AI/ML Job Search crew for different use cases and requirements.

## Agent Configuration (agents.yaml)

Each agent has three main components:

### 1. Role
Defines what the agent specializes in.

**Example:**
```yaml
job_searcher:
  role: >
    AI/ML Job Search Specialist
```

**Tips:**
- Be specific about the domain
- Include relevant keywords
- Keep it concise but descriptive

### 2. Goal
Defines what the agent aims to accomplish.

**Example:**
```yaml
  goal: >
    Find the best AI and Machine Learning job opportunities from top job boards
```

**Tips:**
- Should align with the role
- Focus on the outcome, not the process
- Use action verbs

### 3. Backstory
Provides context and personality to the agent.

**Example:**
```yaml
  backstory: >
    You're an expert job researcher with deep knowledge of the AI/ML job market.
    You excel at finding relevant positions across Google Jobs, LinkedIn, and Dice.
```

**Tips:**
- Add relevant experience
- Create believable expertise
- Can reference specific skills

## Task Configuration (tasks.yaml)

Each task defines what an agent should do:

### Task Components

1. **description**: What the agent should accomplish
```yaml
description: >
  Search for {job_title} positions on Google Jobs, LinkedIn, and Dice.
```

2. **expected_output**: What you want the agent to produce
```yaml
expected_output: >
  A comprehensive list of 15-20 AI/ML job opportunities with titles, companies,
  locations, and direct links to the job postings from all three job boards.
```

3. **agent**: Which agent should execute this task
```yaml
agent: job_searcher
```

## Tool Configuration

Tools are defined in `src/ai_job_search/tools/custom_tool.py`

### JobSearchTool

**Configuration:**
```python
class JobSearchTool(BaseTool):
    name: str = "AI/ML Job Search Tool"
    description: str = "Search for AI/ML related jobs..."
```

**Supported Job Boards:**
- Google Jobs
- LinkedIn
- Dice

**Customization:**
To add a new job board, add a new method:
```python
def _search_new_board(self, query: str) -> list:
    """Search new job board for positions"""
    # Implementation here
    pass
```

Then update the `_run` method to include it:
```python
if job_board in ["all", "new_board"]:
    new_board_jobs = self._search_new_board(job_query)
    jobs.extend(new_board_jobs)
```

### JobAnalyzerTool

**Configuration:**
```python
class JobAnalyzerTool(BaseTool):
    name: str = "Job Analyzer Tool"
    description: str = "Analyze job listings..."
```

**Customization:**
To modify skill detection:
```python
def _extract_skills(self, job_title: str) -> list:
    ai_ml_skills = {
        "skill_name": "Display Name",
        # Add more skills
    }
```

To change experience level detection:
```python
def _determine_experience_level(self, job_title: str) -> str:
    title_lower = job_title.lower()
    if "senior" in title_lower:
        return "Senior (5+ years)"
```

## Crew Configuration (crew.py)

### Process Types

1. **Sequential** (Default)
```python
process=Process.sequential
```
Tasks execute one after another. Each task waits for the previous one to complete.

2. **Hierarchical**
```python
process=Process.hierarchical
```
One agent coordinates others. More complex but can handle dependencies better.

### Adding New Agents

```python
@agent
def new_agent(self) -> Agent:
    return Agent(
        config=self.agents_config['new_agent'],
        tools=[ToolName()],  # Add tools here
        verbose=True
    )
```

### Adding New Tasks

```python
@task
def new_task(self) -> Task:
    return Task(
        config=self.tasks_config['new_task'],
        output_file='optional_file.md'  # Optional output file
    )
```

## Environment Variables (.env)

Create a `.env` file in the project root:

```env
# LLM Configuration
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

# Search API Keys (if using real APIs)
TAVILY_API_KEY=your_key_here
SERPER_API_KEY=your_key_here

# Other Configuration
LOG_LEVEL=INFO
DEBUG_MODE=False
```

## Input Parameters

Default inputs in `main.py`:

```python
inputs = {
    'job_title': 'Machine Learning Engineer',  # Change this
    'current_year': str(datetime.now().year)
}
```

### Common Job Titles to Search

- Machine Learning Engineer
- Data Scientist
- AI Researcher
- Deep Learning Engineer
- NLP Engineer
- Computer Vision Engineer
- MLOps Engineer
- AI Product Manager
- Data Engineer
- AI Solutions Architect

## Output Configuration

### Report Output

The report is generated to: `ai_ml_jobs_report.md`

Change in crew.py:
```python
output_file='custom_report_name.md'
```

### Console Output

Control verbosity with:
```python
verbose=True   # Show detailed logs
verbose=False  # Minimal output
```

## Performance Optimization

### Timeout Configuration

In tools, add timeout to requests:
```python
response = requests.get(url, headers=headers, timeout=5)  # 5 second timeout
```

### Caching

Store results to avoid redundant searches:
```python
import json
from datetime import datetime

def cache_results(results, filename):
    with open(f"cache/{filename}_{datetime.now().date()}.json", "w") as f:
        json.dump(results, f)
```

### Parallel Processing

Consider using asyncio for concurrent searches:
```python
import asyncio

async def search_all_boards(query):
    results = await asyncio.gather(
        self._search_google_jobs(query),
        self._search_linkedin_jobs(query),
        self._search_dice_jobs(query)
    )
    return results
```

## Filtering and Constraints

### Job Title Filtering

Modify search to exclude certain terms:
```python
excluded_keywords = ["manager", "director", "executive"]

def is_relevant_job(title):
    return not any(keyword.lower() in title.lower() 
                   for keyword in excluded_keywords)
```

### Experience Level Filtering

```python
def filter_by_experience(jobs, min_level="Junior", max_level="Senior"):
    level_order = ["Junior", "Mid-Level", "Senior"]
    # Implementation
    pass
```

## Testing Configuration

### Test Multiple Job Titles

Modify `main.py`:
```python
def run_multiple_searches():
    job_titles = [
        "Machine Learning Engineer",
        "Data Scientist",
        "AI Researcher"
    ]
    
    for title in job_titles:
        inputs = {'job_title': title, 'current_year': str(datetime.now().year)}
        AiJobSearch().crew().kickoff(inputs=inputs)
```

### Debugging

Enable verbose output:
```python
crew = Crew(
    agents=self.agents,
    tasks=self.tasks,
    verbose=True,  # Enable detailed logging
    process=Process.sequential
)
```

## Integration Examples

### With Database

```python
import sqlite3

def save_jobs_to_db(jobs):
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    for job in jobs:
        cursor.execute('''INSERT INTO jobs VALUES (?, ?, ?, ?)''',
                      (job['title'], job['company'], job['url'], job['source']))
    conn.commit()
    conn.close()
```

### With Email Notifications

```python
import smtplib
from email.mime.text import MIMEText

def send_job_alert(email, jobs):
    message = MIMEText(f"Found {len(jobs)} new AI/ML jobs!")
    # Send email implementation
    pass
```

### With Web API

```python
from fastapi import FastAPI

app = FastAPI()

@app.post("/search-jobs")
def search_jobs(job_title: str):
    inputs = {'job_title': job_title, 'current_year': str(datetime.now().year)}
    result = AiJobSearch().crew().kickoff(inputs=inputs)
    return {"result": result}
```

## Troubleshooting Configuration

### Agent Not Using Tool

Ensure tool is registered in agent:
```python
Agent(
    config=self.agents_config['agent_name'],
    tools=[YourTool()],  # Must be included
    verbose=True
)
```

### Task Not Running

Check task is registered in crew:
```python
@crew
def crew(self) -> Crew:
    return Crew(
        agents=self.agents,  # Auto-created by @agent
        tasks=self.tasks,    # Auto-created by @task
        # ...
    )
```

### Missing Dependencies

Update pyproject.toml and reinstall:
```bash
uv sync
```

## Best Practices

1. **Use Templates**: Use {variable} syntax in YAML for dynamic content
2. **Descriptive Names**: Use clear agent and task names
3. **Tool Documentation**: Add clear descriptions to tools
4. **Error Handling**: Include try-except blocks in tools
5. **Logging**: Use verbose mode for debugging
6. **Testing**: Test with different job titles
7. **Documentation**: Keep README and guides updated
8. **Version Control**: Track config changes in git
