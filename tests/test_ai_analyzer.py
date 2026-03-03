"""
Unit tests for the AI analyzer functionality
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from app.utils.ai_analyzer import AIAnalyzer
from app.models import Tender


class TestAIAnalyzer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock the OpenRouter API key to avoid needing a real one during tests
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-api-key'}):
            try:
                self.analyzer = AIAnalyzer()
                # Mock the openai API calls to avoid actual API requests
                self.analyzer.model = "openai/gpt-3.5-turbo"
            except ValueError:
                # If there's an issue with API setup, create a partially mocked instance
                self.analyzer = Mock()
                self.analyzer.analyze_tender_verification = Mock(return_value=75.0)
                self.analyzer.deduplicate_tenders = Mock(side_effect=self.mock_deduplicate)
                self.analyzer.calculate_semantic_similarity = Mock(return_value=0.8)
                self.analyzer.analyze_supplier_match = Mock(return_value={
                    "match_score": 85,
                    "relevance_reasons": ["reason1", "reason2"],
                    "missing_capabilities": ["capability1"],
                    "estimated_price_range": {"min": 1000, "max": 5000, "currency": "INR"},
                    "confidence_level": "high"
                })

    def mock_deduplicate(self, tenders):
        """Mock implementation of deduplication for testing."""
        # Simply return the original list as-is for testing purposes
        return tenders

    @patch('openai.chat.completions.create')
    def test_analyze_tender_verification_success(self, mock_create):
        """Test successful tender verification analysis."""
        # Mock the API response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "85.5"
        mock_create.return_value = mock_response
        
        # Create a test tender
        tender = Tender(
            title="Test Tender",
            description="Test Description",
            source_portal="Test Portal",
            source_url="https://example.com"
        )
        
        # Perform the analysis
        result = self.analyzer.analyze_tender_verification(tender)
        
        # Verify the result
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)

    @patch('openai.chat.completions.create')
    def test_analyze_tender_verification_error(self, mock_create):
        """Test tender verification analysis with API error."""
        # Mock an API error
        mock_create.side_effect = Exception("API Error")
        
        # Create a test tender
        tender = Tender(
            title="Test Tender",
            description="Test Description",
            source_portal="Test Portal",
            source_url="https://example.com"
        )
        
        # Perform the analysis - should return default score
        result = self.analyzer.analyze_tender_verification(tender)
        
        # Verify the result is the default score
        self.assertEqual(result, 50.0)

    def test_calculate_completeness_score(self):
        """Test completeness scoring for tenders."""
        # Create a test tender with various fields
        tender = Tender(
            title="Test Tender",
            description="Test Description",
            issuing_authority="Test Authority",
            department="Test Department",
            source_url="https://example.com",
            publish_date=None,
            deadline_date=None,
            category="goods",
            location="Test Location"
        )
        
        # Use the private method directly for testing
        score = self.analyzer._calculate_completeness_score(tender)
        
        # Should be a reasonable score based on filled fields
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_basic_deduplication(self):
        """Test basic deduplication fallback method."""
        # Create test tenders
        tender1 = Tender(title="Test 1", source_url="https://example.com/1")
        tender2 = Tender(title="Test 2", source_url="https://example.com/2")
        tender3 = Tender(title="Test 1", source_url="https://example.com/1")  # Duplicate
        
        tenders = [tender1, tender2, tender3]
        
        # Use the fallback deduplication method
        result = self.analyzer._basic_deduplication(tenders)
        
        # Should return 2 unique tenders
        self.assertEqual(len(result), 2)
        
        # Should preserve order and uniqueness
        urls = [t.source_url for t in result]
        self.assertEqual(len(set(urls)), len(urls))  # All URLs should be unique

    @patch('openai.chat.completions.create')
    def test_analyze_supplier_match_success(self, mock_create):
        """Test successful supplier match analysis."""
        # Mock the API response with JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{
            "match_score": 85,
            "relevance_reasons": ["relevant expertise", "similar projects"],
            "missing_capabilities": ["certification X"],
            "estimated_price_range": {"min": 10000, "max": 50000, "currency": "INR"},
            "confidence_level": "high"
        }'''
        mock_create.return_value = mock_response
        
        # Create a test tender
        tender = Tender(
            title="Construction Project",
            description="Building construction tender",
            category="works"
        )
        
        # Perform the analysis
        result = self.analyzer.analyze_supplier_match(tender, "Construction Company Ltd")
        
        # Verify the result structure
        self.assertIsInstance(result, dict)
        self.assertIn("match_score", result)
        self.assertIn("relevance_reasons", result)
        self.assertIn("estimated_price_range", result)
        self.assertGreaterEqual(result["match_score"], 0)
        self.assertLessEqual(result["match_score"], 100)

    @patch('openai.chat.completions.create')
    def test_analyze_supplier_match_error(self, mock_create):
        """Test supplier match analysis with API error."""
        # Mock an API error
        mock_create.side_effect = Exception("API Error")
        
        # Create a test tender
        tender = Tender(
            title="Test Tender",
            description="Test Description"
        )
        
        # Perform the analysis - should return default analysis
        result = self.analyzer.analyze_supplier_match(tender, "Test Supplier")
        
        # Verify the default result
        self.assertIsInstance(result, dict)
        self.assertEqual(result["match_score"], 50)
        self.assertIn("Default analysis due to AI error", result["relevance_reasons"])

    @patch('openai.chat.completions.create')
    def test_categorize_tender_success(self, mock_create):
        """Test successful tender categorization."""
        # Mock the API response with JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{
            "primary_category": "Works",
            "sub_category": "Construction",
            "keywords": ["construction", "building", "infrastructure"],
            "estimated_value_range": "High"
        }'''
        mock_create.return_value = mock_response
        
        # Create a test tender
        tender = Tender(
            title="Road Construction Project",
            description="Construction of roads and highways"
        )
        
        # Perform the categorization
        result = self.analyzer.categorize_tender(tender)
        
        # Verify the result structure
        self.assertIsInstance(result, dict)
        self.assertIn("primary_category", result)
        self.assertIn("sub_category", result)
        self.assertIn("keywords", result)
        self.assertIn("estimated_value_range", result)

    @patch('openai.chat.completions.create')
    def test_categorize_tender_error(self, mock_create):
        """Test tender categorization with API error."""
        # Mock an API error
        mock_create.side_effect = Exception("API Error")
        
        # Create a test tender
        tender = Tender(
            title="Test Tender",
            description="Test Description"
        )
        
        # Perform the categorization - should return default values
        result = self.analyzer.categorize_tender(tender)
        
        # Verify the default result
        self.assertIsInstance(result, dict)
        self.assertEqual(result["primary_category"], "Services")
        self.assertEqual(result["sub_category"], "General")


if __name__ == '__main__':
    unittest.main()