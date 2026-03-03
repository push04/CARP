/*
JavaScript for Tender Tracking Dashboard
*/

// Global variables
let autoFetchEnabled = false;
let currentPage = 1;
let currentPerPage = 25;
let currentFilters = {};
let currentSort = { field: 'publish_date', order: 'desc' };

// DOM ready function
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the dashboard
    initializeDashboard();
    
    // Set up event listeners
    setupEventListeners();
    
    // Load initial data
    loadTenders(currentPage, currentPerPage, currentFilters, currentSort);
});

// Initialize dashboard components
function initializeDashboard() {
    // Initialize tooltips
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Load dashboard stats
    loadDashboardStats();
}

// Set up event listeners
function setupEventListeners() {
    // Auto-fetch toggle
    const autoFetchToggle = document.getElementById('autoFetchToggle');
    if (autoFetchToggle) {
        autoFetchToggle.addEventListener('change', function() {
            toggleAutoFetch(this.checked);
        });
    }
    
    // Manual fetch button
    const manualFetchBtn = document.getElementById('manualFetchBtn');
    if (manualFetchBtn) {
        manualFetchBtn.addEventListener('click', function() {
            manualFetch();
        });
    }
    
    // Filter form submission
    const filterForm = document.getElementById('filterForm');
    if (filterForm) {
        filterForm.addEventListener('submit', function(e) {
            e.preventDefault();
            applyFilters();
        });
    }
    
    // Export buttons
    document.getElementById('exportCsvBtn')?.addEventListener('click', exportToCsv);
    document.getElementById('exportPdfBtn')?.addEventListener('click', exportToPdf);
    
    // Delete old tenders button
    document.getElementById('deleteOldBtn')?.addEventListener('click', deleteOldTenders);
    
    // Pagination controls
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('page-link')) {
            e.preventDefault();
            const page = parseInt(e.target.getAttribute('data-page'));
            if (!isNaN(page)) {
                loadTenders(page, currentPerPage, currentFilters, currentSort);
            }
        }
    });
    
    // Sortable table headers
    const sortableHeaders = document.querySelectorAll('.sortable');
    sortableHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const field = this.getAttribute('data-field');
            let order = 'asc';
            if (currentSort.field === field && currentSort.order === 'asc') {
                order = 'desc';
            }
            currentSort = { field, order };
            loadTenders(currentPage, currentPerPage, currentFilters, currentSort);
        });
    });
}

// Load dashboard statistics
function loadDashboardStats() {
    fetch('/metrics')
        .then(response => response.json())
        .then(data => {
            document.getElementById('totalTendersCount').textContent = data.total_tenders || 0;
            document.getElementById('openTendersCount').textContent = data.open_tenders || 0;
            document.getElementById('biharTendersCount').textContent = document.getElementById('biharTendersCount') ? 
                Array.from(document.querySelectorAll('.tender-row[data-state="Bihar"]')).length : 0;
            document.getElementById('jharkhandTendersCount').textContent = document.getElementById('jharkhandTendersCount') ? 
                Array.from(document.querySelectorAll('.tender-row[data-state="Jharkhand"]')).length : 0;
                
            // Update auto-fetch status
            autoFetchEnabled = data.auto_fetch_enabled;
            updateAutoFetchDisplay();
        })
        .catch(error => {
            console.error('Error loading dashboard stats:', error);
        });
}

// Load tenders with pagination, filtering, and sorting
function loadTenders(page = 1, perPage = 25, filters = {}, sort = {}) {
    // Show loading indicator
    showLoadingIndicator();
    
    // Build query parameters
    const params = new URLSearchParams({
        page: page,
        per_page: perPage,
        sort_by: sort.field || 'publish_date',
        sort_order: sort.order || 'desc'
    });
    
    // Add filters to parameters
    Object.keys(filters).forEach(key => {
        if (filters[key]) {
            params.append(key, filters[key]);
        }
    });
    
    // Make API request
    fetch(`/api/tenders?${params}`)
        .then(response => response.json())
        .then(data => {
            renderTenders(data.tenders);
            renderPagination(data.current_page, data.pages, data.per_page);
            updateUrlWithFilters(params.toString());
        })
        .catch(error => {
            console.error('Error loading tenders:', error);
            showError('Failed to load tenders. Please try again.');
        })
        .finally(() => {
            hideLoadingIndicator();
        });
}

// Render tenders in the table
function renderTenders(tenders) {
    const tbody = document.querySelector('#tendersTable tbody');
    if (!tbody) return;
    
    // Clear existing content
    tbody.innerHTML = '';
    
    if (tenders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center py-4">No tenders found matching your criteria.</td></tr>';
        return;
    }
    
    tenders.forEach(tender => {
        const row = document.createElement('tr');
        row.className = 'tender-row';
        row.setAttribute('data-state', tender.state);
        row.setAttribute('data-id', tender.id);
        
        // Format dates
        const publishDate = tender.publish_date ? formatDate(new Date(tender.publish_date)) : 'N/A';
        const deadlineDate = tender.deadline_date ? formatDate(new Date(tender.deadline_date)) : 'N/A';
        
        // Format tender value
        const tenderValue = tender.tender_value ? 
            `₹${parseFloat(tender.tender_value).toLocaleString('en-IN')}` : 'N/A';
        
        // Status badge
        let statusBadge = '<span class="badge badge-open">Open</span>';
        if (tender.status === 'closed') {
            statusBadge = '<span class="badge badge-closed">Closed</span>';
        } else if (tender.status === 'extended') {
            statusBadge = '<span class="badge badge-extended">Extended</span>';
        }
        
        row.innerHTML = `
            <td>
                <input type="checkbox" class="tender-checkbox" data-id="${tender.id}">
            </td>
            <td>
                <a href="/tender/${tender.id}" class="fw-bold">${truncateText(tender.title, 50)}</a>
                <div class="small text-muted mt-1">${tender.source_portal}</div>
            </td>
            <td>${tender.issuing_authority || 'N/A'}</td>
            <td>${tender.department || 'N/A'}</td>
            <td>${tender.category || 'N/A'}</td>
            <td>${tender.location || 'N/A'}</td>
            <td>${tender.state}</td>
            <td>${publishDate}</td>
            <td>${deadlineDate}</td>
            <td class="text-end">${tenderValue}</td>
            <td>${statusBadge}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="showSupplierMatches(${tender.id})" data-bs-toggle="tooltip" title="View supplier matches">
                    <i class="fas fa-handshake"></i>
                </button>
            </td>
        `;
        
        tbody.appendChild(row);
    });
    
    // Re-initialize tooltips for new elements
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}

// Render pagination controls
function renderPagination(currentPage, totalPages, perPage) {
    const paginationContainer = document.getElementById('paginationContainer');
    if (!paginationContainer) return;
    
    if (totalPages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }
    
    let paginationHtml = '<nav aria-label="Tenders pagination"><ul class="pagination justify-content-center">';
    
    // Previous button
    paginationHtml += `<li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
        <a class="page-link" href="#" data-page="${currentPage - 1}" aria-label="Previous">
            <span aria-hidden="true">&laquo;</span>
        </a>
    </li>`;
    
    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    if (startPage > 1) {
        paginationHtml += `<li class="page-item"><a class="page-link" href="#" data-page="1">1</a></li>`;
        if (startPage > 2) {
            paginationHtml += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        paginationHtml += `<li class="page-item ${i === currentPage ? 'active' : ''}">
            <a class="page-link" href="#" data-page="${i}">${i}</a>
        </li>`;
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            paginationHtml += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
        paginationHtml += `<li class="page-item"><a class="page-link" href="#" data-page="${totalPages}">${totalPages}</a></li>`;
    }
    
    // Next button
    paginationHtml += `<li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
        <a class="page-link" href="#" data-page="${currentPage + 1}" aria-label="Next">
            <span aria-hidden="true">&raquo;</span>
        </a>
    </li>`;
    
    paginationHtml += '</ul></nav>';
    
    paginationContainer.innerHTML = paginationHtml;
}

// Apply filters from the form
function applyFilters() {
    const form = document.getElementById('filterForm');
    if (!form) return;
    
    // Collect filter values
    currentFilters = {
        state: form.querySelector('select[name="state"]').value || undefined,
        category: form.querySelector('select[name="category"]').value || undefined,
        status: form.querySelector('select[name="status"]').value || undefined,
        start_date: form.querySelector('input[name="start_date"]').value || undefined,
        end_date: form.querySelector('input[name="end_date"]').value || undefined,
        search: form.querySelector('input[name="search"]').value.trim() || undefined
    };
    
    // Clean up empty filters
    Object.keys(currentFilters).forEach(key => {
        if (!currentFilters[key]) {
            delete currentFilters[key];
        }
    });
    
    // Reset to first page and reload
    currentPage = 1;
    loadTenders(currentPage, currentPerPage, currentFilters, currentSort);
}

// Toggle auto-fetch functionality
function toggleAutoFetch(enabled) {
    fetch('/toggle_auto_fetch', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ enabled: enabled })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'enabled' || data.status === 'disabled') {
            autoFetchEnabled = enabled;
            updateAutoFetchDisplay();
            showToast(`Auto-fetch ${enabled ? 'enabled' : 'disabled'}`, 'success');
        } else {
            showToast('Failed to update auto-fetch status', 'error');
            // Reset toggle to previous state
            document.getElementById('autoFetchToggle').checked = !enabled;
        }
    })
    .catch(error => {
        console.error('Error toggling auto-fetch:', error);
        showToast('Error updating auto-fetch status', 'error');
        // Reset toggle to previous state
        document.getElementById('autoFetchToggle').checked = !enabled;
    });
}

// Update auto-fetch display
function updateAutoFetchDisplay() {
    const toggle = document.getElementById('autoFetchToggle');
    const statusText = document.getElementById('autoFetchStatus');
    
    if (toggle) {
        toggle.checked = autoFetchEnabled;
    }
    
    if (statusText) {
        statusText.textContent = autoFetchEnabled ? 'ON' : 'OFF';
        statusText.className = autoFetchEnabled ? 'text-success fw-bold' : 'text-muted';
    }
}

// Manual fetch
function manualFetch() {
    const btn = document.getElementById('manualFetchBtn');
    const originalText = btn.innerHTML;
    
    // Show loading state
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Fetching...';
    btn.disabled = true;
    
    fetch('/fetch_manual', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({})
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'started') {
            showToast('Fetch operation started', 'success');
        } else {
            showToast('Failed to start fetch operation', 'error');
        }
    })
    .catch(error => {
        console.error('Error starting manual fetch:', error);
        showToast('Error starting fetch operation', 'error');
    })
    .finally(() => {
        // Restore button state
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

// Export to CSV
function exportToCsv() {
    window.location.href = '/export_csv';
    showToast('CSV export started', 'info');
}

// Export to PDF
function exportToPdf() {
    // Get selected tender IDs
    const selectedCheckboxes = document.querySelectorAll('.tender-checkbox:checked');
    const selectedIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.dataset.id));
    
    if (selectedIds.length === 0) {
        showToast('Please select at least one tender to export', 'warning');
        return;
    }
    
    fetch('/export_pdf', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tender_ids: selectedIds })
    })
    .then(response => response.json())
    .then(data => {
        if (data.filename) {
            // Create a temporary link to download the PDF
            const link = document.createElement('a');
            link.href = `/download_pdf/${data.filename}`;
            link.download = `tender_report_${new Date().toISOString().slice(0, 10)}.pdf`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            showToast('PDF export completed', 'success');
        } else {
            showToast('Error exporting PDF: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error exporting to PDF:', error);
        showToast('Error exporting to PDF', 'error');
    });
}

// Delete old tenders
function deleteOldTenders() {
    const days = prompt('Enter number of days (tenders older than this will be deleted):', '90');
    if (days === null) return; // User cancelled
    
    const daysInt = parseInt(days);
    if (isNaN(daysInt) || daysInt <= 0) {
        showToast('Please enter a valid number of days', 'error');
        return;
    }
    
    if (!confirm(`Are you sure you want to delete all tenders older than ${daysInt} days?`)) {
        return;
    }
    
    fetch('/delete_old_tenders', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ days_old: daysInt })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'completed') {
            showToast(`${data.deleted_count} tenders deleted`, 'success');
            // Refresh the current view
            loadTenders(currentPage, currentPerPage, currentFilters, currentSort);
        } else {
            showToast('Error deleting tenders: ' + (data.message || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error deleting old tenders:', error);
        showToast('Error deleting tenders', 'error');
    });
}

// Show supplier matches for a tender
function showSupplierMatches(tenderId) {
    fetch(`/get_supplier_matches/${tenderId}`)
        .then(response => response.json())
        .then(data => {
            if (data && data.length > 0) {
                // Create modal to display matches
                createSupplierMatchesModal(tenderId, data);
            } else {
                showToast('No supplier matches found for this tender', 'info');
            }
        })
        .catch(error => {
            console.error('Error fetching supplier matches:', error);
            showToast('Error fetching supplier matches', 'error');
        });
}

// Create modal for supplier matches
function createSupplierMatchesModal(tenderId, matches) {
    // Remove existing modal if present
    const existingModal = document.getElementById('supplierMatchesModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Create modal HTML
    let matchesHtml = '';
    matches.forEach(match => {
        matchesHtml += `
            <div class="card supplier-match-card mb-3">
                <div class="card-body">
                    <div class="supplier-match-header">
                        <h6 class="supplier-name">${match.name}</h6>
                        <span class="match-score">${match.match_score}% match</span>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <p class="mb-1"><strong>Contact:</strong> ${match.contact_person || 'N/A'}</p>
                            <p class="mb-1"><strong>Email:</strong> ${match.email || 'N/A'}</p>
                            <p class="mb-1"><strong>Phone:</strong> ${match.phone || 'N/A'}</p>
                        </div>
                        <div class="col-md-6">
                            <p class="mb-1"><strong>Experience:</strong> ${match.experience_years || 'N/A'} years</p>
                            <p class="mb-1"><strong>Rating:</strong> ${match.rating || 'N/A'}/5</p>
                            <p class="mb-1"><strong>Verified:</strong> ${match.verified ? 'Yes' : 'No'}</p>
                        </div>
                    </div>
                    <div class="mt-2">
                        <p class="mb-1"><strong>Match Reasons:</strong></p>
                        <ul class="mb-0">
                            ${(match.ai_analysis.relevance_reasons || []).map(reason => `<li>${reason}</li>`).join('')}
                        </ul>
                    </div>
                    <div class="mt-2">
                        <p class="mb-1"><strong>Estimated Price Range:</strong> ₹${(match.ai_analysis.estimated_price_range.min || 0).toLocaleString('en-IN')} - ₹${(match.ai_analysis.estimated_price_range.max || 0).toLocaleString('en-IN')}</p>
                    </div>
                </div>
            </div>
        `;
    });
    
    const modalHtml = `
        <div class="modal fade" id="supplierMatchesModal" tabindex="-1" aria-labelledby="supplierMatchesModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="supplierMatchesModalLabel">Supplier Matches</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        ${matchesHtml}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('supplierMatchesModal'));
    modal.show();
    
    // Remove modal when hidden
    document.getElementById('supplierMatchesModal').addEventListener('hidden.bs.modal', function () {
        this.remove();
    });
}

// Helper functions
function formatDate(date) {
    return date.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

function truncateText(text, maxLength) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

function showLoadingIndicator() {
    const loader = document.getElementById('loadingSpinner');
    if (loader) {
        loader.style.display = 'block';
    }
}

function hideLoadingIndicator() {
    const loader = document.getElementById('loadingSpinner');
    if (loader) {
        loader.style.display = 'none';
    }
}

function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '10000';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast_' + Date.now();
    const toastElement = document.createElement('div');
    toastElement.id = toastId;
    toastElement.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
    toastElement.setAttribute('role', 'alert');
    toastElement.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    toastContainer.appendChild(toastElement);
    
    // Show toast
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
    
    // Remove toast after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

function showError(message) {
    showToast(message, 'error');
}

function updateUrlWithFilters(filters) {
    const url = new URL(window.location);
    url.search = filters;
    window.history.replaceState({}, '', url);
}

// Periodic refresh for dashboard stats
setInterval(loadDashboardStats, 30000); // Refresh every 30 seconds