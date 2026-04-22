document.addEventListener('DOMContentLoaded', () => {
    const inboxGrid = document.getElementById('inbox-grid');
    const lastSyncTimeEl = document.getElementById('last-sync-time');
    
    async function fetchUpdates() {
        try {
            const response = await fetch('/api/scan');
            if (!response.ok) return;
            
            const data = await response.json();
            const results = data.results || [];
            const db_status = data.db_status || 'unknown';
            const db_error = data.db_error || 'none';
            
            if (lastSyncTimeEl) {
                lastSyncTimeEl.textContent = new Date().toLocaleTimeString();
            }

            if (results.length === 0) {
                inboxGrid.innerHTML = `
                    <div style="text-align: center; padding: 40px; color: #a1a1aa; background: rgba(0,0,0,0.2); border-radius: 15px;">
                        <p style="font-size: 1.2rem; margin-bottom: 10px;">Status: <span style="color: ${db_status === 'connected' ? '#10b981' : '#f43f5e'}">${db_status}</span></p>
                        <p style="font-size: 0.8rem; color: #71717a;">Error: ${db_error}</p>
                        <hr style="margin: 20px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.1);">
                        <a href="/authorize" class="btn-pro" style="padding: 10px 20px; text-decoration: none;">+ Connect Gmail Now</a>
                    </div>
                `;
                return;
            }

            // (Rendering logic for results would go here)
        } catch (err) {
            console.error('Update Loop Failed:', err);
        }
    }

    fetchUpdates();
    setInterval(fetchUpdates, 5000);
});
