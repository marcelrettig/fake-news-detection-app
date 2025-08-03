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
                    "Only return the final search query string, no explanations: "
                    f"\"{text}\""
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
        # 1) Log inputs once
        logger.debug(
            "build_messages called → use_external=%s, prompt_variant=%r, output_type=%r",
            use_external, prompt_variant, output_type
        )

        # Ensure we have a default variant
        variant = prompt_variant or "long"

        # 2) Handle NO external data
        if not use_external:
            # SHORT variant
            if variant == "short":
                if output_type == "binary":
                    system_content = (
                        "You are a fact-checking assistant.\n"
                        "Given a claim, decide if it is true or false, using both the claim and your internal knowledge.\n"
                        "Reply ONLY in this JSON format:\n"
                        "{\n"
                        "  \"verdict\": \"True\"|\"False\"\n"
                        "}\n"
                    )
                    user_content = (
                        "Claim:\n"
                        f"\"{post}\"\n\n"
                        "Is the claim true or false, using both the claim and your own knowledge?\n"
                        "Reply ONLY in this JSON format:\n"
                        "{\n"
                        "  \"verdict\": \"True\"|\"False\"\n"
                        "}\n"
                    )
                    messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user",   "content": user_content}
                    ]
                    logger.debug("FINAL messages (no_external, short, binary): %r", messages)
                    return messages

                elif output_type == "score":
                    system_content = (
                        "You are a fact-checking assistant.\n"
                        "Given a claim, rate how true it is from 0 (false) to 1 (true), using both the claim and your internal knowledge.\n"
                        "Reply ONLY in this JSON format:\n"
                        "{\n"
                        "  \"score\": <float 0-1>\n"
                        "}\n"
                    )
                    user_content = (
                        "Claim:\n"
                        f"\"{post}\"\n\n"
                        "How well does your knowledge support the claim? "
                        "Rate from 0 (false) to 1 (true), and reply ONLY in this JSON format:\n"
                        "{\n"
                        "  \"score\": <float 0-1>\n"
                        "}\n"
                    )
                    messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user",   "content": user_content}
                    ]
                    logger.debug("FINAL messages (no_external, short, score): %r", messages)
                    return messages

                elif output_type == "binary_expl":
                    system_content = (
                        "You are a fact-checking assistant.\n"
                        "Given a claim, decide if it is true or false, using both the claim and your internal knowledge.\n"
                        "Explain your reasoning, then respond ONLY in this format:\n"
                        "{\n"
                        "  \"verdict\": \"True\"|\"False\",\n"
                        "  \"explanation\": \"…\"\n"
                        "}\n"
                    )
                    user_content = (
                        "Claim:\n"
                        f"\"{post}\"\n\n"
                        "Decide if the claim is true or false using both the information in the claim and your own knowledge.\n"
                        "Reply ONLY in this JSON format:\n"
                        "{\n"
                        "  \"verdict\": \"True\"|\"False\",\n"
                        "  \"explanation\": \"…\"\n"
                        "}\n"
                    )
                    messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user",   "content": user_content}
                    ]
                    logger.debug("FINAL messages (no_external, short, binary_expl): %r", messages)
                    return messages

                elif output_type == "score_expl":
                    system_content = (
                        "You are a fact-checking assistant.\n"
                        "Given a claim, rate how true it is from 0 (false) to 1 (true), using both the claim and your internal knowledge.\n"
                        "Explain your reasoning, then reply ONLY with this JSON:\n"
                        "{\n"
                        "  \"score\": <float 0-1>,\n"
                        "  \"explanation\": \"…\"\n"
                        "}\n"
                    )
                    user_content = (
                        "Claim:\n"
                        f"\"{post}\"\n\n"
                        "Rate, from 0 (completely false) to 1 (completely true), how well your knowledge supports the claim.\n"
                        "Reply ONLY in this JSON format:\n"
                        "{\n"
                        "  \"score\": <float 0-1>,\n"
                        "  \"explanation\": \"…\"\n"
                        "}\n"
                    )
                    messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user",   "content": user_content}
                    ]
                    logger.debug("FINAL messages (no_external, short, score_expl): %r", messages)
                    return messages

            # LONG variant (default) without external
            if output_type == "binary":
                system_content = (
                    "You are an expert fact-checking assistant.\n"
                    "Your task is to analyze a given claim, using both the information in the claim and your own internal knowledge and data.\n"
                    "Apply logical reasoning and your knowledge base to determine whether the claim is true or false.\n"
                    "Do not include any explanation; only output the binary verdict as an exact JSON in the format below.\n\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"verdict\": \"True\"|\"False\"\n"
                    "}\n"
                )
                user_content = (
                    "Claim:\n"
                    f"\"{post}\"\n\n"
                    "Analyze the claim using both its contents and your internal knowledge and data.\n"
                    "Decide if it is true or false and reply ONLY in the following exact JSON format (without any explanation):\n\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"verdict\": \"True\"|\"False\"\n"
                    "}\n"
                )
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user",   "content": user_content}
                ]
                logger.debug("FINAL messages (no_external, long, binary): %r", messages)
                return messages

            if output_type == "score":
                system_content = (
                    "You are an expert fact-checking assistant.\n"
                    "Your task is to analyze a given claim, using both the information in the claim and your internal knowledge and data.\n"
                    "Based on logical reasoning and your knowledge, provide a score from 0 (completely false) to 1 (completely true) for how well the claim aligns with reality.\n"
                    "Do not include any explanation; only output the score as an exact JSON in the format below.\n\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"score\": <float between 0 and 1>\n"
                    "}\n"
                )
                user_content = (
                    "Claim:\n"
                    f"\"{post}\"\n\n"
                    "Analyze the claim using both its contents and your internal knowledge and data.\n"
                    "Rate, from 0 (completely false) to 1 (completely true), how well your knowledge supports the claim, and reply ONLY in the following exact JSON format (without any explanation):\n\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"score\": <float between 0 and 1>\n"
                    "}\n"
                )
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user",   "content": user_content}
                ]
                logger.debug("FINAL messages (no_external, long, score): %r", messages)
                return messages

            if output_type == "binary_expl":
                system_content = (
                    "You are an expert fact-checking assistant.\n"
                    "Your job is to analyze a given claim, using both the content of the claim and your own internal knowledge and data.\n"
                    "Using logical reasoning, you must:\n"
                    "\n"
                    "- Carefully read and interpret the claim.\n"
                    "- Assess the plausibility and accuracy of the claim based on what is stated and what you already know.\n"
                    "- Break down your reasoning step by step, drawing on both the claim and your internal knowledge of facts, concepts, and commonly available data.\n"
                    "- Do not fabricate evidence, but use your knowledge base to supplement and check the claim's validity.\n"
                    "- After your reasoning, output your decision as an exact JSON with:\n"
                    "  - A binary verdict: \"True\" if the claim is accurate and plausible given your knowledge, \"False\" if not.\n"
                    "  - A clear, concise explanation of your reasoning and how you arrived at your verdict.\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"verdict\": \"True\"|\"False\",\n"
                    "  \"explanation\": \"…\"\n"
                    "}\n"
                )
                user_content = (
                    "Claim:\n"
                    f"\"{post}\"\n\n"
                    "Analyze the claim using both the information explicitly given and your own internal knowledge and data.\n"
                    "\n"
                    "- Think through each step logically:\n"
                    "  - Identify the main assertion(s) in the claim.\n"
                    "  - Evaluate whether the claim is accurate, plausible, and consistent, using both the content of the claim and your knowledge base.\n"
                    "  - Clearly state what knowledge or data you are relying on, in addition to what is in the claim itself.\n"
                    "  - Conclude if the claim is correct (True) or incorrect (False).\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"verdict\": \"True\"|\"False\",\n"
                    "  \"explanation\": \"…\"\n"
                    "}\n"
                )
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user",   "content": user_content}
                ]
                logger.debug("FINAL messages (no_external, long, binary_expl): %r", messages)
                return messages

            if output_type == "score_expl":
                system_content = (
                    "You are an expert fact-checking assistant.\n"
                    "Your job is to analyze a given claim, using both the content of the claim and your own internal knowledge and data.\n"
                    "Using logical reasoning, you must:\n"
                    "\n"
                    "- Carefully read and interpret the claim.\n"
                    "- Assess the plausibility and accuracy of the claim based on what is stated and what you already know.\n"
                    "- Break down your reasoning step by step, drawing on both the claim and your internal knowledge of facts, concepts, and commonly available data.\n"
                    "- Do not fabricate evidence, but use your knowledge base to supplement and check the claim's validity.\n"
                    "- After your reasoning, output your decision as an exact JSON with:\n"
                    "  - A score from 0 (completely false) to 1 (completely true), reflecting how well the claim aligns with your knowledge and the information provided.\n"
                    "  - A clear, concise explanation of your reasoning and how you arrived at your score.\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"score\": <float between 0 and 1>,\n"
                    "  \"explanation\": \"…\"\n"
                    "}\n"
                )
                user_content = (
                    "Claim:\n"
                    f"\"{post}\"\n\n"
                    "Analyze the claim using both the information explicitly given and your own internal knowledge and data.\n"
                    "\n"
                    "- Think through each step logically:\n"
                    "  - Identify the main assertion(s) in the claim.\n"
                    "  - Evaluate whether the claim is accurate, plausible, and consistent, using both the content of the claim and your knowledge base.\n"
                    "  - Clearly state what knowledge or data you are relying on, in addition to what is in the claim itself.\n"
                    "  - Decide, on a scale from 0 (completely false) to 1 (completely true), how well your knowledge supports the claim.\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"score\": <float between 0 and 1>,\n"
                    "  \"explanation\": \"…\"\n"
                    "}\n"
                )
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user",   "content": user_content}
                ]
                logger.debug("FINAL messages (no_external, long, score_expl): %r", messages)
                return messages

        # 3) Handle WITH external data
        if use_external:
            # SHORT variant
            if variant == "short":
                if output_type == "binary":
                    system_content = (
                        "You are a fact-checking assistant.\n"
                        "Given a claim and articles from trusted sources, decide if the claim is true or false.\n"
                        "Use only information from the articles.\n"
                        "Respond ONLY with this JSON:\n"
                        "{\n"
                        "  \"verdict\": \"True\"|\"False\"\n"
                        "}\n"
                    )
                    user_content = (
                        "Claim:\n"
                        f"\"{post}\"\n\n"
                        "Articles from trusted sources:\n"
                        f"{articles_block}\n\n"
                        "Decide if the claim is true or false, using only these articles.\n"
                        "Reply ONLY in this JSON format:\n"
                        "{\n"
                        "  \"verdict\": \"True\"|\"False\"\n"
                        "}\n"
                    )
                    messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user",   "content": user_content}
                    ]
                    logger.debug("FINAL messages (external, short, binary): %r", messages)
                    return messages

                elif output_type == "score":
                    system_content = (
                        "You are a fact-checking assistant.\n"
                        "Given a claim and articles from trusted sources, rate support for the claim.\n"
                        "Use only information from the articles.\n"
                        "Respond ONLY with this JSON:\n"
                        "{\n"
                        "  \"score\": <float 0-1>\n"
                        "}\n"
                    )
                    user_content = (
                        "Claim:\n"
                        f"\"{post}\"\n\n"
                        "Articles from trusted sources:\n"
                        f"{articles_block}\n\n"
                        "Rate, from 0 (completely false) to 1 (completely true), how well the articles support the claim.\n"
                        "Reply ONLY in this JSON format:\n"
                        "{\n"
                        "  \"score\": <float 0-1>\n"
                        "}\n"
                    )
                    messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user",   "content": user_content}
                    ]
                    logger.debug("FINAL messages (external, short, score): %r", messages)
                    return messages

                elif output_type == "binary_expl":
                    system_content = (
                        "You are a fact-checking assistant.\n"
                        "Given a claim and articles from trusted sources, decide if the claim is true or false.\n"
                        "Use only information from the articles.\n"
                        "Explain your reasoning step-by-step.\n"
                        "Respond ONLY with this JSON:\n"
                        "{\n"
                        "  \"verdict\": \"True\"|\"False\",\n"
                        "  \"explanation\": \"…\"\n"
                        "}\n"
                    )
                    user_content = (
                        "Claim:\n"
                        f"\"{post}\"\n\n"
                        "Articles from trusted sources:\n"
                        f"{articles_block}\n\n"
                        "Decide if the claim is true or false, using only these articles.\n"
                        "Reason step by step, then reply ONLY in this JSON format:\n"
                        "{\n"
                        "  \"verdict\": \"True\"|\"False\",\n"
                        "  \"explanation\": \"…\"\n"
                        "}\n"
                    )
                    messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user",   "content": user_content}
                    ]
                    logger.debug("FINAL messages (external, short, binary_expl): %r", messages)
                    return messages

                elif output_type == "score_expl":
                    system_content = (
                        "You are a fact-checking assistant.\n"
                        "Given a claim and articles from trusted sources, rate support for the claim.\n"
                        "Use only information from the articles.\n"
                        "Explain your reasoning step-by-step.\n"
                        "Respond ONLY with this JSON:\n"
                        "{\n"
                        "  \"score\": <float 0-1>,\n"
                        "  \"explanation\": \"…\"\n"
                        "}\n"
                    )
                    user_content = (
                        "Claim:\n"
                        f"\"{post}\"\n\n"
                        "Articles from trusted sources:\n"
                        f"{articles_block}\n\n"
                        "Rate, from 0 (completely false) to 1 (completely true), how well the articles support the claim.\n"
                        "Reason step by step, then reply ONLY in this JSON format:\n"
                        "{\n"
                        "  \"score\": <float 0-1>,\n"
                        "  \"explanation\": \"…\"\n"
                        "}\n"
                    )
                    messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user",   "content": user_content}
                    ]
                    logger.debug("FINAL messages (external, short, score_expl): %r", messages)
                    return messages

            # LONG variant with external data
            if output_type == "binary":
                system_content = (
                    "You are an expert fact-checking assistant. Your job is to analyze a given claim and a set of articles from trusted news sources about the claim. Using logical reasoning, you must:\n"
                    "\n"
                    "- Carefully read and compare the claim to the information in the articles.\n"
                    "- Base your decision strictly on the information present in the articles.\n"
                    "- Break down your reasoning step by step, noting if the articles confirm, contradict, or ignore the claim.\n"
                    "- Avoid any speculation or information not present in the provided sources.\n"
                    "- After reasoning, output an exact JSON with:\n"
                    "  - A binary verdict: \"True\" if the claim is verified by the articles, \"False\" if not.\n"
                    "\n"
                    "Your response should strictly follow this format:\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"verdict\": \"True\"|\"False\"\n"
                    "}\n"
                )
                user_content = (
                   "Claim:\n"
                        f"\"{post}\"\n\n"
                        "\n"
                        "Related articles from trusted sources:\n"
                        f"\n{articles_block}\n\n"
                        "\n"
                        "Analyze the claim using only the information in the provided articles.\n"
                        "\n"
                        "- Think through each step logically:\n"
                        "  - Identify the main factual assertion of the claim.\n"
                        "  - Check if the articles support, contradict, or provide no relevant info for the claim.\n"
                        "  - Assess the credibility and consistency of evidence across sources.\n"
                        "  - Conclude whether the claim is verified (True) or refuted (False).\n"
                        "\n"
                        "At the end, output your answer in the following exact JSON format ONLY (without any explanation):\n"
                        "\n"
                        "Output (exact JSON):\n"
                        "{\n"
                        "  \"verdict\": \"True\"|\"False\"\n"
                        "}\n"
                        "\n"
                        "Do NOT include any information outside this JSON.\n"
                )
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user",   "content": user_content}
                ]
                logger.debug("FINAL messages (external, long, binary): %r", messages)
                return messages

            if output_type == "score":
                system_content = (
                    "You are an expert fact-checking assistant. Your job is to analyze a claim and a set of articles from trusted news sources about the claim. Using logical reasoning, you must:\n"
                    "\n"
                    "- Carefully read and compare the claim to the information in the articles.\n"
                    "- Base your decision strictly on the information present in the articles.\n"
                    "- Break down your reasoning step by step, noting if the articles confirm, contradict, or ignore the claim.\n"
                    "- Avoid any speculation or information not present in the provided sources.\n"
                    "- After reasoning, output an exact JSON with:\n"
                    "  - A score from 0 (completely false) to 1 (completely true), reflecting how well the claim is supported by the articles.\n"
                    "\n"
                    "Your response should strictly follow this format:\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"score\": <float between 0 and 1>\n"
                    "}\n"
                )
                user_content = (
                    "Claim:\n"
                    f"\"{post}\"\n\n"
                    "Related articles from trusted sources:\n"
                    f"{articles_block}\n\n"
                    "Analyze the claim using only the information in the provided articles.\n"
                    "\n"
                    "- Think through each step logically:\n"
                    "  - Identify the main factual assertion of the claim.\n"
                    "  - Check if the articles support, contradict, or provide no relevant info for the claim.\n"
                    "  - Assess the credibility and consistency of evidence across sources.\n"
                    "  - Decide, on a scale from 0 (completely false) to 1 (completely true), how well these sources support the claim.\n"
                    "\n"
                    "At the end, output your answer in the following exact JSON format ONLY (without any explanation):\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"score\": <float between 0 and 1>\n"
                    "}\n"
                    "\n"
                    "Do NOT include any information outside this JSON.\n"
                )
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user",   "content": user_content}
                ]
                logger.debug("FINAL messages (external, long, score): %r", messages)
                return messages

            if output_type == "binary_expl":
                system_content = (
                    "You are an expert fact-checking assistant. Your job is to analyze a given claim and a set of articles from trusted news sources about the claim. Using logical reasoning, you must:\n"
                    "\n"
                    "- Carefully read and compare the claim to the information in the articles.\n"
                    "- Base your decision strictly on the information present in the articles.\n"
                    "- Break down your reasoning step by step, noting if the articles confirm, contradict, or ignore the claim.\n"
                    "- Avoid any speculation or information not present in the provided sources.\n"
                    "- After reasoning, output an exact JSON with:\n"
                    "  - A binary verdict: \"True\" if the claim is verified by the articles, \"False\" if not.\n"
                    "  - A clear, concise explanation of your reasoning and the evidence used.\n"
                    "\n"
                    "Your response should strictly follow this format:\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"verdict\": \"True\"|\"False\",\n"
                    "  \"explanation\": \"…\"\n"
                    "}\n"
                )
                user_content = (
                    "Claim:\n"
                    f"\"{post}\"\n\n"
                    "Related articles from trusted sources:\n"
                    f"{articles_block}\n\n"
                    "Analyze the claim using only the information in the provided articles.\n"
                    "\n"
                    "- Think through each step logically:\n"
                    "  - Identify the main factual assertion of the claim.\n"
                    "  - Check if the articles support, contradict, or provide no relevant info for the claim.\n"
                    "  - Assess the credibility and consistency of evidence across sources.\n"
                    "  - Conclude whether the claim is verified (True) or refuted (False).\n"
                    "\n"
                    "At the end, output your answer in the following exact JSON format ONLY:\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"verdict\": \"True\"|\"False\",\n"
                    "  \"explanation\": \"…\"\n"
                    "}\n"
                    "\n"
                    "Replace \"…\" with your reasoning and the evidence leading to your verdict. Do NOT include any information outside this JSON.\n"
                )
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user",   "content": user_content}
                ]
                logger.debug("FINAL messages (external, long, binary_expl): %r", messages)
                return messages

            if output_type == "score_expl":
                system_content = (
                    "You are an expert fact-checking assistant. Your job is to analyze a claim and a set of articles from trusted news sources about the claim. Using logical reasoning, you must:\n"
                    "\n"
                    "- Carefully read and compare the claim to the information in the articles.\n"
                    "- Base your decision strictly on the information present in the articles.\n"
                    "- Break down your reasoning step by step, noting if the articles confirm, contradict, or ignore the claim.\n"
                    "- Avoid any speculation or information not present in the provided sources.\n"
                    "- After reasoning, output an exact JSON with:\n"
                    "  - A score from 0 (completely false) to 1 (completely true), reflecting how well the claim is supported by the articles.\n"
                    "  - A clear, concise explanation of your reasoning and the evidence used.\n"
                    "\n"
                    "Your response should strictly follow this format:\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"score\": <float between 0 and 1>,\n"
                    "  \"explanation\": \"…\"\n"
                    "}\n"
                )
                user_content = (
                    "Claim:\n"
                    f"\"{post}\"\n\n"
                    "Related articles from trusted sources:\n"
                    f"{articles_block}\n\n"
                    "Analyze the claim using only the information in the provided articles.\n"
                    "\n"
                    "- Think through each step logically:\n"
                    "  - Identify the main factual assertion of the claim.\n"
                    "  - Check if the articles support, contradict, or provide no relevant info for the claim.\n"
                    "  - Assess the credibility and consistency of evidence across sources.\n"
                    "  - Decide, on a scale from 0 (completely false) to 1 (completely true), how well these sources support the claim.\n"
                    "\n"
                    "At the end, output your answer in the following exact JSON format ONLY:\n"
                    "\n"
                    "Output (exact JSON):\n"
                    "{\n"
                    "  \"score\": <float between 0 and 1>,\n"
                    "  \"explanation\": \"…\"\n"
                    "}\n"
                    "\n"
                    "Replace \"…\" with your reasoning and the evidence leading to your score. Do NOT include any information outside this JSON.\n"
                )
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user",   "content": user_content}
                ]
                logger.debug("FINAL messages (external, long, score_expl): %r", messages)
                return messages

        # 4) If we reach here, something was mis-configured
        raise ValueError(
            f"build_messages: unsupported combo → use_external={use_external!r}, "
            f"prompt_variant={variant!r}, output_type={output_type!r}"
        )

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
