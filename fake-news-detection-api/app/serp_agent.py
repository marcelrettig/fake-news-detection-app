import os
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool
from langchain_openai import ChatOpenAI

serp_key = os.getenv("SERP_API_KEY")
print(serp_key)
if not serp_key:
    raise RuntimeError("Missing SERPER_API_KEY environment variable")

# Initialize the search tool with the SERP API key
search_tool = SerperDevTool(api_key=serp_key)

class SerpAgent:
    def __init__(self):
        openai_key = os.getenv("OPENAI_API_KEY")
        os.environ['SERPER_API_KEY'] = serp_key
        self.research_model = os.getenv("LLM_RESEARCH_MODEL", "gpt-4o")
        self.summary_model  = os.getenv("LLM_SUMMARY_MODEL",  "gpt-4o")
        self.research_llm = ChatOpenAI(
            model_name=self.research_model,
            temperature=0.3,
            api_key=openai_key
        )
        self.writer_llm = ChatOpenAI(
            model_name=self.summary_model,
            temperature=0.5,
            api_key=openai_key
        )

    def search_news(self, query: str, post: str,) -> str:
        # Researcher agent
        researcher = Agent(
            role="Google News Research Agent",
            goal="Use the search tool to look for current, relevant and trustworthy news articles based on a given query.",
            backstory="""You are a digital research assistant specializing in real-time news sourcing.
            You have access to Google News and your expertise lies in identifying credible, up-to-date news content from trusted sources.
            Your task is to research news articles based on the provided query and return a list of the most relevant articles, including the title, source, date (if available), and URL.""",
            verbose=False,
            allow_delegation=False,
            tools=[search_tool],
            llm=self.research_llm
        )

        # Writer agent
        writer = Agent(
            role="News Summary Writer",
            goal="Summarize key factual information from the provided news articles, including source links.",
            backstory="""You are an expert writer who specializes in summarizing complex news stories into clear and informative articles.
            You transform raw news data into well-structured summaries that capture the most important points. You always include links to the original articles to ensure transparency and source validation.""",
            verbose=True,
            allow_delegation=False,
            llm=self.writer_llm
        )

        # Research task
        research_task = Task(
            description=f"""Please use the search tool to search for recent and trustworthy news articles related to the following query: "{query}".
            Return a list of 5–10 articles, including:
            - Article title
            - Source name
            - Date of publication (if available)
            - Direct link to the article

            Only include results from reputable news outlets (e.g., The New York Times, BBC, Reuters, ScienceDaily, etc.).""",
            expected_output="A bulleted list of 5–10 reputable news articles with title, source, date, and URL.",
            agent=researcher
        )

        # Summary task
        summary_task = Task(
            description=f"""Summarize the key facts from the researcher's article findings.
            They goal is to find information that either confirms or refutes the following claim: "{post}". 
            Your task is not to judge whether the claim is true or not but to extract the structured facts from the articles that will help to classify the claim later on.""",
            expected_output="A well-structured article summary followed by the full list of URLs.",
            agent=writer,
        )

        # Crew
        crew = Crew(
            agents=[researcher, writer],
            tasks=[research_task, summary_task],
            process=Process.sequential
        )

        result = crew.kickoff()
        return str(result)