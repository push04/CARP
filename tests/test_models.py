"""
Unit tests for the database models
"""
import unittest
from datetime import datetime
from app import create_app
from app.extensions import db
from app.models import Tender, Supplier, FetchLog


class TestModels(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

    def tearDown(self):
        """Tear down test fixtures after each test method."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_tender_model(self):
        """Test Tender model creation and properties."""
        tender = Tender(
            title='Test Tender',
            description='Test Description',
            issuing_authority='Test Authority',
            source_portal='Test Portal',
            source_url='https://example.com',
            location='Patna, Bihar',
            last_checked=datetime.utcnow()
        )
        
        db.session.add(tender)
        db.session.commit()
        
        self.assertEqual(tender.title, 'Test Tender')
        self.assertEqual(tender.location, 'Patna, Bihar')
        self.assertIsNotNone(tender.id)
        self.assertIsNotNone(tender.created_at)
        self.assertIsNotNone(tender.updated_at)

    def test_supplier_model(self):
        """Test Supplier model creation and properties."""
        supplier = Supplier(
            name='Test Supplier',
            contact_person='John Doe',
            email='john@example.com',
            phone='1234567890',
            address='Test Address',
            products_services='["Product A", "Service B"]',
            categories='["Category 1", "Category 2"]',
            certifications='["ISO 9001", "ISO 14001"]',
            experience_years=5,
            rating=4.5
        )
        
        db.session.add(supplier)
        db.session.commit()
        
        self.assertEqual(supplier.name, 'Test Supplier')
        self.assertEqual(supplier.email, 'john@example.com')
        self.assertEqual(supplier.experience_years, 5)
        self.assertEqual(supplier.rating, 4.5)
        self.assertIsNotNone(supplier.id)
        self.assertIsNotNone(supplier.created_at)
        self.assertIsNotNone(supplier.updated_at)

    def test_fetch_log_model(self):
        """Test FetchLog model creation and properties."""
        fetch_log = FetchLog(
            source_portal='Test Portal',
            success_count=10,
            error_count=2,
            total_processed=12
        )
        
        db.session.add(fetch_log)
        db.session.commit()
        
        self.assertEqual(fetch_log.source_portal, 'Test Portal')
        self.assertEqual(fetch_log.success_count, 10)
        self.assertEqual(fetch_log.error_count, 2)
        self.assertEqual(fetch_log.total_processed, 12)
        self.assertIsNotNone(fetch_log.id)
        self.assertIsNotNone(fetch_log.created_at)

    def test_tender_to_dict(self):
        """Test Tender model to_dict method."""
        tender = Tender(
            title='Test Tender',
            description='Test Description',
            issuing_authority='Test Authority',
            source_portal='Test Portal',
            source_url='https://example.com',
            state='Bihar',
            last_checked=datetime.utcnow()
        )
        
        db.session.add(tender)
        db.session.commit()
        
        tender_dict = tender.to_dict()
        
        self.assertEqual(tender_dict['title'], 'Test Tender')
        self.assertEqual(tender_dict['state'], 'Bihar')
        self.assertIn('created_at', tender_dict)
        self.assertIn('updated_at', tender_dict)

    def test_supplier_to_dict(self):
        """Test Supplier model to_dict method."""
        supplier = Supplier(
            name='Test Supplier',
            contact_person='John Doe',
            email='john@example.com',
            phone='1234567890'
        )
        
        db.session.add(supplier)
        db.session.commit()
        
        supplier_dict = supplier.to_dict()
        
        self.assertEqual(supplier_dict['name'], 'Test Supplier')
        self.assertEqual(supplier_dict['email'], 'john@example.com')
        self.assertIn('created_at', supplier_dict)
        self.assertIn('updated_at', supplier_dict)

    def test_fetch_log_to_dict(self):
        """Test FetchLog model to_dict method."""
        fetch_log = FetchLog(
            source_portal='Test Portal',
            success_count=10,
            error_count=2
        )
        
        db.session.add(fetch_log)
        db.session.commit()
        
        log_dict = fetch_log.to_dict()
        
        self.assertEqual(log_dict['source_portal'], 'Test Portal')
        self.assertEqual(log_dict['success_count'], 10)
        self.assertEqual(log_dict['error_count'], 2)
        self.assertIn('created_at', log_dict)


if __name__ == '__main__':
    unittest.main()