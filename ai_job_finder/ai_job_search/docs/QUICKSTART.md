# Quick Start Guide - AI/ML Job Search with CrewAI

## 5-Minute Setup

### 1. Prerequisites Check
```bash
# Verify Python 3.10+
python --version

# Verify UV is installed
uv --version
```

### 2. Navigate to Project
```bash
cd ai_job_search
```

### 3. Install Dependencies
```bash
# Using UV (recommended)
uv sync

# Alternative with pip
pip install crewai[tools] requests pydantic
```

### 4. Set API Keys (Optional)
Create `.env` file:
```env
OPENAI_API_KEY=your_key_here
```

### 5. Run the Job Search
```bash
# Default search for Machine Learning Engineer
uv run ai_job_search

# Or using Python directly
python -m ai_job_search.main
```

## Expected Output

When running, you'll see:
1. **Agent Activity Logs** - Shows what each agent is doing
2. **Task Progress** - Displays task completion
3. **Generated Report** - Creates `ai_ml_jobs_report.md`

## Common Commands

### Search for Different Job Titles

**Edit `src/ai_job_search/main.py`:**
```python
inputs = {
    'job_title': 'Data Scientist',  # Change this line
    'current_year': str(datetime.now().year)
}
```

Then run:
```bash
uv run ai_job_search
```

### Run Example Script
```bash
# Show tool usage examples
python examples.py
```

## Job Titles to Try

- Machine Learning Engineer
- Data Scientist
- AI Researcher
- Deep Learning Engineer
- NLP Engineer
- Computer Vision Engineer
- MLOps Engineer
- AI Product Manager

## File Structure

```
ai_job_search/
├── src/ai_job_search/
│   ├── config/
│   │   ├── agents.yaml          # Agent configurations
│   │   └── tasks.yaml           # Task definitions
│   ├── tools/
│   │   └── custom_tool.py       # Search and analysis tools
│   ├── crew.py                  # Main crew logic
│   └── main.py                  # Entry point
├── examples.py                  # Tool usage examples
├── JOB_SEARCH_GUIDE.md         # Full documentation
├── CONFIG_GUIDE.md              # Configuration details
└── QUICKSTART.md               # This file
```

## What's Happening?

The crew executes 3 tasks sequentially:

1. **search_ai_jobs** (Job Searcher Agent)
   - Searches Google Jobs, LinkedIn, Dice
   - Finds 15-20 relevant positions
   - Provides job titles, companies, locations, URLs

2. **analyze_job_requirements** (Job Analyzer Agent)
   - Extracts required skills from job postings
   - Determines experience level
   - Classifies job type (remote/on-site)

3. **generate_market_report** (Report Curator Agent)
   - Synthesizes all data
   - Identifies trends
   - Provides market insights
   - Generates recommendations

## Output Files

### ai_ml_jobs_report.md
Complete report containing:
- Job opportunities summary
- Required skills breakdown
- Experience level distribution
- Market trends
- Recommendations

## Troubleshooting

### Issue: "crewai not found"
```bash
# Install and update shell configuration
uv tool update-shell
uv run --with crewai crewai create crew test_crew
```

### Issue: API Key Error
1. Create `.env` file in project root
2. Add your OpenAI API key: `OPENAI_API_KEY=sk-...`
3. Run again

### Issue: Timeout Error
- Check internet connection
- Job boards may be slow to respond
- Increase timeout in `custom_tool.py`

### Issue: No Results
- Try different job title
- Check if job boards are accessible
- Ensure API key is valid

## Next Steps

1. **Explore the Code**
   - Read `JOB_SEARCH_GUIDE.md` for detailed docs
   - Review `src/ai_job_search/tools/custom_tool.py`

2. **Customize Configuration**
   - Edit `agents.yaml` to change agent behavior
   - Edit `tasks.yaml` to modify task descriptions
   - See `CONFIG_GUIDE.md` for advanced options

3. **Add New Features**
   - Add more job boards in `custom_tool.py`
   - Create new agents and tasks
   - Implement database storage
   - Add email notifications

4. **Integrate with Your Project**
   - Use as Python library in your code
   - Create API endpoint
   - Set up scheduled searches
   - Build web interface

## Example Use Cases

### 1. Personal Job Search
```python
# Modify main.py with your target role
inputs = {
    'job_title': 'Senior Machine Learning Engineer',
}
```

### 2. Market Research
```python
# Search multiple positions
titles = ["ML Engineer", "Data Scientist", "NLP Engineer"]
for title in titles:
    # Run crew for each
```

### 3. Skill Gap Analysis
Extract required skills across positions to identify:
- Most in-demand skills
- Skill combinations
- Experience requirements

### 4. Company Insights
Analyze which companies are hiring:
- Number of openings
- Preferred locations
- Tech stack requirements

## Resources

- [CrewAI Documentation](https://docs.crewai.com/)
- [CrewAI GitHub](https://github.com/joaomdmoura/crewAI)
- [Job Search Guide](JOB_SEARCH_GUIDE.md)
- [Configuration Guide](CONFIG_GUIDE.md)

## Tips & Tricks

### Run Specific Job Search
```python
from ai_job_search.tools.custom_tool import JobSearchTool

tool = JobSearchTool()
results = tool._run("Data Scientist", job_board="linkedin")
```

### Parse Report Output
```python
import json

with open('ai_ml_jobs_report.md', 'r') as f:
    report_content = f.read()
    # Process report
```

### Enable Debug Mode
```python
# In main.py
AiJobSearch().crew().kickoff(inputs=inputs)
# Add verbose logging
```

## Support & Questions

- Check [JOB_SEARCH_GUIDE.md](JOB_SEARCH_GUIDE.md) for FAQ
- Review [CONFIG_GUIDE.md](CONFIG_GUIDE.md) for advanced configuration
- Visit [CrewAI Docs](https://docs.crewai.com/) for framework help

---

**Ready to find your next AI/ML opportunity?** 🚀

```bash
uv run ai_job_search
```
