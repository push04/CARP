"""
PDF generation utility for tender reports
"""
import os
import tempfile
from datetime import datetime
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_pdf_report(tenders, client_name="CARP BIOTECH PRIVATE LIMITED"):
    """
    Generate a professional PDF report with tender information and checkboxes for manual verification
    """
    try:
        # Create HTML content for the PDF
        html_content = generate_html_report(tenders, client_name)
        
        # Create a temporary file for the PDF
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = os.path.join(temp_dir, f"tender_report_{timestamp}.pdf")
        
        # Generate PDF using WeasyPrint
        font_config = FontConfiguration()
        HTML(string=html_content).write_pdf(
            pdf_filename,
            stylesheets=[CSS(string='''
                @page {
                    size: A4;
                    margin: 2cm;
                    @bottom-right {
                        content: "Page " counter(page) " of " counter(pages);
                        font-size: 10px;
                        color: #666;
                    }
                }
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }
                .header {
                    text-align: center;
                    border-bottom: 2px solid #333;
                    padding-bottom: 20px;
                    margin-bottom: 30px;
                }
                .client-name {
                    font-size: 24px;
                    font-weight: bold;
                    color: #2c3e50;
                    margin-bottom: 5px;
                }
                .report-title {
                    font-size: 18px;
                    color: #7f8c8d;
                    margin-bottom: 5px;
                }
                .report-date {
                    font-size: 14px;
                    color: #95a5a6;
                }
                .tender-block {
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 20px;
                    background-color: #f9f9f9;
                }
                .tender-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 10px;
                    padding-bottom: 10px;
                    border-bottom: 1px solid #eee;
                }
                .tender-title {
                    font-size: 16px;
                    font-weight: bold;
                    color: #2c3e50;
                    flex-grow: 1;
                }
                .tender-id {
                    font-size: 12px;
                    color: #7f8c8d;
                    margin-left: 10px;
                }
                .tender-details {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 10px;
                    margin-bottom: 10px;
                }
                .detail-item {
                    margin-bottom: 5px;
                }
                .detail-label {
                    font-weight: bold;
                    color: #34495e;
                    font-size: 12px;
                    text-transform: uppercase;
                }
                .detail-value {
                    font-size: 13px;
                    color: #555;
                }
                .tender-description {
                    font-size: 13px;
                    color: #555;
                    line-height: 1.5;
                    margin-bottom: 10px;
                }
                .attachments {
                    font-size: 12px;
                    color: #2980b9;
                    margin-bottom: 10px;
                }
                .checkbox-container {
                    display: flex;
                    align-items: center;
                    margin-top: 10px;
                    padding-top: 10px;
                    border-top: 1px solid #eee;
                }
                .checkbox {
                    width: 18px;
                    height: 18px;
                    margin-right: 10px;
                    transform: scale(1.2);
                }
                .checkbox-label {
                    font-size: 13px;
                    color: #7f8c8d;
                }
                .footer {
                    margin-top: 30px;
                    text-align: center;
                    font-size: 12px;
                    color: #7f8c8d;
                    border-top: 1px solid #eee;
                    padding-top: 10px;
                }
            ''', font_config=font_config)],
            font_config=font_config
        )
        
        logger.info(f"PDF report generated successfully: {pdf_filename}")
        return pdf_filename
        
    except Exception as e:
        logger.error(f"Error generating PDF report: {str(e)}")
        raise


def generate_html_report(tenders, client_name):
    """
    Generate HTML content for the PDF report
    """
    # Start building the HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Tender Report</title>
    </head>
    <body>
        <div class="header">
            <div class="client-name">{client_name}</div>
            <div class="report-title">Tender Verification Checklist</div>
            <div class="report-date">Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
        </div>
    """
    
    # Add each tender to the report
    for i, tender in enumerate(tenders, 1):
        # Format dates
        publish_date = tender.publish_date.strftime('%B %d, %Y') if tender.publish_date else 'N/A'
        deadline_date = tender.deadline_date.strftime('%B %d, %Y') if tender.deadline_date else 'N/A'
        
        # Format attachments
        attachments = ""
        if tender.attachments:
            try:
                import json
                attachment_list = json.loads(tender.attachments)
                if attachment_list:
                    attachments = "<div class='attachments'><strong>Attachments:</strong><br>" + "<br>".join([
                        f"<a href='{url}' style='color: #2980b9;'>{url}</a>" for url in attachment_list
                    ]) + "</div>"
            except:
                pass
        
        html += f"""
        <div class="tender-block">
            <div class="tender-header">
                <div class="tender-title">{tender.title}</div>
                <div class="tender-id">ID: {tender.tender_id or 'N/A'}</div>
            </div>
            
            <div class="tender-details">
                <div class="detail-item">
                    <div class="detail-label">Issuing Authority</div>
                    <div class="detail-value">{tender.issuing_authority or 'N/A'}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Department</div>
                    <div class="detail-value">{tender.department or 'N/A'}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Category</div>
                    <div class="detail-value">{tender.category or 'N/A'}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Location</div>
                    <div class="detail-value">{tender.location or 'N/A'}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Publish Date</div>
                    <div class="detail-value">{publish_date}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Deadline</div>
                    <div class="detail-value">{deadline_date}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Source Portal</div>
                    <div class="detail-value">{tender.source_portal}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Value</div>
                    <div class="detail-value">₹{tender.tender_value:,.2f} {tender.currency or 'INR' if tender.tender_value else 'N/A'}</div>
                </div>
            </div>
            
            <div class="tender-description">
                <strong>Description:</strong><br>
                {tender.description or 'No description available'}
            </div>
            
            {attachments}
            
            <div class="checkbox-container">
                <input type="checkbox" class="checkbox" id="verify_{i}">
                <label for="verify_{i}" class="checkbox-label">Mark as manually verified</label>
            </div>
        </div>
        """
    
    html += f"""
        <div class="footer">
            Report generated by Tender Tracking System | Page intentionally left blank for verification notes
        </div>
    </body>
    </html>
    """
    
    return html


def generate_single_tender_pdf(tender, client_name="CARP BIOTECH PRIVATE LIMITED"):
    """
    Generate a PDF for a single tender
    """
    return generate_pdf_report([tender], client_name)