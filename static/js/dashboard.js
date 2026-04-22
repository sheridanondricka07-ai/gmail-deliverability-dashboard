document.addEventListener('DOMContentLoaded', () => {
    const inboxGrid = document.getElementById('inbox-grid');
    const cardTemplate = document.getElementById('pro-card-template');
    const itemTemplate = document.getElementById('pro-item-template');
    
    // Global Stat Elements
    const totalAccountsEl = document.getElementById('total-accounts');
    const primaryRateEl = document.getElementById('primary-rate');
    const spamRateEl = document.getElementById('spam-rate');
    const lastSyncTimeEl = document.getElementById('last-sync-time');

    async function fetchUpdates() {
        try {
            const response = await fetch('/api/scan');
            if (!response.ok) throw new Error('Unauthorized or Offline');
            const data = await response.json();
            
            lastSyncTimeEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

            if (data.length === 0) {
                inboxGrid.innerHTML = `
                    <div class="loading-state">
                        <p style="color: var(--text-muted)">No active boites. Add an account to begin monitoring.</p>
                    </div>
                `;
                updateGlobalStats(0, 0, 0);
                return;
            }

            // Remove loading spinner
            const loading = inboxGrid.querySelector('.loading-state');
            if (loading) loading.remove();

            let totalInbox = 0;
            let totalSpam = 0;
            let totalProcessed = 0;

            data.forEach(account => {
                let card = document.querySelector(`[data-email="${account.email}"]`);
                
                if (!card) {
                    const clone = cardTemplate.content.cloneNode(true);
                    card = clone.querySelector('.modern-card');
                    card.setAttribute('data-email', account.email);
                    card.querySelector('.acc-email').textContent = account.email;
                    inboxGrid.appendChild(clone);
                    card = document.querySelector(`[data-email="${account.email}"]`);
                }

                // Calculate Placement Gauge
                const inboxCount = account.emails.filter(e => e.folder === 'Inbox').length;
                const spamCount = account.emails.filter(e => e.folder === 'Spam').length;
                const total = account.emails.length;
                const rate = total > 0 ? Math.round((inboxCount / total) * 100) : 0;
                
                card.querySelector('.gauge-circle').textContent = `${rate}%`;
                card.querySelector('.gauge-circle').style.color = rate > 80 ? 'var(--accent-emerald)' : (rate > 50 ? 'var(--accent-amber)' : 'var(--accent-rose)');

                totalInbox += inboxCount;
                totalSpam += spamCount;
                totalProcessed += total;

                // Update Feed
                const emailList = card.querySelector('.item-list');
                const currentIds = new Set(Array.from(emailList.querySelectorAll('.pro-list-item')).map(e => e.getAttribute('data-id')));
                
                account.emails.reverse().forEach(email => {
                    if (!currentIds.has(email.id)) {
                        const itemClone = itemTemplate.content.cloneNode(true);
                        const item = itemClone.querySelector('.pro-list-item');
                        item.setAttribute('data-id', email.id);
                        item.setAttribute('data-ts', email.timestamp);
                        
                        item.querySelector('.p-name').textContent = email.from.split('<')[0].trim() || 'Internal User';
                        item.querySelector('.p-mail').textContent = email.from;
                        item.querySelector('.p-subject').textContent = email.subject || '(No Subject)';
                        
                        const badge = item.querySelector('.p-status-badge');
                        badge.textContent = email.folder;
                        badge.className = `p-status-badge ${email.folder.toLowerCase()}`;
                        
                        emailList.prepend(itemClone);
                    }
                });

                // Clean up list
                const items = emailList.querySelectorAll('.pro-list-item');
                if (items.length > 20) {
                    for (let i = 20; i < items.length; i++) items[i].remove();
                }
            });

            updateGlobalStats(data.length, totalInbox, totalProcessed);
            updateTimers();

        } catch (err) {
            console.error('Scan error:', err);
        }
    }

    function updateGlobalStats(count, inbox, total) {
        totalAccountsEl.textContent = count;
        const rate = total > 0 ? Math.round((inbox / total) * 100) : 0;
        primaryRateEl.textContent = `${rate}%`;
        spamRateEl.textContent = `${100 - rate}%`;
    }

    function updateTimers() {
        const now = Date.now();
        document.querySelectorAll('.pro-list-item').forEach(item => {
            const ts = parseInt(item.getAttribute('data-ts'));
            const diff = Math.floor((now - ts) / 1000);
            
            let str = 'Just now';
            if (diff > 0) {
                if (diff < 60) str = `${diff}s ago`;
                else if (diff < 3600) str = `${Math.floor(diff/60)}m ago`;
                else str = `${Math.floor(diff/3600)}h ago`;
            }
            item.querySelector('.p-time').textContent = str;
        });
    }

    // Init
    fetchUpdates();
    setInterval(fetchUpdates, 3000);
    setInterval(updateTimers, 1000);
});
