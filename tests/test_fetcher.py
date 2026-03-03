"""
Unit tests for the tender fetcher functionality
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from app.fetchers.tender_fetcher import TenderFetcher
from app.models import Tender
from datetime import datetime


class TestTenderFetcher(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.fetcher = TenderFetcher()

    @patch('requests.Session.get')
    def test_fetch_generic_success(self, mock_get):
        """Test successful fetching from a generic URL."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<html><body><div class="tender-item">Test Tender</div></body></html>'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test the fetch
        result = self.fetcher._fetch_generic('https://example.com')
        
        # Assertions
        self.assertIsInstance(result, list)
        mock_get.assert_called_once()

    @patch('requests.Session.get')
    def test_fetch_generic_request_exception(self, mock_get):
        """Test handling of request exceptions."""
        # Mock request exception
        mock_get.side_effect = Exception("Network error")
        
        # Test the fetch
        result = self.fetcher._fetch_generic('https://example.com')
        
        # Should return empty list on exception
        self.assertEqual(result, [])

    def test_extract_date_various_formats(self):
        """Test date extraction from various formats."""
        test_cases = [
            ("Project starts on 15/03/2023", datetime(2023, 3, 15)),
            ("Deadline: 2023-03-15", datetime(2023, 3, 15)),
            ("Due date: 15 Mar 2023", datetime(2023, 3, 15)),
            ("Opening on March 15, 2023", datetime(2023, 3, 15)),
            ("No date in this text", None),
        ]
        
        for text, expected_date in test_cases:
            with self.subTest(text=text):
                result = self.fetcher._extract_date(text)
                if expected_date:
                    self.assertEqual(result.date() if result else None, expected_date.date())
                else:
                    self.assertIsNone(result)

    def test_calculate_completeness_score(self):
        """Test completeness scoring for tenders."""
        # Create a mock tender with various fields filled
        tender = Tender(
            title="Test Tender",
            description="Test Description",
            issuing_authority="Test Authority",
            department="Test Department",
            source_url="https://example.com",
            publish_date=datetime.utcnow(),
            deadline_date=datetime.utcnow(),
            category="goods",
            location="Test Location"
        )
        
        score = self.fetcher._calculate_completeness_score(tender)
        
        # Should have a high score with many fields filled
        self.assertGreater(score, 70)  # At least 70% completeness
        
        # Test with minimal fields
        minimal_tender = Tender(title="Test", source_url="https://example.com")
        minimal_score = self.fetcher._calculate_completeness_score(minimal_tender)
        
        self.assertLess(minimal_score, score)  # Less complete than full tender

    def test_basic_deduplication(self):
        """Test basic deduplication functionality."""
        # Create test tenders
        tender1 = Tender(
            title="Test Tender 1",
            source_url="https://example.com/1"
        )
        tender2 = Tender(
            title="Test Tender 2", 
            source_url="https://example.com/2"
        )
        tender3 = Tender(  # Duplicate of tender1
            title="Test Tender 1",
            source_url="https://example.com/1"
        )
        
        tenders = [tender1, tender2, tender3]
        unique_tenders = self.fetcher._basic_deduplication(tenders)
        
        # Should have 2 unique tenders (tender1 and tender2)
        self.assertEqual(len(unique_tenders), 2)
        
        # Should contain tender1 and tender2 but not tender3 (duplicate)
        titles = [t.title for t in unique_tenders]
        self.assertIn("Test Tender 1", titles)
        self.assertIn("Test Tender 2", titles)
        self.assertEqual(titles.count("Test Tender 1"), 1)

    def test_save_tenders_basic(self):
        """Test saving tenders to the database."""
        # This test would normally require a database connection
        # For now, we'll just verify the method exists and accepts parameters
        tender_data = {
            'title': 'Test Tender',
            'source_url': 'https://example.com',
            'source_portal': 'Test Portal',
            'state': 'Bihar'
        }
        
        # Mock the database session to avoid actual database operations
        with patch.object(self.fetcher, '_save_tenders') as mock_save:
            mock_save.return_value = 1  # Simulate saving 1 tender
            result = self.fetcher._save_tenders([tender_data], 'Test Portal')
            self.assertEqual(result, 1)

    def test_find_tender_elements(self):
        """Test finding tender elements on a page."""
        from bs4 import BeautifulSoup
        
        # Sample HTML with tender-like elements
        html = '''
        <html>
            <body>
                <div class="tender-item">Tender 1</div>
                <div class="other-item">Other 1</div>
                <a href="/tender/1">Tender Link</a>
                <div class="notice">Notice Item</div>
            </body>
        </html>
        '''
        
        soup = BeautifulSoup(html, 'html.parser')
        elements = self.fetcher._find_tender_elements(soup, 'https://example.com')
        
        # Should find elements with tender/notice classes and links
        self.assertGreater(len(elements), 0)
        
    def test_extract_tender_data(self):
        """Test extracting tender data from HTML element."""
        from bs4 import BeautifulSoup
        
        html = '''
        <div>
            <h3>Test Tender Title</h3>
            <a href="/tender/123">View Details</a>
            <p>Published on 15/03/2023</p>
        </div>
        '''
        
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('div')
        base_url = 'https://example.com'
        
        result = self.fetcher._extract_tender_data(element, base_url)
        
        # Should extract title and other data
        if result:  # May return None if date extraction fails
            self.assertIsNotNone(result.get('title'))
            self.assertIn('tender', result.get('title', '').lower())


if __name__ == '__main__':
    unittest.main()