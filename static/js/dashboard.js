document.addEventListener('DOMContentLoaded', () => {
    const inboxGrid = document.getElementById('inbox-grid');
    const lastSyncTimeEl = document.getElementById('last-sync-time');
    const refreshBtn = document.getElementById('refresh-btn');
    const totalAccountsEl = document.getElementById('total-accounts');
    
    // Safety check for the refresh button
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            const icon = document.getElementById('refresh-icon');
            if (icon) {
                icon.style.transition = 'transform 0.5s ease';
                icon.style.transform = 'rotate(360deg)';
                setTimeout(() => { icon.style.transform = 'rotate(0deg)'; }, 500);
            }
            fetchUpdates();
        });
    }

    async function fetchUpdates() {
        try {
            console.log("Fetching updates...");
            const response = await fetch('/api/scan');
            if (!response.ok) {
                console.error('API Offline or Unauthorized');
                return;
            }
            
            const data = await response.json();
            const results = data.results || [];
            const db_status = data.db_status || 'unknown';
            
            console.log("DB Status:", db_status);
            if (lastSyncTimeEl) {
                lastSyncTimeEl.textContent = new Date().toLocaleTimeString();
            }

            if (results.length === 0) {
                inboxGrid.innerHTML = `
                    <div style="text-align: center; padding: 60px; color: #a1a1aa; background: rgba(255,255,255,0.05); border-radius: 20px; border: 1px dashed rgba(255,255,255,0.1);">
                        <p style="font-size: 1.2rem; margin-bottom: 10px;">No accounts found.</p>
                        <p style="font-size: 0.9rem; margin-bottom: 20px;">Database Status: <span style="color: ${db_status === 'connected' ? '#10b981' : '#f43f5e'}">${db_status}</span></p>
                        <a href="/authorize" class="btn-pro" style="padding: 10px 20px; text-decoration: none;">+ Connect Gmail Now</a>
                    </div>
                `;
                if (totalAccountsEl) totalAccountsEl.textContent = '0';
                return;
            }

            if (totalAccountsEl) totalAccountsEl.textContent = results.length;

            // Render cards
            let html = '';
            results.forEach(acc => {
                const inboxCount = acc.emails.filter(e => e.folder === 'Inbox').length;
                const spamCount = acc.emails.filter(e => e.folder === 'Spam').length;
                const rate = acc.emails.length > 0 ? Math.round((inboxCount / acc.emails.length) * 100) : 0;
                
                html += `
                    <div class="modern-card" style="margin-bottom: 20px; padding: 25px;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div>
                                <h3 style="margin-bottom: 5px;">${acc.email}</h3>
                                <span class="badge ${acc.status === 'online' ? 'online' : 'error'}">${acc.status}</span>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 1.5rem; font-weight: bold; color: ${rate > 80 ? '#10b981' : '#f59e0b'}">${rate}%</div>
                                <div style="font-size: 0.7rem; color: #71717a;">INBOX RATE</div>
                            </div>
                        </div>
                        
                        <div style="margin-top: 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                            <div style="background: rgba(16, 185, 129, 0.1); padding: 10px; border-radius: 10px; text-align: center;">
                                <div style="font-size: 0.7rem; color: #10b981;">INBOX</div>
                                <div style="font-size: 1.1rem; font-weight: bold;">${inboxCount}</div>
                            </div>
                            <div style="background: rgba(244, 63, 94, 0.1); padding: 10px; border-radius: 10px; text-align: center;">
                                <div style="font-size: 0.7rem; color: #f43f5e;">SPAM</div>
                                <div style="font-size: 1.1rem; font-weight: bold;">${spamCount}</div>
                            </div>
                        </div>

                        <div style="margin-top: 20px;">
                            <div style="font-size: 0.8rem; color: #a1a1aa; margin-bottom: 10px;">Recent Activity</div>
                            ${acc.emails.length > 0 ? acc.emails.slice(0, 3).map(e => `
                                <div style="display: flex; justify-content: space-between; padding: 8px 0; border-top: 1px solid rgba(255,255,255,0.05); font-size: 0.8rem;">
                                    <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px;">${e.subject}</span>
                                    <span style="color: ${e.folder === 'Spam' ? '#f43f5e' : '#10b981'}">${e.folder}</span>
                                </div>
                            `).join('') : '<p style="font-size: 0.7rem; color: #71717a;">No recent emails found.</p>'}
                        </div>
                    </div>
                `;
            });
            inboxGrid.innerHTML = html;

        } catch (err) {
            console.error('Update Loop Failed:', err);
        }
    }

    // Start polling
    fetchUpdates();
    setInterval(fetchUpdates, 5000);
});
