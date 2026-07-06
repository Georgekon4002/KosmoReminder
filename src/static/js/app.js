document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const statTotal = document.getElementById('stat-total');
    const statSent = document.getElementById('stat-sent');
    const statDelivered = document.getElementById('stat-delivered');
    const statFailed = document.getElementById('stat-failed');
    const tbody = document.getElementById('messages-tbody');
    const refreshBtn = document.getElementById('refresh-btn');
    const statsSection = document.getElementById('stats-section');
    const tabBtns = document.querySelectorAll('.tab-btn');

    let currentMode = 'all-time';

    // Format Date helper
    const formatDate = (isoString) => {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleString('en-GB', {
            day: '2-digit', month: 'short', 
            hour: '2-digit', minute: '2-digit'
        });
    };

    const formatDateOnly = (isoString) => {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric'
        });
    };

    const formatTimeOnly = (isoString) => {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleString('en-GB', {
            hour: '2-digit', minute: '2-digit'
        });
    };

    // Format Cost helper
    const formatCost = (cost) => {
        if (cost === null || cost === undefined) return '-';
        return `€${parseFloat(cost).toFixed(3)}`;
    };

    // Fetch and update stats
    const fetchStats = async () => {
        try {
            const res = await fetch(`/api/dashboard/stats?mode=${currentMode}`);
            if (!res.ok) throw new Error('Network response was not ok');
            const data = await res.json();
            
            // Animate number updates (simple direct update for now)
            if (currentMode === 'today') {
                document.getElementById('stat-total-title').textContent = 'Pending';
                statTotal.textContent = data.Pending || 0;
            } else {
                document.getElementById('stat-total-title').textContent = 'Total Processed';
                statTotal.textContent = (data.Sent || 0) + (data.Delivered || 0) + (data.Failed || 0) + (data.Pending || 0);
            }
            statSent.textContent = data.Sent || 0;
            statDelivered.textContent = data.Delivered || 0;
            statFailed.textContent = data.Failed || 0;
        } catch (error) {
            console.error('Error fetching stats:', error);
        }
    };

    // Fetch and update table
    const fetchMessages = async () => {
        try {
            const res = await fetch(`/api/dashboard/messages?mode=${currentMode}`);
            if (!res.ok) throw new Error('Network response was not ok');
            const data = await res.json();
            
            tbody.innerHTML = ''; // Clear table
            
            if (data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="loading-state">No messages found.</td></tr>`;
                return;
            }

            // Group by AppointmentDateTime
            data.sort((a, b) => {
                const dateA = a.AppointmentDateTime ? new Date(a.AppointmentDateTime).getTime() : 0;
                const dateB = b.AppointmentDateTime ? new Date(b.AppointmentDateTime).getTime() : 0;
                return dateB - dateA;
            });

            let currentApptGroup = null;

            data.forEach(msg => {
                const apptDateOnly = formatDateOnly(msg.AppointmentDateTime);
                const apptTimeOnly = formatTimeOnly(msg.AppointmentDateTime);

                if (currentApptGroup !== apptDateOnly) {
                    currentApptGroup = apptDateOnly;
                    const groupTr = document.createElement('tr');
                    groupTr.className = 'group-header';
                    groupTr.innerHTML = `<td colspan="6" style="background-color: rgba(255, 255, 255, 0.05); font-weight: 600; padding: 12px 16px; border-bottom: 1px solid var(--glass-border); color: var(--text-main);"><i class="ph ph-calendar-blank" style="vertical-align: middle; margin-right: 8px;"></i>${apptDateOnly === '-' ? 'No Appointment Date' : apptDateOnly}</td>`;
                    tbody.appendChild(groupTr);
                }

                const tr = document.createElement('tr');
                
                // Patient Name fallback
                const firstName = msg.FirstName || 'Unknown';
                const lastName = msg.LastName || '';
                const fullName = `${firstName} ${lastName}`.trim();
                
                // Status Badge
                const statusClass = msg.Status ? `status-${msg.Status.toLowerCase()}` : 'status-pending';
                const statusText = msg.Status || 'Unknown';

                tr.innerHTML = `
                    <td>
                        <div class="patient-cell">
                            <span class="patient-name">${fullName}</span>
                            <span class="patient-dept">${msg.Department || 'N/A'}</span>
                        </div>
                    </td>
                    <td>${apptTimeOnly}</td>
                    <td>${msg.Phone || '-'}</td>
                    <td>${msg.ChannelUsed || 'SMS'}</td>
                    <td><span class="badge ${statusClass}">${statusText}</span></td>
                    <td>${formatDate(msg.SentAt)}</td>
                `;
                tbody.appendChild(tr);
            });

        } catch (error) {
            console.error('Error fetching messages:', error);
            tbody.innerHTML = `<tr><td colspan="6" class="loading-state" style="color: var(--accent-red)">Error loading data.</td></tr>`;
        }
    };

    // Main refresh function
    const refreshDashboard = async () => {
        // Always show stats grid
        statsSection.style.display = 'grid';

        // Add spinning class to button icon
        const icon = refreshBtn.querySelector('i');
        icon.classList.add('spin');
        
        await Promise.all([fetchStats(), fetchMessages()]);
        
        // Remove spinning class after at least 500ms to show it did something
        setTimeout(() => icon.classList.remove('spin'), 500);
    };

    // Event Listeners
    refreshBtn.addEventListener('click', refreshDashboard);

    tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Update active state
            tabBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            // Update mode and fetch
            currentMode = e.target.getAttribute('data-mode');
            
            // Show loading state immediately
            tbody.innerHTML = `<tr><td colspan="6" class="loading-state"><i class="ph ph-spinner-gap spin"></i> Loading data...</td></tr>`;
            
            refreshDashboard();
        });
    });

    // Initial load
    refreshDashboard();

    // Auto-refresh every 30 seconds
    setInterval(refreshDashboard, 30000);
});
