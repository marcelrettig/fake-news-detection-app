from app.llm_manager import LLMManager
from app.serp_agent import SerpAgent
import os

class ClassificationService:
    def __init__(self, llm: LLMManager, serp: SerpAgent):
        self.llm = llm
        self.serp = serp
        self.apply_env_models()


    def apply_env_models(self) -> None:
        # Read the four model names from .env (with sensible fallbacks)
        self.llm.extract_model  = os.getenv("LLM_EXTRACT_MODEL",  "gpt-4o")
        self.llm.classify_model = os.getenv("LLM_CLASSIFY_MODEL", "gpt-4o")
        # If your LLMManager has setters, feel free to call them here instead:
        # self.llm.set_models(extract=self.llm.extract_model, classify=self.llm.classify_model)

        # Keep Serp/Crew models in sync, used only when use_external_info=True
        self.serp.research_model = os.getenv("LLM_RESEARCH_MODEL", "gpt-4o")
        self.serp.summary_model  = os.getenv("LLM_SUMMARY_MODEL",  "gpt-4o")

    def extract_query(self, text: str) -> str:
        if not text.strip():
            raise ValueError("Post must not be empty")
        return self.llm.extract_google_search_query(text)

    def fetch_articles(self, query: str, text: str, use_external: bool) -> str:
        if not use_external:
            return ""
        return self.serp.search_news(query, text)

    def build_messages(
        self,
        text: str,
        articles: str,
        use_external: bool,
        variant: str,
        output: str
    ) -> list[str]:
        return self.llm.build_messages(
            post=text,
            articles_block=articles,
            use_external=use_external,
            prompt_variant=variant,
            output_type=output,
        )

    def classify(self, messages: list[str], iterations: int) -> list[str]:
        responses: list[str] = []
        for _ in range(iterations):
            responses.append(self.llm.classify_once(messages))
        return responses
