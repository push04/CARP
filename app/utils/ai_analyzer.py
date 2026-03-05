"""
AI Analysis module using OpenRouter API for advanced tender processing
"""
import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Tender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIAnalyzer:
    """
    AI Analysis class for tender processing using OpenRouter API
    """
    
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set. AI features will return fallback responses.")
        
        self.base_url = "https://openrouter.ai/api/v1"
        
        self.available_models = [
            "openrouter/auto",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "qwen/qwen3-coder:free",
            "stepfun/step-3.5-flash:free",
            "nvidia/nemotron-3-nano-30b-a3b:free",
            "google/gemma-3-27b-it:free",
        ]
        
        self.model = self.available_models[0]
        self.max_retries = 2
    
    def _call_api(self, messages: List[Dict], temperature: float = 0.3, max_tokens: int = 1000) -> Optional[str]:
        """Make API call to OpenRouter"""
        if not self.api_key:
            logger.warning("No API key configured, returning None")
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tender-carp.local",
            "X-Title": "CARP Tender Tracker"
        }
        
        # Try all free models
        for model in self.available_models:
            for attempt in range(self.max_retries):
                try:
                    payload = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                    
                    response = requests.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=90
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        self.model = model
                        return data['choices'][0]['message']['content']
                    elif response.status_code == 429:
                        logger.warning(f"Rate limited on {model}, trying next model")
                        continue
                    else:
                        logger.warning(f"Error {response.status_code} on {model}: {response.text[:100]}")
                        continue
                        
                except Exception as e:
                    logger.warning(f"Exception on {model}: {str(e)[:100]}")
                    continue
        
        logger.error("All free models failed")
        return None

    def enhance_tender_data(self, tender: "Tender") -> Dict[str, Any]:
        """
        Use AI to enhance and fill in tender data fields properly
        """
        prompt = f"""You are a tender data normalization expert. Analyze this tender and provide enhanced information.

Current Tender Data:
- Title: {tender.title or 'N/A'}
- Description: {tender.description or 'N/A'}
- Authority: {tender.issuing_authority or 'N/A'}
- Department: {tender.department or 'N/A'}
- Category: {tender.category or 'N/A'}
- Location: {tender.location or 'N/A'}
- Source: {tender.source_portal or 'N/A'}

Analyze and return ONLY a JSON object with these fields (fill in missing or improve existing):
{{
    "title": "improved_title_here",
    "issuing_authority": "correct_authority_name",
    "department": "correct_department",
    "category": "Works|Goods|Services",
    "sub_category": "specific_subcategory",
    "location": "city, district, state",
    "estimated_value_range": "Low|Medium|High|Very High",
    "key_requirements": ["requirement1", "requirement2"],
    "eligibility_criteria": "who_can_apply",
    "bid_security_required": true_or_false,
    "completion_period_months": number_or_null,
    "quality_standards": "ISO_certifications_needed",
    "experience_years_required": number_or_null,
    "verification_score": 0-100
}}

Return ONLY valid JSON, no explanation."""
        
        messages = [
            {"role": "system", "content": "You are a tender data expert. Return ONLY JSON."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(messages, temperature=0.2, max_tokens=800)
        
        if result:
            try:
                # Try to extract JSON from response
                start = result.find('{')
                end = result.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = result[start:end]
                    data = json.loads(json_str)
                    return data
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}")
        
        return {"verification_score": 50}

    def analyze_tender_fully(self, tender: "Tender") -> Dict[str, Any]:
        """
        Comprehensive AI analysis of a tender
        """
        prompt = f"""Analyze this tender comprehensively and provide insights.

Tender Info:
Title: {tender.title}
Description: {tender.description[:500] if tender.description else 'N/A'}
Authority: {tender.issuing_authority}
Department: {tender.department}
Category: {tender.category}
Location: {tender.location}
Value: {tender.tender_value}
Deadline: {tender.deadline_date}

Provide a JSON with:
{{
    "summary": "2-3 sentence summary of what this tender is about",
    "opportunity_type": "Works|Goods|Services|Consultancy",
    "sector": "Healthcare|Education|Infrastructure|IT|etc",
    "government_level": "Central|State|District|Local",
    "eligibility_requirements": ["req1", "req2"],
    "scope_of_work": "main deliverables",
    "compliance_requirements": ["req1", "req2"],
    "risk_factors": ["risk1", "risk2"],
    "recommended_bid_strategy": "advice on how to bid",
    "documents_required": ["doc1", "doc2"],
    "estimated_project_value": "value_estimate_in_INR",
    "difficulty_level": "Easy|Medium|Complex",
    "competition_estimate": "Low|Medium|High",
    "fit_score_for_medical_supplier": 0-100,
    "reasons_for_fit": ["reason1", "reason2"]
}}

Return ONLY valid JSON."""
        
        messages = [
            {"role": "system", "content": "You are a procurement expert specializing in Indian government tenders. Return ONLY JSON."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(messages, temperature=0.4, max_tokens=1500)
        
        if result:
            try:
                start = result.find('{')
                end = result.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(result[start:end])
            except:
                pass
        
        return {"summary": "Analysis unavailable", "fit_score_for_medical_supplier": 50}

    def draft_supplier_email(self, tender: "Tender", supplier_name: str) -> str:
        """
        Draft an email to a supplier about this tender
        """
        prompt = f"""Draft a professional business email to {supplier_name} about this tender opportunity.

Tender:
Title: {tender.title}
Description: {tender.description[:300] if tender.description else 'N/A'}
Authority: {tender.issuing_authority}
Deadline: {tender.deadline_date}
Location: {tender.location}
Category: {tender.category}

Company Name: Medical Solutions Provider (Please use a generic professional tone indicating we are a medical/healthcare solutions provider)

Write a professional email that:
- Is concise and clear
- Highlights key tender details
- Mentions deadline
- Requests expression of interest
- Includes call to action

Write ONLY the email content, no explanation."""
        
        messages = [
            {"role": "system", "content": "You are a professional business communication expert."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(messages, temperature=0.5, max_tokens=600)
        return result or "Email drafting failed."

    def find_similar_tenders(self, tender: "Tender", all_tenders: List["Tender"], limit: int = 5) -> List[Dict]:
        """
        Find similar tenders using AI similarity
        """
        prompt = f"""Given this tender:
Title: {tender.title}
Description: {tender.description[:200] if tender.description else 'N/A'}
Category: {tender.category}

Find the most similar tenders from this list (return as JSON array):
"""
        
        # Add up to 20 tenders for comparison
        for i, t in enumerate(all_tenders[:20]):
            if t.id != tender.id:
                prompt += f"{i+1}. {t.title[:100]} | {t.category} | {t.location}\n"
        
        prompt += """
Return JSON array of the most similar tenders (up to 5), with fields:
[{"id": tender_id, "similarity_score": 0-100, "reason": "why_similar"}]

Return ONLY valid JSON array."""
        
        messages = [
            {"role": "system", "content": "You are an expert in document similarity analysis."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(messages, temperature=0.2, max_tokens=500)
        
        if result:
            try:
                start = result.find('[')
                end = result.rfind(']') + 1
                if start >= 0 and end > start:
                    return json.loads(result[start:end])
            except:
                pass
        
        return []

    def batch_analyze_tenders(self, tenders: List["Tender"]) -> List[Dict]:
        """
        Batch analyze multiple tenders efficiently
        """
        results = []
        
        for tender in tenders:
            try:
                analysis = self.analyze_tender_fully(tender)
                results.append({
                    'tender_id': tender.id,
                    'analysis': analysis
                })
            except Exception as e:
                logger.error(f"Error analyzing tender {tender.id}: {e}")
                results.append({
                    'tender_id': tender.id,
                    'analysis': {'error': str(e)}
                })
        
        return results

    def analyze_supplier_match(self, tender: "Tender", supplier_info: str) -> Dict[str, Any]:
        """
        Analyze how well a supplier matches a tender
        """
        prompt = f"""Analyze how well this supplier matches this tender opportunity.

Tender:
Title: {tender.title}
Description: {(tender.description or 'N/A')[:300]}
Category: {tender.category}
Location: {tender.location}

Supplier: {supplier_info}

Return a JSON with:
{{
    "match_percentage": 0-100,
    "relevance_reasons": ["reason1", "reason2"],
    "recommended_actions": ["action1", "action2"],
    "estimated_price_range": {{
        "min": number_in_inr,
        "max": number_in_inr
    }},
    "risk_assessment": "Low|Medium|High"
}}

Return ONLY valid JSON."""
        
        messages = [
            {"role": "system", "content": "You are a procurement and supplier matching expert. Return ONLY JSON."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(messages, temperature=0.3, max_tokens=600)
        
        if result:
            try:
                start = result.find('{')
                end = result.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(result[start:end])
            except json.JSONDecodeError:
                pass
        
        return {
            "match_percentage": 50,
            "relevance_reasons": ["Unable to analyze - AI unavailable"],
            "recommended_actions": ["Manual review recommended"],
            "estimated_price_range": {"min": 0, "max": 0},
            "risk_assessment": "Medium"
        }
