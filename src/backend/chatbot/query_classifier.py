"""
Query Classifier Module
Classifies user queries to determine if they're questions and their relevance
"""

import logging
import json
from typing import Dict, Any
import litellm
from ..rag.query_engine import load_prompts
from ..config import settings

logger = logging.getLogger(__name__)


class QueryClassifier:
    """
    Classifies user queries to determine:
    - Is it a question?
    - Is it relevant to educational content?
    - What type of question is it?
    """
    
    def __init__(self):
        self.llm_model = settings.LLM_MODEL
        self.prompts = load_prompts()
        self.enabled = settings.ENABLE_QUERY_CLASSIFICATION
        
        logger.info(f"Initialized QueryClassifier (enabled={self.enabled})")
    
    async def classify_query(self, query: str) -> Dict[str, Any]:
        """
        Classify a user query
        
        Args:
            query: User's input text
        
        Returns:
            Dict with classification results:
            - is_question: bool
            - is_relevant: bool
            - question_type: str
            - confidence: float
            - reasoning: str
        """
        if not self.enabled:
            # Default classification when disabled
            return {
                "is_question": True,
                "is_relevant": True,
                "question_type": "general",
                "confidence": 1.0,
                "reasoning": "Classification disabled"
            }
        
        try:
            # Load prompts
            system_prompt = self.prompts.get("classification_system_prompt", "")
            user_prompt_template = self.prompts.get("classification_user_prompt", "")
            user_prompt = user_prompt_template.format(query=query)
            
            # Call LLM for classification
            response = await litellm.acompletion(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for consistent classification
                max_tokens=200
            )
            
            # Parse JSON response
            classification_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in classification_text:
                classification_text = classification_text.split("```json")[1].split("```")[0].strip()
            elif "```" in classification_text:
                classification_text = classification_text.split("```")[1].split("```")[0].strip()
            
            classification = json.loads(classification_text)
            
            logger.info(f"Query classified: {classification}")
            return classification
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification response: {e}")
            # Default to treating as question
            return {
                "is_question": True,
                "is_relevant": True,
                "question_type": "general",
                "confidence": 0.5,
                "reasoning": "Classification parsing failed"
            }
        
        except Exception as e:
            logger.error(f"Error classifying query: {str(e)}")
            # Default to treating as question
            return {
                "is_question": True,
                "is_relevant": True,
                "question_type": "general",
                "confidence": 0.5,
                "reasoning": f"Classification error: {str(e)}"
            }
    
    def should_store_question(self, classification: Dict[str, Any]) -> bool:
        """
        Determine if a query should be stored as a question in the database
        
        Args:
            classification: Classification result from classify_query
        
        Returns:
            bool: True if should be stored
        """
        return (
            classification.get("is_question", False) and
            classification.get("is_relevant", False) and
            classification.get("confidence", 0.0) >= 0.6
        )

