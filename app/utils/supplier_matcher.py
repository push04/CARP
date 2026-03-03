"""
Supplier matching functionality for the tender tracking system
"""
import pandas as pd
import numpy as np
from rapidfuzz import fuzz, process
from typing import List, Dict, Tuple
import logging
from app.models import Tender, Supplier
from app import db
from app.utils.ai_analyzer import AIAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SupplierMatcher:
    """
    Class to handle supplier matching for tenders
    """
    
    def __init__(self):
        self.ai_analyzer = AIAnalyzer()
        
    def find_supplier_matches(self, tender: Tender, limit: int = 5) -> List[Dict]:
        """
        Find supplier matches for a given tender
        """
        try:
            # Get all suppliers from the database
            suppliers = Supplier.query.all()
            
            if not suppliers:
                return []
                
            # Extract tender keywords for matching
            tender_keywords = self._extract_keywords(tender)
            
            # Score each supplier against the tender
            scored_suppliers = []
            for supplier in suppliers:
                score = self._calculate_supplier_score(tender, supplier, tender_keywords)
                if score > 0:  # Only include suppliers with positive scores
                    scored_suppliers.append((supplier, score))
            
            # Sort suppliers by score (descending)
            scored_suppliers.sort(key=lambda x: x[1], reverse=True)
            
            # Prepare results with AI-enhanced analysis
            results = []
            for supplier, score in scored_suppliers[:limit]:
                # Use AI to get more detailed analysis
                ai_analysis = self.ai_analyzer.analyze_supplier_match(
                    tender, 
                    f"{supplier.name} - {supplier.products_services or ''}"
                )
                
                results.append({
                    'supplier_id': supplier.id,
                    'name': supplier.name,
                    'contact_person': supplier.contact_person,
                    'email': supplier.email,
                    'phone': supplier.phone,
                    'match_score': round(score * 100, 2),  # Convert to percentage
                    'ai_analysis': ai_analysis,
                    'address': supplier.address,
                    'products_services': supplier.products_services,
                    'categories': supplier.categories,
                    'certifications': supplier.certifications,
                    'experience_years': supplier.experience_years,
                    'rating': supplier.rating
                })
                
            return results
            
        except Exception as e:
            logger.error(f"Error finding supplier matches: {str(e)}")
            return []

    def _extract_keywords(self, tender: Tender) -> List[str]:
        """
        Extract keywords from tender for matching purposes
        """
        keywords = []
        
        # Add title words
        if tender.title:
            keywords.extend(tender.title.lower().split())
            
        # Add description words
        if tender.description:
            keywords.extend(tender.description.lower().split())
            
        # Add category and subcategory
        if tender.category:
            keywords.append(tender.category.lower())
        if tender.sub_category:
            keywords.append(tender.sub_category.lower())
            
        # Remove duplicates and return
        return list(set(keywords))

    def _calculate_supplier_score(self, tender: Tender, supplier: Supplier, tender_keywords: List[str]) -> float:
        """
        Calculate match score between a tender and supplier
        """
        score = 0.0
        
        # Fuzzy matching on supplier name vs tender title/description
        if supplier.name:
            name_match = fuzz.token_set_ratio(tender.title.lower(), supplier.name.lower())
            score += name_match * 0.2  # Weight of 20%
            
        # Match supplier products/services with tender requirements
        if supplier.products_services:
            supplier_products = supplier.products_services.lower()
            tender_text = f"{tender.title} {tender.description}".lower()
            product_match = fuzz.partial_ratio(supplier_products, tender_text)
            score += product_match * 0.3  # Weight of 30%
            
        # Keyword matching
        if supplier.products_services:
            supplier_keywords = supplier.products_services.lower().split()
            keyword_matches = 0
            total_keywords = len(tender_keywords)
            
            for keyword in tender_keywords:
                if keyword in supplier_products:
                    keyword_matches += 1
                    
            if total_keywords > 0:
                keyword_score = (keyword_matches / total_keywords) * 100
                score += keyword_score * 0.3  # Weight of 30%
                
        # Category matching
        if supplier.categories and tender.category:
            supplier_categories = eval(supplier.categories) if isinstance(supplier.categories, str) else supplier.categories or []
            if tender.category.lower() in [cat.lower() for cat in supplier_categories]:
                score += 20  # Bonus for category match
                
        # Geographic proximity (if location is specified)
        if supplier.address and tender.location:
            # Simple geographic match - could be enhanced with distance calculation
            if tender.location.lower() in supplier.address.lower():
                score += 15  # Bonus for location match
                
        # Certification match (could be enhanced based on tender requirements)
        if supplier.certifications:
            score += 5  # Small bonus for having certifications
            
        # Normalize score to 0-1 range
        return min(score / 100.0, 1.0)

    def add_supplier(self, supplier_data: Dict) -> bool:
        """
        Add a new supplier to the database
        """
        try:
            supplier = Supplier(
                name=supplier_data.get('name'),
                contact_person=supplier_data.get('contact_person'),
                email=supplier_data.get('email'),
                phone=supplier_data.get('phone'),
                address=supplier_data.get('address'),
                products_services=str(supplier_data.get('products_services', [])),
                categories=str(supplier_data.get('categories', [])),
                certifications=str(supplier_data.get('certifications', [])),
                experience_years=supplier_data.get('experience_years'),
                rating=supplier_data.get('rating', 0.0),
                verified=supplier_data.get('verified', False)
            )
            
            db.session.add(supplier)
            db.session.commit()
            
            logger.info(f"Added new supplier: {supplier.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding supplier: {str(e)}")
            db.session.rollback()
            return False

    def update_supplier_matches_for_all_tenders(self):
        """
        Update supplier matches for all tenders in the database
        """
        try:
            tenders = Tender.query.all()
            updated_count = 0
            
            for tender in tenders:
                matches = self.find_supplier_matches(tender)
                tender.supplier_matches = str(matches)
                updated_count += 1
                
            db.session.commit()
            logger.info(f"Updated supplier matches for {updated_count} tenders")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating supplier matches for all tenders: {str(e)}")
            return 0

    def upload_supplier_list(self, file_path: str) -> int:
        """
        Upload suppliers from a CSV file
        """
        try:
            df = pd.read_csv(file_path)
            imported_count = 0
            
            for _, row in df.iterrows():
                supplier_data = {
                    'name': row.get('name', ''),
                    'contact_person': row.get('contact_person'),
                    'email': row.get('email'),
                    'phone': row.get('phone'),
                    'address': row.get('address'),
                    'products_services': row.get('products_services', []),
                    'categories': row.get('categories', []),
                    'certifications': row.get('certifications', []),
                    'experience_years': row.get('experience_years'),
                    'rating': row.get('rating', 0.0),
                    'verified': row.get('verified', False)
                }
                
                if self.add_supplier(supplier_data):
                    imported_count += 1
                    
            logger.info(f"Imported {imported_count} suppliers from {file_path}")
            return imported_count
            
        except Exception as e:
            logger.error(f"Error uploading supplier list: {str(e)}")
            return 0