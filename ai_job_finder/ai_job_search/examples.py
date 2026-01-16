#!/usr/bin/env python
"""
Example script demonstrating direct usage of Job Search Tools
"""

import json
from ai_job_search.tools.custom_tool import JobSearchTool, JobAnalyzerTool


def example_direct_tool_usage():
    """Example of using tools directly without the crew"""
    
    print("=" * 80)
    print("AI/ML JOB SEARCH TOOL - DIRECT USAGE EXAMPLE")
    print("=" * 80)
    
    # Initialize tools
    search_tool = JobSearchTool()
    analyzer_tool = JobAnalyzerTool()
    
    # Example 1: Search for Machine Learning Engineer jobs
    print("\n1. Searching for Machine Learning Engineer positions...")
    print("-" * 80)
    
    search_result = search_tool._run(
        job_query="Machine Learning Engineer",
        job_board="all"
    )
    
    jobs = json.loads(search_result)
    print(f"Found {len(jobs)} job opportunities:")
    for i, job in enumerate(jobs, 1):
        print(f"\n{i}. {job.get('title')}")
        print(f"   Company: {job.get('company')}")
        print(f"   Source: {job.get('source')}")
        print(f"   Location: {job.get('location')}")
        print(f"   URL: {job.get('url')}")
    
    # Example 2: Analyze the job listings
    print("\n" + "=" * 80)
    print("2. Analyzing job listings...")
    print("-" * 80)
    
    analysis_result = analyzer_tool._run(job_data=search_result)
    analyzed_jobs = json.loads(analysis_result)
    
    for job in analyzed_jobs:
        print(f"\nJob: {job.get('title')}")
        print(f"Company: {job.get('company')}")
        print(f"Required Skills: {', '.join(job.get('required_skills', []))}")
        print(f"Experience Level: {job.get('experience_level')}")
        print(f"Job Type: {job.get('job_type')}")
    
    # Example 3: Search for specific boards
    print("\n" + "=" * 80)
    print("3. Searching LinkedIn specifically...")
    print("-" * 80)
    
    linkedin_result = search_tool._run(
        job_query="Data Scientist",
        job_board="linkedin"
    )
    
    linkedin_jobs = json.loads(linkedin_result)
    print(f"Found {len(linkedin_jobs)} LinkedIn job(s):")
    for job in linkedin_jobs:
        print(f"- {job.get('title')} at {job.get('company')}")
        print(f"  {job.get('url')}")
    
    # Example 4: Search Dice specifically
    print("\n" + "=" * 80)
    print("4. Searching Dice specifically...")
    print("-" * 80)
    
    dice_result = search_tool._run(
        job_query="AI Engineer",
        job_board="dice"
    )
    
    dice_jobs = json.loads(dice_result)
    print(f"Found {len(dice_jobs)} Dice job(s):")
    for job in dice_jobs:
        print(f"- {job.get('title')} at {job.get('company')}")
        print(f"  {job.get('url')}")
    
    # Example 5: Multiple searches and combined analysis
    print("\n" + "=" * 80)
    print("5. Combined search and analysis...")
    print("-" * 80)
    
    queries = [
        "Machine Learning Engineer",
        "Deep Learning Engineer",
        "NLP Engineer"
    ]
    
    all_jobs = []
    for query in queries:
        print(f"\nSearching for: {query}")
        result = search_tool._run(job_query=query, job_board="all")
        jobs_list = json.loads(result)
        all_jobs.extend(jobs_list)
        print(f"  Found {len(jobs_list)} positions")
    
    # Analyze all combined jobs
    print(f"\nAnalyzing {len(all_jobs)} total positions...")
    combined_analysis = analyzer_tool._run(job_data=json.dumps(all_jobs))
    
    # Extract skills distribution
    analyzed = json.loads(combined_analysis)
    all_skills = {}
    
    for job in analyzed:
        for skill in job.get('required_skills', []):
            all_skills[skill] = all_skills.get(skill, 0) + 1
    
    print("\nMost In-Demand Skills:")
    for skill, count in sorted(all_skills.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {skill}: {count} positions")
    
    # Experience distribution
    experience_levels = {}
    for job in analyzed:
        level = job.get('experience_level', 'Unknown')
        experience_levels[level] = experience_levels.get(level, 0) + 1
    
    print("\nExperience Level Distribution:")
    for level, count in sorted(experience_levels.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {level}: {count} positions")
    
    print("\n" + "=" * 80)
    print("Job Search and Analysis Complete!")
    print("=" * 80)


if __name__ == "__main__":
    example_direct_tool_usage()
