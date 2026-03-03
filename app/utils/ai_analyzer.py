"""
AI Analysis module using OpenRouter API for advanced tender processing
"""
import openai
import os
import json
import logging
from typing import Dict, List, Optional
from app.models import Tender

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIAnalyzer:
    """
    AI Analysis class for tender processing using OpenRouter API
    """
    
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        
        # Set OpenAI API key and base URL for OpenRouter
        openai.api_key = self.api_key
        openai.base_url = "https://openrouter.ai/api/v1"
        
        # Model to use (you can change this to any supported model on OpenRouter)
        self.model = "openai/gpt-3.5-turbo"
        
        # Alternative models available on OpenRouter
        self.available_models = [
            "openai/gpt-3.5-turbo",
            "openai/gpt-4",
            "anthropic/claude-3-haiku",
            "google/gemini-pro",
            "meta-llama/llama-2-70b-chat"
        ]

    def analyze_tender_verification(self, tender: Tender) -> float:
        """
        Analyze a tender and return a verification score (0-100)
        Higher score indicates more confidence in the tender's authenticity
        """
        try:
            prompt = f"""
            Analyze the following tender information and provide a verification score from 0 to 100.
            Consider factors like:
            - Completeness of information
            - Presence of official government domains
            - Professional formatting
            - Standard tender terminology
            - Plausibility of details
            
            Tender Details:
            Title: {tender.title}
            Description: {tender.description}
            Issuing Authority: {tender.issuing_authority}
            Department: {tender.department}
            Source Portal: {tender.source_portal}
            Source URL: {tender.source_url}
            Category: {tender.category}
            Location: {tender.location}
            State: {tender.state}
            
            Return only a number between 0 and 100 representing the verification score.
            """
            
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert tender verification analyst. Respond only with a number between 0 and 100."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0.1
            )
            
            score_text = response.choices[0].message.content.strip()
            score = float(score_text) if score_text.replace('.', '', 1).isdigit() else 50.0
            
            # Ensure score is within bounds
            score = max(0, min(100, score))
            
            return score
            
        except Exception as e:
            logger.error(f"Error analyzing tender verification: {str(e)}")
            return 50.0  # Default score if analysis fails

    def deduplicate_tenders(self, tenders: List[Tender]) -> List[Tender]:
        """
        Use AI to semantically deduplicate tenders
        Returns a list of unique tenders based on semantic similarity
        """
        if len(tenders) <= 1:
            return tenders
            
        try:
            # Group tenders by potential similarity
            unique_tenders = []
            processed_indices = set()
            
            for i, tender1 in enumerate(tenders):
                if i in processed_indices:
                    continue
                    
                # Compare with remaining tenders
                similar_group = [tender1]
                processed_indices.add(i)
                
                for j, tender2 in enumerate(tenders[i+1:], i+1):
                    if j in processed_indices:
                        continue
                        
                    similarity = self.calculate_semantic_similarity(tender1, tender2)
                    
                    # If similarity is above threshold, consider them duplicates
                    if similarity > 0.85:  # 85% similarity threshold
                        similar_group.append(tender2)
                        processed_indices.add(j)
                
                # From the similar group, select the most complete tender
                best_tender = max(similar_group, key=lambda t: self._calculate_completeness_score(t))
                unique_tenders.append(best_tender)
                
            return unique_tenders
            
        except Exception as e:
            logger.error(f"Error in AI deduplication: {str(e)}")
            # Fallback to basic deduplication if AI fails
            return self._basic_deduplication(tenders)

    def calculate_semantic_similarity(self, tender1: Tender, tender2: Tender) -> float:
        """
        Calculate semantic similarity between two tenders using AI
        """
        try:
            prompt = f"""
            Compare the following two tenders and rate their semantic similarity on a scale of 0 to 1.
            Consider the title, description, issuing authority, and other key details.
            
            Tender 1:
            Title: {tender1.title}
            Description: {tender1.description}
            Issuing Authority: {tender1.issuing_authority}
            Department: {tender1.department}
            Category: {tender1.category}
            
            Tender 2:
            Title: {tender2.title}
            Description: {tender2.description}
            Issuing Authority: {tender2.issuing_authority}
            Department: {tender2.department}
            Category: {tender2.category}
            
            Return only a decimal number between 0 and 1 representing the similarity score.
            """
            
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in document similarity analysis. Respond only with a decimal number between 0 and 1."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0.1
            )
            
            similarity_text = response.choices[0].message.content.strip()
            similarity = float(similarity_text) if similarity_text.replace('.', '', 1).replace('-', '', 1).isdigit() else 0.0
            
            # Ensure similarity is within bounds
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            logger.error(f"Error calculating semantic similarity: {str(e)}")
            return 0.0

    def _calculate_completeness_score(self, tender: Tender) -> float:
        """
        Calculate a completeness score based on available fields
        """
        score = 0.0
        
        if tender.title:
            score += 20
        if tender.description and len(tender.description) > 50:
            score += 15
        if tender.issuing_authority:
            score += 15
        if tender.department:
            score += 10
        if tender.source_url:
            score += 10
        if tender.publish_date:
            score += 10
        if tender.deadline_date:
            score += 10
        if tender.category:
            score += 10
        if tender.location:
            score += 10
            
        return min(100, score)

    def _basic_deduplication(self, tenders: List[Tender]) -> List[Tender]:
        """
        Basic deduplication as fallback when AI analysis fails
        """
        seen_urls = set()
        seen_titles = set()
        unique_tenders = []
        
        for tender in tenders:
            if tender.source_url not in seen_urls or tender.title not in seen_titles:
                seen_urls.add(tender.source_url)
                seen_titles.add(tender.title)
                unique_tenders.append(tender)
                
        return unique_tenders

    def analyze_supplier_match(self, tender: Tender, supplier_description: str) -> Dict:
        """
        Analyze how well a supplier matches a tender requirement
        """
        try:
            prompt = f"""
            Analyze how well the following supplier matches the tender requirement.
            
            TENDER REQUIREMENT:
            {tender.title}
            Description: {tender.description}
            Category: {tender.category}
            Sub-category: {tender.sub_category}
            
            SUPPLIER DESCRIPTION:
            {supplier_description}
            
            Provide your analysis in the following JSON format:
            {{
                "match_score": <number between 0 and 100>,
                "relevance_reasons": ["reason1", "reason2"],
                "missing_capabilities": ["capability1", "capability2"],
                "estimated_price_range": {{
                    "min": <minimum estimated price>,
                    "max": <maximum estimated price>,
                    "currency": "INR"
                }},
                "confidence_level": "high|medium|low"
            }}
            """
            
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert procurement analyst. Respond only with a valid JSON object."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing supplier match: {str(e)}")
            # Return default analysis if AI fails
            return {
                "match_score": 50,
                "relevance_reasons": ["Default analysis due to AI error"],
                "missing_capabilities": ["Full analysis unavailable"],
                "estimated_price_range": {
                    "min": 0,
                    "max": 0,
                    "currency": "INR"
                },
                "confidence_level": "low"
            }

    def draft_supplier_email(self, tender: Tender, supplier_name: str, supplier_contact: str) -> str:
        """
        Draft an email to a supplier about a tender opportunity
        """
        try:
            prompt = f"""
            Draft a professional business email to {supplier_name} ({supplier_contact}) about the following tender opportunity:
            
            TENDER:
            Title: {tender.title}
            Description: {tender.description}
            Category: {tender.category}
            Deadline: {tender.deadline_date}
            Location: {tender.location}
            
            The email should:
            - Be professional and concise
            - Highlight key requirements
            - Mention the deadline
            - Request expression of interest
            - Include our company name: CARP BIOTECH PRIVATE LIMITED
            
            Return only the email content.
            """
            
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional business communication assistant. Return only the email content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.5
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error drafting supplier email: {str(e)}")
            return f"""Subject: Tender Opportunity: {tender.title}

Dear {supplier_name},

We have identified a potential tender opportunity that may align with your capabilities:

Tender: {tender.title}
Description: {tender.description}
Deadline: {tender.deadline_date}
Location: {tender.location}

Please let us know if you're interested in exploring this opportunity.

Best regards,
CARP BIOTECH PRIVATE LIMITED"""

    def categorize_tender(self, tender: Tender) -> Dict:
        """
        Categorize a tender using AI analysis
        """
        try:
            prompt = f"""
            Categorize the following tender according to standard procurement categories:
            
            Title: {tender.title}
            Description: {tender.description}
            
            Provide your response in the following JSON format:
            {{
                "primary_category": "Works|Goods|Services",
                "sub_category": "<specific subcategory>",
                "keywords": ["keyword1", "keyword2", "keyword3"],
                "estimated_value_range": "Low (<₹10L)|Medium (₹10L-₹1Cr)|High (₹1Cr-₹10Cr)|Very High (>₹10Cr)"
            }}
            """
            
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert tender categorization specialist. Respond only with a valid JSON object."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Error categorizing tender: {str(e)}")
            return {
                "primary_category": "Services",
                "sub_category": "General",
                "keywords": ["procurement", "general"],
                "estimated_value_range": "Medium"
            }