from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from ai_job_search.tools.custom_tool import JobSearchTool, JobAnalyzerTool

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

@CrewBase
class AiJobSearch():
    """AiJobSearch crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def job_searcher(self) -> Agent:
        return Agent(
            config=self.agents_config['job_searcher'],
            tools=[JobSearchTool()],
            verbose=True
        )

    @agent
    def job_analyzer(self) -> Agent:
        return Agent(
            config=self.agents_config['job_analyzer'],
            tools=[JobAnalyzerTool()],
            verbose=True
        )

    @agent
    def report_curator(self) -> Agent:
        return Agent(
            config=self.agents_config['report_curator'],
            verbose=True
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def search_ai_jobs(self) -> Task:
        return Task(
            config=self.tasks_config['search_ai_jobs'],
        )

    @task
    def analyze_job_requirements(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_job_requirements'],
        )

    @task
    def generate_market_report(self) -> Task:
        return Task(
            config=self.tasks_config['generate_market_report'],
            output_file='ai_ml_jobs_report.md'
        )

    @crew
    def crew(self) -> Crew:
        """Creates the AiJobSearch crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
