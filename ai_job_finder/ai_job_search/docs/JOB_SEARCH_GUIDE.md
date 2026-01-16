# AI/ML Job Search Automation with CrewAI

This project uses CrewAI to automate the search and analysis of AI/ML job opportunities across multiple job boards: Google Jobs, LinkedIn, and Dice.

## Overview

The system consists of three specialized agents working together:

1. **Job Searcher**: Searches for AI/ML positions across Google Jobs, LinkedIn, and Dice
2. **Job Analyzer**: Analyzes job postings to extract requirements, skills, and qualifications
3. **Report Curator**: Generates comprehensive market reports with insights and recommendations

## Project Structure

```
ai_job_search/
├── src/ai_job_search/
│   ├── config/
│   │   ├── agents.yaml          # Agent configurations
│   │   └── tasks.yaml           # Task definitions
│   ├── tools/
│   │   └── custom_tool.py       # JobSearchTool and JobAnalyzerTool
│   ├── crew.py                  # Main crew definition
│   └── main.py                  # Entry point
├── pyproject.toml               # Project dependencies
└── README.md                    # Original README
```

## Installation

### Prerequisites
- Python 3.10+
- UV package manager (recommended)

### Setup

1. Navigate to the project directory:
```bash
cd ai_job_search
```

2. Install dependencies:
```bash
# Using UV
uv sync

# Or using pip
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the project root and add your API keys if needed:
```env
OPENAI_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
```

## Usage

### Basic Job Search

Run a job search for Machine Learning Engineer positions:

```bash
# Using UV
uv run ai_job_search

# Or directly
python -m ai_job_search.main
```

### Custom Job Search

To search for a specific job title, modify the `job_title` in `main.py`:

```python
inputs = {
    'job_title': 'Data Scientist',  # Change this
    'current_year': str(datetime.now().year)
}
```

Then run:
```bash
uv run ai_job_search
```

### Available Job Titles to Search

- Machine Learning Engineer
- Data Scientist
- AI Researcher
- Deep Learning Engineer
- NLP Engineer
- Computer Vision Engineer
- MLOps Engineer
- AI Product Manager

## Custom Tools

### JobSearchTool

Searches across multiple job boards for AI/ML positions.

**Input:**
- `job_query`: The job title or keywords to search for (e.g., "Machine Learning Engineer")
- `job_board`: Optional - specify 'all', 'google', 'linkedin', or 'dice' (default: 'all')

**Output:**
- List of job listings with titles, companies, locations, and URLs

**Example:**
```python
tool = JobSearchTool()
result = tool._run(
    job_query="Machine Learning Engineer",
    job_board="all"
)
```

### JobAnalyzerTool

Analyzes job listings to extract key information.

**Input:**
- `job_data`: JSON string containing job listings

**Output:**
- Analyzed jobs with extracted skills, experience level, and job type

**Example:**
```python
tool = JobAnalyzerTool()
result = tool._run(job_data=json.dumps(jobs))
```

## Agents

### Job Searcher Agent

- **Role**: AI/ML Job Search Specialist
- **Goal**: Find the best AI and ML job opportunities
- **Tools**: JobSearchTool
- **Responsibilities**:
  - Search across Google Jobs, LinkedIn, and Dice
  - Identify relevant positions
  - Provide direct links to job postings

### Job Analyzer Agent

- **Role**: AI/ML Job Analysis Expert
- **Goal**: Analyze job postings for key requirements
- **Tools**: JobAnalyzerTool
- **Responsibilities**:
  - Extract required skills
  - Identify experience levels
  - Determine job type (remote/on-site)
  - Analyze compensation and company details

### Report Curator Agent

- **Role**: Job Market Report Curator
- **Goal**: Create comprehensive reports
- **Tools**: None (uses LLM reasoning)
- **Responsibilities**:
  - Synthesize job data
  - Identify market trends
  - Provide actionable insights
  - Generate recommendations

## Output

After running, you'll get:

1. **ai_ml_jobs_report.md**: A comprehensive markdown report containing:
   - Market overview
   - Top job opportunities
   - Required skills breakdown
   - Experience level distribution
   - Hiring trends
   - Actionable recommendations

2. **Console output**: Detailed logs of agent activities and reasoning

## Advanced Usage

### Training the Crew

Train the crew on multiple iterations:

```bash
uv run --with crewai crewai train 5 training_results.json
```

### Testing the Crew

Test with evaluation:

```bash
uv run --with crewai crewai test 3 gpt-4
```

### Replaying Tasks

Replay from a specific task:

```bash
uv run --with crewai crewai replay <task_id>
```

## Customization

### Add New Job Boards

Edit `src/ai_job_search/tools/custom_tool.py`:

```python
def _search_new_board(self, query: str) -> list:
    """Search new job board"""
    # Implement board-specific search logic
    pass
```

### Modify Agent Behavior

Edit `src/ai_job_search/config/agents.yaml` to change agent roles and goals.

### Change Task Requirements

Edit `src/ai_job_search/config/tasks.yaml` to modify task descriptions and expected outputs.

## Features

✅ Multi-board job search (Google, LinkedIn, Dice)
✅ Automatic skill extraction
✅ Experience level detection
✅ Job type classification
✅ Comprehensive market reports
✅ Structured data output (JSON)
✅ Sequential agent workflow
✅ Detailed logging

## Future Enhancements

- [ ] Salary range estimation
- [ ] Company profile integration
- [ ] Skills gap analysis
- [ ] Personalized recommendations
- [ ] Job alert subscription
- [ ] Real-time job board scraping with Selenium
- [ ] Database integration for tracking
- [ ] Email notifications
- [ ] Web interface
- [ ] API endpoint for programmatic access

## Troubleshooting

### Issue: crewai command not found
**Solution**: Use `uv run` prefix or install globally with `uv pip install crewai`

### Issue: API key errors
**Solution**: Ensure `.env` file has correct API keys set

### Issue: Job search returns no results
**Solution**: Try different job titles or check internet connection

## Dependencies

- **crewai**: AI agent framework
- **requests**: HTTP library for web requests
- **pydantic**: Data validation

## License

MIT

## Support

For issues and questions, please check the [CrewAI documentation](https://docs.crewai.com/)

## Contributing

Contributions are welcome! Please submit pull requests with improvements.
