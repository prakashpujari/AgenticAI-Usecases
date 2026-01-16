# AI/ML Job Search - Project Index

## Quick Navigation

### 📋 Documentation
- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[JOB_SEARCH_GUIDE.md](JOB_SEARCH_GUIDE.md)** - Comprehensive documentation
- **[CONFIG_GUIDE.md](CONFIG_GUIDE.md)** - Advanced configuration options
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - What was built
- **[README.md](README.md)** - Original project README

### 💻 Source Code
- **[crew.py](src/ai_job_search/crew.py)** - Main crew orchestration
- **[custom_tool.py](src/ai_job_search/tools/custom_tool.py)** - JobSearchTool & JobAnalyzerTool
- **[agents.yaml](src/ai_job_search/config/agents.yaml)** - Agent configurations
- **[tasks.yaml](src/ai_job_search/config/tasks.yaml)** - Task definitions
- **[main.py](src/ai_job_search/main.py)** - Entry point

### 🔧 Examples & Config
- **[examples.py](examples.py)** - Tool usage examples
- **[pyproject.toml](pyproject.toml)** - Project dependencies
- **[.env](.env)** - Environment configuration (add your API keys)

## Getting Started

### 1. First Time Setup (5 minutes)
```bash
cd ai_job_search
uv sync
uv run ai_job_search
```

See **[QUICKSTART.md](QUICKSTART.md)** for detailed steps.

### 2. Understanding the System
Read **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** to understand:
- What was implemented
- How it works
- Key features

### 3. Using the Tools
Check **[JOB_SEARCH_GUIDE.md](JOB_SEARCH_GUIDE.md)** for:
- Tool documentation
- Agent descriptions
- Usage examples
- Customization options

### 4. Advanced Configuration
Visit **[CONFIG_GUIDE.md](CONFIG_GUIDE.md)** to learn:
- Agent configuration details
- Task customization
- Tool extensions
- Performance optimization
- Integration examples

## Project Structure Overview

```
ai_job_search/
├── 📂 src/ai_job_search/
│   ├── 📂 config/
│   │   ├── agents.yaml          (3 AI agents)
│   │   └── tasks.yaml           (3 job search tasks)
│   ├── 📂 tools/
│   │   └── custom_tool.py       (Search & Analysis tools)
│   ├── crew.py                  (Orchestration)
│   └── main.py                  (Entry point)
├── 📄 examples.py               (Usage examples)
├── 📄 pyproject.toml            (Dependencies)
├── 📄 QUICKSTART.md             (5-min setup)
├── 📄 JOB_SEARCH_GUIDE.md       (Full guide)
├── 📄 CONFIG_GUIDE.md           (Configuration)
├── 📄 IMPLEMENTATION_SUMMARY.md  (What's built)
└── 📄 INDEX.md                  (This file)
```

## What This System Does

### 🔍 Search
Finds AI/ML job opportunities across:
- Google Jobs
- LinkedIn
- Dice Job Board

### 📊 Analyze
Extracts from job postings:
- Required skills
- Experience level
- Job type (remote/on-site)
- Company information

### 📑 Report
Generates comprehensive reports with:
- Top opportunities
- Market trends
- Skill demand analysis
- Experience distribution
- Recommendations

## Core Components

### Agents (3 specialized AI agents)

1. **Job Searcher**
   - Searches multiple job boards
   - Finds relevant AI/ML positions
   - Provides structured results

2. **Job Analyzer**
   - Analyzes job postings
   - Extracts key information
   - Classifies roles

3. **Report Curator**
   - Synthesizes data
   - Creates insights
   - Generates recommendations

### Tools (2 powerful custom tools)

1. **JobSearchTool**
   - Multi-board search capability
   - Flexible filtering
   - Structured JSON output

2. **JobAnalyzerTool**
   - Skill extraction
   - Experience level detection
   - Job type classification

## Quick Commands

```bash
# Install dependencies
uv sync

# Run default job search (Machine Learning Engineer)
uv run ai_job_search

# Run tool examples
python examples.py

# Run specific job search (edit main.py first)
uv run ai_job_search

# Train the crew (advanced)
uv run --with crewai crewai train 5 results.json

# Test the crew (advanced)
uv run --with crewai crewai test 3 gpt-4
```

## Customization Examples

### Change Job Title
Edit `src/ai_job_search/main.py`:
```python
inputs = {
    'job_title': 'Data Scientist',  # Change this
}
```

### Add New Job Board
Edit `src/ai_job_search/tools/custom_tool.py`:
```python
def _search_new_board(self, query: str) -> list:
    # Implement search logic
    pass
```

### Modify Agent Behavior
Edit `src/ai_job_search/config/agents.yaml`:
```yaml
job_searcher:
  role: "Your custom role"
  goal: "Your custom goal"
  backstory: "Your custom backstory"
```

## File Purpose Summary

| File | Purpose | Edit for... |
|------|---------|------------|
| **crew.py** | Main orchestration | Agent/task binding |
| **agents.yaml** | Agent configs | Agent behavior |
| **tasks.yaml** | Task definitions | Task descriptions |
| **custom_tool.py** | Job search tools | Tool logic |
| **main.py** | Entry point | Input parameters |
| **examples.py** | Usage examples | Learning |
| **CONFIG_GUIDE.md** | Configuration help | Advanced setup |
| **JOB_SEARCH_GUIDE.md** | Full documentation | Comprehensive info |
| **QUICKSTART.md** | Quick setup | Getting started |

## Common Tasks

### I want to...

**Search for jobs in a new role**
→ Edit `job_title` in `main.py` → Run `uv run ai_job_search`
→ See [QUICKSTART.md](QUICKSTART.md)

**Understand how the system works**
→ Read [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
→ Review [JOB_SEARCH_GUIDE.md](JOB_SEARCH_GUIDE.md)

**Add a new job board**
→ Edit `custom_tool.py` to add search method
→ See [CONFIG_GUIDE.md](CONFIG_GUIDE.md)

**Change agent behavior**
→ Edit `agents.yaml` or `tasks.yaml`
→ See [CONFIG_GUIDE.md](CONFIG_GUIDE.md)

**Use tools directly in code**
→ Review `examples.py`
→ See [JOB_SEARCH_GUIDE.md](JOB_SEARCH_GUIDE.md#custom-tools)

**Deploy as API**
→ See [CONFIG_GUIDE.md](CONFIG_GUIDE.md#integration-examples)
→ Use FastAPI integration example

**Save results to database**
→ See [CONFIG_GUIDE.md](CONFIG_GUIDE.md#integration-examples)
→ Implement database saving

## Output Files Generated

After running the system:

- **ai_ml_jobs_report.md** - Comprehensive job market report
  - Generated in project root
  - Contains all findings and recommendations
  - Markdown formatted

## Dependencies

All required packages are in `pyproject.toml`:

```
crewai[tools]==1.8.1  # CrewAI framework
requests>=2.31.0      # HTTP requests
pydantic>=2.0.0       # Data validation
```

Install with: `uv sync`

## Environment Setup

Create `.env` file in project root:

```env
OPENAI_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here    # Optional, for advanced searches
```

## Support & Resources

**Official Documentation**
- [CrewAI Docs](https://docs.crewai.com/)
- [CrewAI GitHub](https://github.com/joaomdmoura/crewAI)

**Project Documentation**
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [JOB_SEARCH_GUIDE.md](JOB_SEARCH_GUIDE.md) - Full documentation
- [CONFIG_GUIDE.md](CONFIG_GUIDE.md) - Configuration help
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - What's built

**Code Examples**
- [examples.py](examples.py) - Tool usage examples
- [custom_tool.py](src/ai_job_search/tools/custom_tool.py) - Tool implementation

## Next Steps

1. **Run your first job search**
   ```bash
   cd ai_job_search && uv sync && uv run ai_job_search
   ```

2. **Read the documentation**
   - Start with [QUICKSTART.md](QUICKSTART.md)
   - Then [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
   - Advanced: [CONFIG_GUIDE.md](CONFIG_GUIDE.md)

3. **Customize for your needs**
   - Change job titles in `main.py`
   - Modify agents in `agents.yaml`
   - Extend tools in `custom_tool.py`

4. **Integrate with your systems**
   - Add to applications
   - Create REST API
   - Set up database storage
   - Build web interface

---

**Status**: ✅ Complete and Ready to Use

All features implemented, documented, and tested. Start with [QUICKSTART.md](QUICKSTART.md) for immediate usage!
