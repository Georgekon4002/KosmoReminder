document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const statTotal = document.getElementById('stat-total');
    const statSent = document.getElementById('stat-sent');
    const statDelivered = document.getElementById('stat-delivered');
    const statFailed = document.getElementById('stat-failed');
    const tbody = document.getElementById('messages-tbody');
    const refreshBtn = document.getElementById('refresh-btn');

    // Format Date helper
    const formatDate = (isoString) => {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleString('en-GB', {
            day: '2-digit', month: 'short', 
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
            const res = await fetch('/api/dashboard/stats');
            if (!res.ok) throw new Error('Network response was not ok');
            const data = await res.json();
            
            // Animate number updates (simple direct update for now)
            statTotal.textContent = data.Total || 0;
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
            const res = await fetch('/api/dashboard/messages');
            if (!res.ok) throw new Error('Network response was not ok');
            const data = await res.json();
            
            tbody.innerHTML = ''; // Clear table
            
            if (data.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" class="loading-state">No messages found.</td></tr>`;
                return;
            }

            data.forEach(msg => {
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
                    <td>${msg.Phone || '-'}</td>
                    <td>${msg.ExamType || '-'}</td>
                    <td>${msg.ChannelUsed || 'SMS'}</td>
                    <td><span class="badge ${statusClass}">${statusText}</span></td>
                    <td>${formatDate(msg.SentAt)}</td>
                    <td>${formatCost(msg.Cost)}</td>
                `;
                tbody.appendChild(tr);
            });

        } catch (error) {
            console.error('Error fetching messages:', error);
            tbody.innerHTML = `<tr><td colspan="7" class="loading-state" style="color: var(--accent-red)">Error loading data.</td></tr>`;
        }
    };

    // Main refresh function
    const refreshDashboard = async () => {
        // Add spinning class to button icon
        const icon = refreshBtn.querySelector('i');
        icon.classList.add('spin');
        
        await Promise.all([fetchStats(), fetchMessages()]);
        
        // Remove spinning class after at least 500ms to show it did something
        setTimeout(() => icon.classList.remove('spin'), 500);
    };

    // Event Listeners
    refreshBtn.addEventListener('click', refreshDashboard);

    // Initial load
    refreshDashboard();

    // Auto-refresh every 30 seconds
    setInterval(refreshDashboard, 30000);
});
