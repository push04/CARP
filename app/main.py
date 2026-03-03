"""
Main Flask application blueprint
"""
from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from app.models import Tender, Supplier, FetchLog
from app import db
from app.fetchers.tender_fetcher import TenderFetcher
from app.utils.pdf_generator import generate_pdf_report
from app.utils.supplier_matcher import SupplierMatcher
import pandas as pd
import os
from datetime import datetime, timedelta
import threading
import time

main_bp = Blueprint('main', __name__)

# Global variable to track auto-fetch status
auto_fetch_enabled = False
auto_fetch_thread = None


@main_bp.route('/')
def index():
    """Main dashboard page"""
    # Get basic statistics
    total_tenders = Tender.query.count()
    open_tenders = Tender.query.filter_by(status='open').count()
    bihar_tenders = Tender.query.filter_by(state='Bihar').count()
    jharkhand_tenders = Tender.query.filter_by(state='Jharkhand').count()
    
    # Get recent fetch logs
    recent_logs = FetchLog.query.order_by(FetchLog.created_at.desc()).limit(10).all()
    
    return render_template('dashboard.html',
                         total_tenders=total_tenders,
                         open_tenders=open_tenders,
                         bihar_tenders=bihar_tenders,
                         jharkhand_tenders=jharkhand_tenders,
                         recent_logs=[log.to_dict() for log in recent_logs])


@main_bp.route('/api/tenders')
def api_tenders():
    """API endpoint to get tenders with filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 25, type=int), 100)
    
    # Build query with filters
    query = Tender.query
    
    # Apply filters
    state_filter = request.args.get('state')
    if state_filter:
        query = query.filter(Tender.state == state_filter)
    
    category_filter = request.args.get('category')
    if category_filter:
        query = query.filter(Tender.category == category_filter)
    
    status_filter = request.args.get('status')
    if status_filter:
        query = query.filter(Tender.status == status_filter)
    
    # Date range filters
    start_date = request.args.get('start_date')
    if start_date:
        query = query.filter(Tender.publish_date >= datetime.fromisoformat(start_date))
    
    end_date = request.args.get('end_date')
    if end_date:
        query = query.filter(Tender.publish_date <= datetime.fromisoformat(end_date))
    
    # Search filter
    search_term = request.args.get('search')
    if search_term:
        query = query.filter(
            Tender.title.contains(search_term) |
            Tender.description.contains(search_term) |
            Tender.issuing_authority.contains(search_term)
        )
    
    # Sorting
    sort_by = request.args.get('sort_by', 'publish_date')
    sort_order = request.args.get('sort_order', 'desc')
    
    if hasattr(Tender, sort_by):
        column = getattr(Tender, sort_by)
        if sort_order.lower() == 'asc':
            query = query.order_by(column.asc())
        else:
            query = query.order_by(column.desc())
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    tenders = [tender.to_dict() for tender in pagination.items]
    
    return jsonify({
        'tenders': tenders,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'per_page': per_page
    })


@main_bp.route('/tender/<int:tender_id>')
def tender_detail(tender_id):
    """Detailed view of a specific tender"""
    tender = Tender.query.get_or_404(tender_id)
    return render_template('tender_detail.html', tender=tender)


@main_bp.route('/fetch_manual', methods=['POST'])
def fetch_manual():
    """Manually trigger a fetch operation"""
    data = request.json
    sources = data.get('sources', [])  # Specific sources to fetch from
    
    fetcher = TenderFetcher()
    
    # Run fetch in background thread
    def run_fetch():
        fetcher.fetch_all(sources=sources if sources else None)
    
    thread = threading.Thread(target=run_fetch)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'started', 'message': 'Fetch operation started'})


@main_bp.route('/toggle_auto_fetch', methods=['POST'])
def toggle_auto_fetch():
    """Toggle auto-fetch functionality"""
    global auto_fetch_enabled, auto_fetch_thread
    
    data = request.json
    enabled = data.get('enabled', False)
    
    if enabled and not auto_fetch_enabled:
        # Start auto-fetch
        auto_fetch_enabled = True
        
        def run_auto_fetch():
            fetcher = TenderFetcher()
            while auto_fetch_enabled:
                fetcher.fetch_all()
                time.sleep(int(os.getenv('AUTO_FETCH_INTERVAL', 1800)))  # Default 30 minutes
        
        auto_fetch_thread = threading.Thread(target=run_auto_fetch)
        auto_fetch_thread.daemon = True
        auto_fetch_thread.start()
        
        return jsonify({'status': 'enabled', 'message': 'Auto-fetch enabled'})
    
    elif not enabled and auto_fetch_enabled:
        # Stop auto-fetch
        auto_fetch_enabled = False
        return jsonify({'status': 'disabled', 'message': 'Auto-fetch disabled'})
    
    return jsonify({'status': 'unchanged'})


@main_bp.route('/delete_old_tenders', methods=['POST'])
def delete_old_tenders():
    """Delete tenders older than a specified number of days"""
    data = request.json
    days_old = data.get('days_old', 90)  # Default 90 days
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    old_tenders = Tender.query.filter(Tender.publish_date < cutoff_date).all()
    
    deleted_count = len(old_tenders)
    for tender in old_tenders:
        db.session.delete(tender)
    
    db.session.commit()
    
    return jsonify({
        'status': 'completed',
        'deleted_count': deleted_count,
        'message': f'Deleted {deleted_count} tenders older than {days_old} days'
    })


@main_bp.route('/export_csv')
def export_csv():
    """Export tenders to CSV file"""
    tenders = Tender.query.all()
    tender_dicts = [tender.to_dict() for tender in tenders]
    
    df = pd.DataFrame(tender_dicts)
    
    # Create temporary file
    temp_filename = f"tenders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(temp_filename, index=False)
    
    return send_file(temp_filename, as_attachment=True)


@main_bp.route('/export_pdf', methods=['POST'])
def export_pdf():
    """Export selected tenders to PDF report"""
    data = request.json
    tender_ids = data.get('tender_ids', [])
    
    if not tender_ids:
        return jsonify({'error': 'No tender IDs provided'}), 400
    
    tenders = Tender.query.filter(Tender.id.in_(tender_ids)).all()
    
    if not tenders:
        return jsonify({'error': 'No valid tender IDs provided'}), 400
    
    # Generate PDF report
    pdf_filename = generate_pdf_report(tenders, client_name="CARP BIOTECH PRIVATE LIMITED")
    
    return jsonify({'filename': pdf_filename})


@main_bp.route('/get_supplier_matches/<int:tender_id>')
def get_supplier_matches(tender_id):
    """Get supplier matches for a specific tender"""
    tender = Tender.query.get_or_404(tender_id)
    
    matcher = SupplierMatcher()
    matches = matcher.find_supplier_matches(tender)
    
    # Update tender with supplier matches
    tender.supplier_matches = str(matches)
    db.session.commit()
    
    return jsonify(matches)


@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page for API keys and configurations"""
    if request.method == 'POST':
        # Update settings from form data
        # This would typically update environment variables or a settings table
        pass
    
    return render_template('settings.html')


@main_bp.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})


@main_bp.route('/metrics')
def metrics():
    """Metrics endpoint for monitoring"""
    total_tenders = Tender.query.count()
    open_tenders = Tender.query.filter_by(status='open').count()
    closed_tenders = Tender.query.filter_by(status='closed').count()
    
    return jsonify({
        'total_tenders': total_tenders,
        'open_tenders': open_tenders,
        'closed_tenders': closed_tenders,
        'auto_fetch_enabled': auto_fetch_enabled
    })