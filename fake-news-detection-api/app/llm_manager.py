from openai import OpenAI
from typing import List, Dict
import logging
import os

# configure a logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # or INFO in production
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)

class LLMManager:
    def __init__(self):
        key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=key)

        self.extract_model  = os.getenv("LLM_EXTRACT_MODEL",  "gpt-4o")
        self.classify_model = os.getenv("LLM_CLASSIFY_MODEL", "gpt-4o")

        logger.info("LLMManager initialized with OpenAI client")

    def set_model(self, model: str):
        logger.info(f"Switching LLMManager models → {model}")
        self.extract_model   = model
        self.classify_model  = model

    def extract_google_search_query(self, text: str) -> str:
        logger.debug("Extracting search query for text: %r", text)
        resp = self.client.chat.completions.create(
            model = self.extract_model,
            messages = [
                {"role": "system", "content": "You are a tweet-to-search-query converter."},
                {"role": "user", "content": (
                    "Identify the key entities (people, organizations, tokens), "
                    "capture any numeric facts or claims, "
                    "omit filler, opinion, hashtags, and punctuation. "
                    "Combine the essentials into a single space-separated Google News query. "
                    f"Only return the final search query string, no explanations: \"{text}\""
                )}
            ],
            max_tokens = 20,
            temperature = 0.3

        )
        query = resp.choices[0].message.content.strip()
        logger.debug("Extracted search query: %r", query)
        return query

    def extract_search_terms(self, text: str) -> str:
        logger.debug("Extracting search terms for text: %r", text)
        resp = self.client.chat.completions.create(
            model=self.extract_model,
            messages=[
                {"role": "system", "content": "You are an AI that converts text into concise search terms."},
                {"role": "user", "content": (
                    f"Extract the three most important words from this text. "
                    f"Only return those words, separated by spaces, no punctuation: \"{text}\""
                )}
            ],
            max_tokens=20,
            temperature=0.3
        )
        terms = resp.choices[0].message.content.strip()
        logger.debug("Extracted search terms: %r", terms)
        return terms

    def build_messages(
        self,
        post: str,
        articles_block: str,
        use_external: bool,
        prompt_variant: str,
        output_type: str
    ) -> List[Dict[str, str]]:
        """
        Constructs the system and user messages for the classification prompt,
        based on whether external articles are used, prompt length, and output type.
        """
        system_content = ""
        user_content = ""

        if not use_external:
            # No external data
            system_content = "You are a fact-checking assistant."
            if prompt_variant == "short":
                if output_type == "binary":
                    user_content = (
                        f"Claim: \"{post}\"\n"
                        "Is this statement true or false?\n"
                        "Respond with only \"True\" or \"False.\""
                    )
                elif output_type == "score":
                    user_content = (
                        f"Claim: \"{post}\"\n"
                        "On a scale from 0 (definitely false) to 1 (definitely true), how truthful is this?\n"
                        "Respond with only a number between 0 and 1."
                    )
                else:  # detailed
                    user_content = (
                        f"Claim: \"{post}\"\n"
                        "Provide:\n"
                        "1. A verdict (\"True\" or \"False\")\n"
                        "2. A brief explanation (2–3 sentences)."
                    )
            else:
                # Default (long) prompts without external data
                if output_type == "binary":
                    system_content = (
                        "You are a fact‑checking assistant. Evaluate the veracity of the following claim "
                        "using your internal knowledge and publicly available data."
                    )
                    user_content = (
                        f"Claim: \"{post}\"\n\n"
                        "Task: Decide if the claim is true or false.\n\n"
                        "Output format (exact):\n"
                        "{\n  \"verdict\": \"True\" | \"False\"\n}\n"
                        "Do not include any other fields."
                    )
                elif output_type == "score":
                    system_content = "You are a fact‑checking assistant. Assess the credibility of the following claim."
                    user_content = (
                        f"Claim: \"{post}\"\n\n"
                        "Task: Assign a confidence score between 0 (definitely false) and 1 (definitely true).\n\n"
                        "Output format (exact):\n"
                        "{\n  \"score\": 0.00-1.00\n}\n"
                        "Do not include any other fields or text."
                    )
                else:  # detailed
                    system_content = (
                        "You are a fact‑checking assistant. Analyze the following claim, determine its truthfulness, "
                        "and explain your reasoning."
                    )
                    user_content = (
                        f"Claim: \"{post}\"\n\n"
                        "Task: Provide a JSON with:\n"
                        "1. verdict: \"True\" or \"False\",\n"
                        "2. score: confidence (0.00–1.00),\n"
                        "3. explanation: a short paragraph citing reliable knowledge.\n\n"
                        "Output format (exact):\n"
                        "{\n"
                        "  \"verdict\": \"True\" | \"False\",\n"
                        "  \"score\": 0.00-1.00,\n"
                        "  \"explanation\": \"…\"\n"
                        "}"
                    )
        else:
            # With external articles
            system_content = "You are a fact‑checking assistant."
            if prompt_variant == "short":
                if output_type == "binary":
                    user_content = (
                        f"Based on the following articles, answer ONLY with 'True' if the post is mostly correct, "
                        "or 'False' if it is mostly incorrect.\n\n"
                        f"Post: \"{post}\"\n\n"
                        f"Articles:\n{articles_block}"
                    )
                elif output_type == "score":
                    user_content = (
                        f"Article:\n{articles_block}\n"
                        f"Claim: \"{post}\"\n"
                        "Based on the article, rate the truthfulness from 0.00 (definitely false) to 1.00 (definitely true).\n"
                        "Respond with only a number between 0.00 and 1.00"
                    )
                else:  # detailed
                    user_content = (
                        f"Article:\n{articles_block}\n"
                        f"Claim: \"{post}\"\n"
                        "Provide:\n"
                        "1. Verdict (\"True\" or \"False\")\n"
                        "2. A concise explanation citing the article."
                    )
            else:
                # Default (long) prompts with external data
                if output_type == "binary":
                    system_content = (
                        "You are a fact‑checking assistant. Use only the provided article to judge the claim’s accuracy."
                    )
                    user_content = (
                        f"Article:\n{articles_block}\n\n"
                        f"Claim: \"{post}\"\n\n"
                        "Task: Decide if the claim is true or false based solely on the article.\n\n"
                        "Output format (exact):\n"
                        "{\n  \"verdict\": \"True\" | \"False\"\n}\n"
                        "No additional commentary."
                    )
                elif output_type == "score":
                    system_content = (
                        "You are a fact‑checking assistant. Based solely on the article below, rate how likely the claim is true."
                    )
                    user_content = (
                        f"Article:\n{articles_block}\n\n"
                        f"Claim: \"{post}\"\n\n"
                        "Task: Provide a confidence score between 0.00 (definitely false) and 1.00 (definitely true).\n\n"
                        "Output format (exact):\n"
                        "{\n  \"score\": 0.00-1.00\n}\n"
                        "No extra text."
                    )
                else:  # detailed
                    system_content = (
                        "You are a fact‑checking assistant. Read the article and then evaluate the claim. Your answer must be based only on the article’s content."
                    )
                    user_content = (
                        f"Article:\n{articles_block}\n\n"
                        f"Claim: \"{post}\"\n\n"
                        "Task: Return a JSON with:\n"
                        "- score: (0.00-1.00) where 0.00 is definitely false and 1.00 is definitely true\n"
                        "- explanation: 2–3 sentences citing specific lines or data from the article.\n\n"
                        "Output format (exact):\n"
                        "{\n"
                        "  \"score\": 0.00-1.00,\n"
                        "  \"explanation\": \"…\"\n"
                        "}"
                    )

        messages: List[Dict[str, str]] = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        messages.append({"role": "user", "content": user_content})

        return messages

    def classify_once(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500
    ) -> str:
        """
        Sends a single classification call to GPT-4o with the given messages.
        """

        resp = self.client.chat.completions.create(
            model=self.classify_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3
        )
        content = resp.choices[0].message.content.strip()

        logger.info("LLM response: %s", content)
        return content
