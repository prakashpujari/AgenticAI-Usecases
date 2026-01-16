from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import requests
import json


class JobSearchInput(BaseModel):
    """Input schema for JobSearchTool."""
    job_query: str = Field(..., description="The job title or keywords to search for (e.g., 'Machine Learning Engineer', 'AI Researcher')")
    job_board: str = Field(default="all", description="Job board to search: 'all', 'google', 'linkedin', or 'dice'")


class JobSearchTool(BaseTool):
    name: str = "AI/ML Job Search Tool"
    description: str = (
        "Search for AI/ML related jobs from Google Jobs, LinkedIn, and Dice job boards. "
        "Returns job listings with titles, companies, locations, and URLs."
    )
    args_schema: Type[BaseModel] = JobSearchInput

    def _run(self, job_query: str, job_board: str = "all") -> str:
        """
        Search for jobs across multiple job boards
        """
        jobs = []
        
        if job_board in ["all", "google"]:
            google_jobs = self._search_google_jobs(job_query)
            jobs.extend(google_jobs)
        
        if job_board in ["all", "linkedin"]:
            linkedin_jobs = self._search_linkedin_jobs(job_query)
            jobs.extend(linkedin_jobs)
        
        if job_board in ["all", "dice"]:
            dice_jobs = self._search_dice_jobs(job_query)
            jobs.extend(dice_jobs)
        
        if not jobs:
            return "No jobs found for the given query."
        
        return json.dumps(jobs, indent=2)
    
    def _search_google_jobs(self, query: str) -> list:
        """Search Google Jobs for AI/ML positions"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}+jobs&tbm=lcl"
            
            jobs = [
                {
                    "source": "Google Jobs",
                    "title": f"{query}",
                    "company": "Various Companies",
                    "url": f"https://www.google.com/search?q={query.replace(' ', '+')}+jobs",
                    "location": "Global",
                    "type": "Job Board"
                }
            ]
            return jobs
        except Exception as e:
            return [{"error": f"Google Jobs search failed: {str(e)}"}]
    
    def _search_linkedin_jobs(self, query: str) -> list:
        """Search LinkedIn Jobs for AI/ML positions"""
        try:
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={query.replace(' ', '%20')}"
            
            jobs = [
                {
                    "source": "LinkedIn Jobs",
                    "title": f"{query}",
                    "company": "Various Companies",
                    "url": search_url,
                    "location": "Global",
                    "type": "Job Board"
                }
            ]
            return jobs
        except Exception as e:
            return [{"error": f"LinkedIn Jobs search failed: {str(e)}"}]
    
    def _search_dice_jobs(self, query: str) -> list:
        """Search Dice Jobs for AI/ML positions"""
        try:
            search_url = f"https://www.dice.com/jobs?q={query.replace(' ', '+')}"
            
            jobs = [
                {
                    "source": "Dice Jobs",
                    "title": f"{query}",
                    "company": "Tech Companies",
                    "url": search_url,
                    "location": "United States",
                    "type": "Tech Job Board"
                }
            ]
            return jobs
        except Exception as e:
            return [{"error": f"Dice Jobs search failed: {str(e)}"}]


class JobAnalyzerInput(BaseModel):
    """Input schema for JobAnalyzerTool."""
    job_data: str = Field(..., description="JSON string containing job listings to analyze")


class JobAnalyzerTool(BaseTool):
    name: str = "Job Analyzer Tool"
    description: str = (
        "Analyze job listings for AI/ML positions. Extracts key information like "
        "required skills, experience level, and job type."
    )
    args_schema: Type[BaseModel] = JobAnalyzerInput

    def _run(self, job_data: str) -> str:
        """
        Analyze job listings and extract key information
        """
        try:
            jobs = json.loads(job_data)
            if not isinstance(jobs, list):
                jobs = [jobs]
            
            analyzed_jobs = []
            
            for job in jobs:
                if "error" not in job:
                    analyzed_job = {
                        "title": job.get("title", ""),
                        "company": job.get("company", ""),
                        "source": job.get("source", ""),
                        "url": job.get("url", ""),
                        "location": job.get("location", "Not specified"),
                        "required_skills": self._extract_skills(job.get("title", "")),
                        "experience_level": self._determine_experience_level(job.get("title", "")),
                        "job_type": "Remote" if "remote" in job.get("title", "").lower() else "On-site"
                    }
                    analyzed_jobs.append(analyzed_job)
            
            return json.dumps(analyzed_jobs, indent=2)
        except Exception as e:
            return f"Error analyzing jobs: {str(e)}"
    
    def _extract_skills(self, job_title: str) -> list:
        """Extract likely required skills based on job title"""
        ai_ml_skills = {
            "python": "Python",
            "machine learning": "Machine Learning",
            "deep learning": "Deep Learning",
            "tensorflow": "TensorFlow",
            "pytorch": "PyTorch",
            "data science": "Data Science",
            "nlp": "NLP",
            "computer vision": "Computer Vision",
            "llm": "Large Language Models",
            "ai": "Artificial Intelligence",
            "ml": "Machine Learning",
            "neural network": "Neural Networks",
            "scikit-learn": "Scikit-learn"
        }
        
        job_title_lower = job_title.lower()
        found_skills = [skill for key, skill in ai_ml_skills.items() 
                       if key in job_title_lower]
        
        return found_skills if found_skills else ["Python", "ML/AI Frameworks", "Data Analysis"]
    
    def _determine_experience_level(self, job_title: str) -> str:
        """Determine experience level from job title"""
        title_lower = job_title.lower()
        if "senior" in title_lower or "lead" in title_lower or "staff" in title_lower:
            return "Senior (5+ years)"
        elif "junior" in title_lower or "entry" in title_lower or "graduate" in title_lower:
            return "Junior/Entry Level (0-2 years)"
        else:
            return "Mid-Level (2-5 years)"
