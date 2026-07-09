document.addEventListener('DOMContentLoaded', () => {
    // Global functions for manual send actions
    window.sendSms = async function (btn, appointmentIds) {
        btn.disabled = true;
        btn.classList.add('disabled');
        try {
            const res = await fetch('/api/send-sms', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ appointment_ids: appointmentIds })
            });
            if (res.ok) {
                document.getElementById('refresh-btn').click();
            } else {
                alert('Failed to send SMS');
                btn.disabled = false;
                btn.classList.remove('disabled');
            }
        } catch (e) {
            console.error(e);
            alert('Error sending SMS');
            btn.disabled = false;
            btn.classList.remove('disabled');
        }
    };

    window.sendEmail = async function (btn, appointmentIds) {
        btn.disabled = true;
        btn.classList.add('disabled');
        try {
            const res = await fetch('/api/send-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ appointment_ids: appointmentIds })
            });
            if (res.ok) {
                document.getElementById('refresh-btn').click();
            } else {
                alert('Failed to send email');
                btn.disabled = false;
                btn.classList.remove('disabled');
            }
        } catch (e) {
            console.error(e);
            alert('Error sending email');
            btn.disabled = false;
            btn.classList.remove('disabled');
        }
    };

    // ─────────────────────────────────────────
    // DOM Elements
    // ─────────────────────────────────────────
    const statSent      = document.getElementById('stat-sent');
    const statDelivered = document.getElementById('stat-delivered');
    const statFailed    = document.getElementById('stat-failed');
    const statPending   = document.getElementById('stat-pending');
    const tbody         = document.getElementById('messages-tbody');
    const refreshBtn    = document.getElementById('refresh-btn');
    const statsSection  = document.getElementById('stats-section');
    const searchInput   = document.getElementById('search-input');
    const filterTomorrow = document.getElementById('filter-tomorrow');

    let currentMode = 'all-time';
    let currentWeekOffset = 0;
    let allLoadedMessages = [];

    // Pagination DOM
    const paginationControls = document.getElementById('pagination-controls');
    const pagePrev = document.getElementById('page-prev');
    const pageNext = document.getElementById('page-next');
    const pageInfo = document.getElementById('page-info');

    // ─────────────────────────────────────────
    // Custom Dropdown Logic
    // ─────────────────────────────────────────
    function setupDropdown(triggerId, panelId, labelId, onChangeCallback) {
        const trigger = document.getElementById(triggerId);
        const panel   = document.getElementById(panelId);
        const label   = document.getElementById(labelId);
        const checkboxes = panel ? panel.querySelectorAll('input[type="checkbox"]') : [];

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = panel.classList.contains('open');
            document.querySelectorAll('.dropdown-panel.open').forEach(p => p.classList.remove('open'));
            document.querySelectorAll('.dropdown-trigger.open').forEach(t => t.classList.remove('open'));
            if (!isOpen) {
                panel.classList.add('open');
                trigger.classList.add('open');
            }
        });

        checkboxes.forEach(cb => {
            cb.addEventListener('change', () => {
                updateTriggerLabel();
                onChangeCallback();
            });
        });

        function updateTriggerLabel() {
            const checked = Array.from(checkboxes).filter(c => c.checked);
            const existingBadge = trigger.querySelector('.filter-badge');
            if (existingBadge) existingBadge.remove();
            if (checked.length === 0) {
                label.textContent = label.dataset.default || 'All';
                trigger.classList.remove('active-filter');
            } else {
                label.textContent = label.dataset.default || 'All';
                trigger.classList.add('active-filter');
                const badge = document.createElement('span');
                badge.className = 'filter-badge';
                badge.textContent = checked.length;
                trigger.appendChild(badge);
            }
        }

        if (label) label.dataset.default = label.textContent;

        return {
            getValues: () => Array.from(checkboxes).filter(c => c.checked).map(c => c.value),
        };
    }

    document.addEventListener('click', () => {
        document.querySelectorAll('.dropdown-panel.open').forEach(p => p.classList.remove('open'));
        document.querySelectorAll('.dropdown-trigger.open').forEach(t => t.classList.remove('open'));
    });

    const channelFilter = setupDropdown('channel-trigger', 'channel-panel', 'channel-label', () => renderTable());
    const statusFilter  = setupDropdown('status-trigger',  'status-panel',  'status-label',  () => renderTable());

    // ─────────────────────────────────────────
    // Helpers
    // ─────────────────────────────────────────
    const formatDate = (isoString) => {
        if (!isoString) return '-';
        return new Date(isoString).toLocaleString('en-GB', {
            day: '2-digit', month: 'short',
            hour: '2-digit', minute: '2-digit'
        });
    };

    const formatDateOnly = (isoString) => {
        if (!isoString) return '-';
        return new Date(isoString).toLocaleString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric'
        });
    };

    const formatTimeOnly = (isoString) => {
        if (!isoString) return '-';
        return new Date(isoString).toLocaleString('en-GB', {
            hour: '2-digit', minute: '2-digit'
        });
    };

    // Strip quoted-printable = artifact and trim
    const cleanEmail = (raw) => {
        if (!raw) return '';
        return raw.replace(/^=+/, '').trim();
    };

    // ─────────────────────────────────────────
    // Greek-aware normalisation
    // Strips Greek tonos/dialytika accents so "καβάλη" matches "ΚΑΒΑΛΗ"
    // ─────────────────────────────────────────
    const GREEK_ACCENT_MAP = {
        'ά': 'α', 'έ': 'ε', 'ή': 'η', 'ί': 'ι', 'ό': 'ο', 'ύ': 'υ', 'ώ': 'ω',
        'ϊ': 'ι', 'ϋ': 'υ', 'ΐ': 'ι', 'ΰ': 'υ',
        'Ά': 'α', 'Έ': 'ε', 'Ή': 'η', 'Ί': 'ι', 'Ό': 'ο', 'Ύ': 'υ', 'Ώ': 'ω',
        'Ϊ': 'ι', 'Ϋ': 'υ',
    };

    const normalise = (str) => {
        if (!str) return '';
        return str
            .toLowerCase()
            // Normalise standard unicode accents (covers Latin letters)
            .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            // Manually strip Greek tonos (not covered by NFD for some Greek chars)
            .replace(/[άέήίόύώϊϋΐΰΆΈΉΊΌΎΏΪΫ]/g, ch => GREEK_ACCENT_MAP[ch] || ch);
    };

    // ─────────────────────────────────────────
    // Multi-format date search
    // Parses a Date object into multiple locale strings so users can search
    // in English or Greek, in different formats.
    // ─────────────────────────────────────────
    const buildDateSearchBlob = (isoString) => {
        if (!isoString) return '';
        const d = new Date(isoString);
        const day   = d.getDate();
        const month = d.getMonth() + 1;
        const year  = d.getFullYear();
        const dd    = String(day).padStart(2, '0');
        const mm    = String(month).padStart(2, '0');

        const variants = [
            // "8 Jul 2026" / "08 Jul 2026"
            d.toLocaleDateString('en-GB', { day: 'numeric',  month: 'short', year: 'numeric' }),
            d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
            // "8 July 2026" / "July 8"
            d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }),
            d.toLocaleDateString('en-US', { month: 'long', day: 'numeric' }),
            // "08/07/2026" / "8/7"
            d.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' }),
            d.toLocaleDateString('en-GB', { day: 'numeric', month: 'numeric' }),
            // Greek: "8 Ιουλίου 2026" / "8 Ιουλ"
            d.toLocaleDateString('el-GR', { day: 'numeric', month: 'long',  year: 'numeric' }),
            d.toLocaleDateString('el-GR', { day: 'numeric', month: 'short' }),
            // ISO: "2026-07-08"
            d.toISOString().slice(0, 10),
            // Dash-separated: "8-7", "08-07", "8-7-2026", "08-07-2026"
            `${day}-${month}`,
            `${dd}-${mm}`,
            `${day}-${month}-${year}`,
            `${dd}-${mm}-${year}`,
            // Raw numbers for partial matching
            String(day), dd, String(month), mm, String(year),
        ];
        return variants.join(' ');
    };

    // ─────────────────────────────────────────
    // Smart Search: AND token matching with normalisation
    // ─────────────────────────────────────────
    const matchesSearch = (msg, query) => {
        if (!query || !query.trim()) return true;

        const nameBlob     = normalise(`${msg.FirstName || ''} ${msg.LastName || ''}`);
        const dept         = normalise(msg.Department || '');
        const phone        = (msg.Phone || '').replace(/\s+/g, '');
        const email        = normalise(cleanEmail(msg.EmailAddress || ''));
        const channel      = normalise(msg.ChannelUsed || '');
        const smsStatus    = normalise(msg.Status || '');
        const emailStatus  = normalise(msg.EmailStatus || '');
        const dateBlob     = normalise(buildDateSearchBlob(msg.AppointmentDateTime));

        const blob = `${nameBlob} ${dept} ${phone} ${email} ${channel} ${smsStatus} ${emailStatus} ${dateBlob}`;

        // AND logic: every token must appear somewhere
        const tokens = normalise(query).trim().split(/\s+/).filter(Boolean);
        return tokens.every(token => blob.includes(token));
    };

    // ─────────────────────────────────────────
    // Render Table
    // ─────────────────────────────────────────
    const renderTable = () => {
        const query         = searchInput.value;
        const activeChannels = channelFilter.getValues();
        const activeStatuses = statusFilter.getValues();

        let filteredData = allLoadedMessages.filter(msg => {
            if (!matchesSearch(msg, query)) return false;

            if (activeChannels.length > 0 && !activeChannels.includes(msg.ChannelUsed)) return false;

            if (activeStatuses.length > 0) {
                const s = (msg.Status || 'Pending').toLowerCase();
                const e = (msg.EmailStatus || 'no_email').toLowerCase();
                const matchesAny = activeStatuses.some(statusVal => {
                    switch (statusVal) {
                        case 'sent_mail':     return e === 'sent';
                        case 'pending_mail':  return e === 'pending' || e === 'no_email';
                        case 'failed_mail':   return e === 'failed';
                        case 'sent_sms':      return s === 'sent';
                        case 'delivered_sms': return s === 'delivered';
                        case 'pending_sms':   return s === 'pending';
                        case 'failed_sms':    return s === 'failed' || s === 'rejected' || s === 'expired';
                        default: return false;
                    }
                });
                if (!matchesAny) return false;
            }
            return true;
        });

        tbody.innerHTML = '';

        if (filteredData.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="loading-state">No messages found matching criteria.</td></tr>`;
            return;
        }

        filteredData.sort((a, b) => {
            const dA = a.AppointmentDateTime ? new Date(a.AppointmentDateTime).getTime() : 0;
            const dB = b.AppointmentDateTime ? new Date(b.AppointmentDateTime).getTime() : 0;
            return dB - dA;
        });

        let currentApptGroup = null;

        filteredData.forEach(msg => {
            const apptDateOnly = formatDateOnly(msg.AppointmentDateTime);
            const apptTimeOnly = formatTimeOnly(msg.AppointmentDateTime);

            if (currentApptGroup !== apptDateOnly) {
                currentApptGroup = apptDateOnly;
                const groupTr = document.createElement('tr');
                groupTr.className = 'group-header';
                groupTr.innerHTML = `<td colspan="8" style="background-color: rgba(255,255,255,0.05); font-weight: 600; padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.06); color: var(--text-main);"><i class="ph ph-calendar-blank" style="vertical-align:middle; margin-right:8px;"></i>${apptDateOnly === '-' ? 'No Appointment Date' : apptDateOnly}</td>`;
                tbody.appendChild(groupTr);
            }

            const tr = document.createElement('tr');
            const fullName = `${msg.FirstName || 'Unknown'} ${msg.LastName || ''}`.trim();

            // Email Status Badge
            const emailStatus = msg.EmailStatus;
            let emailBadge = '-';
            let showEmailButton = false;
            if (emailStatus === 'sent') {
                emailBadge = `<span class="badge status-sent">Sent</span>`;
            } else if (emailStatus === 'failed') {
                emailBadge = `<span class="badge status-failed">Failed</span>`;
                showEmailButton = true;
            } else if (emailStatus === 'no_email') {
                emailBadge = `<span class="badge" style="background:rgba(255,255,255,0.05); color:var(--text-muted)">No Email</span>`;
            } else {
                emailBadge = `<span class="badge status-pending">Pending</span>`;
                showEmailButton = true;
            }
            if (showEmailButton && msg.AppointmentIDs) {
                emailBadge += ` <button class="btn-action-round btn-email" title="Send Email Manually" onclick="sendEmail(this, '${msg.AppointmentIDs}')">📨</button>`;
            }

            // SMS Status Badge
            const statusClass = msg.Status ? `status-${msg.Status.toLowerCase()}` : 'status-pending';
            let statusBadge = `<span class="badge ${statusClass}">${msg.Status || 'Unknown'}</span>`;
            const s = (msg.Status || 'Pending').toLowerCase();
            if ((s === 'failed' || s === 'pending' || s === 'rejected') && msg.AppointmentIDs) {
                statusBadge += ` <button class="btn-action-round btn-sms" title="Send SMS/Viber Manually" onclick="sendSms(this, '${msg.AppointmentIDs}')">💬</button>`;
            }

            const emailAddr = cleanEmail(msg.EmailAddress || '');

            tr.innerHTML = `
                <td>
                    <div class="patient-cell">
                        <span class="patient-name">${fullName}</span>
                        <span class="patient-dept">${msg.Department || 'N/A'}</span>
                    </div>
                </td>
                <td>${apptTimeOnly}</td>
                <td class="col-sep-left">${msg.Phone || '-'}</td>
                <td>${statusBadge}</td>
                <td>${msg.ChannelUsed || 'SMS'}</td>
                <td>${formatDate(msg.SentAt)}</td>
                <td class="col-sep-left">${emailAddr || '-'}</td>
                <td>${emailBadge}</td>
            `;
            tbody.appendChild(tr);
        });
    };

    // ─────────────────────────────────────────
    // Fetch Stats
    // ─────────────────────────────────────────
    const fetchStats = async () => {
        try {
            const res = await fetch(`/api/dashboard/stats?mode=${currentMode}`);
            if (!res.ok) throw new Error('Network response was not ok');
            const data = await res.json();

            statSent.textContent      = data.Sent      || 0;
            statDelivered.textContent = data.Delivered || 0;
            statFailed.textContent    = data.Failed    || 0;
            statPending.textContent   = data.Pending   || 0;
        } catch (error) {
            console.error('Error fetching stats:', error);
        }
    };

    // ─────────────────────────────────────────
    // Fetch Messages
    // ─────────────────────────────────────────
    const fetchMessages = async () => {
        try {
            const url = currentMode === 'today'
                ? `/api/dashboard/messages?mode=today`
                : `/api/dashboard/messages?mode=all-time&weekOffset=${currentWeekOffset}`;

            const res = await fetch(url);
            if (!res.ok) throw new Error('Network response was not ok');
            const responseData = await res.json();

            allLoadedMessages = responseData.messages || [];

            if (currentMode === 'today') {
                paginationControls.style.display = 'none';
            } else {
                const pagination = responseData.pagination || {};
                paginationControls.style.display = 'flex';
                if (pagination.startDate && pagination.endDate) {
                    const fwd = (ds) => new Date(ds).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    pageInfo.textContent = `${fwd(pagination.startDate)} - ${fwd(pagination.endDate)}`;
                } else {
                    pageInfo.textContent = `Week ${currentWeekOffset}`;
                }
                pagePrev.disabled = false;
                pageNext.disabled = false;
            }

            renderTable();
        } catch (error) {
            console.error('Error fetching messages:', error);
            tbody.innerHTML = `<tr><td colspan="8" class="loading-state" style="color: var(--accent-red)">Error loading data.</td></tr>`;
        }
    };

    // ─────────────────────────────────────────
    // Refresh (silent = true skips table clear for auto-refresh)
    // ─────────────────────────────────────────
    const refreshDashboard = async (silent = false) => {
        statsSection.style.display = 'grid';
        const icon = refreshBtn.querySelector('i');
        icon.classList.add('spin');

        if (!silent) {
            tbody.innerHTML = `<tr><td colspan="8" class="loading-state"><i class="ph ph-spinner-gap spin"></i> Loading data...</td></tr>`;
        }

        await Promise.all([fetchStats(), fetchMessages()]);
        setTimeout(() => icon.classList.remove('spin'), 500);
    };

    // ─────────────────────────────────────────
    // Event Listeners
    // ─────────────────────────────────────────
    refreshBtn.addEventListener('click', () => refreshDashboard(false));

    pagePrev.addEventListener('click', () => {
        if (currentMode !== 'today') { currentWeekOffset--; refreshDashboard(false); }
    });
    pageNext.addEventListener('click', () => {
        if (currentMode !== 'today') { currentWeekOffset++; refreshDashboard(false); }
    });

    searchInput.addEventListener('input', renderTable);

    filterTomorrow.addEventListener('change', (e) => {
        currentMode = e.target.checked ? 'today' : 'all-time';
        currentWeekOffset = 0;
        refreshDashboard(false);
    });

    // ─────────────────────────────────────────
    // Initial load + silent auto-refresh
    // ─────────────────────────────────────────
    refreshDashboard(false);
    setInterval(() => refreshDashboard(true), 30000);
});
