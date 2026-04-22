document.addEventListener('DOMContentLoaded', () => {
    const feedContainer = document.getElementById('feed-container');
    const manageBtn = document.getElementById('manage-btn');
    const modal = document.getElementById('manage-modal');
    const closeModal = document.querySelector('.close-modal');
    const accountList = document.getElementById('account-list');

    async function fetchFeed() {
        try {
            const res = await fetch('/api/scan');
            const data = await res.json();
            const results = data.results || [];

            if (results.length === 0) {
                feedContainer.innerHTML = `
                    <div style="text-align: center; padding: 100px; color: #888;">
                        <p style="font-size: 1.2rem;">No accounts connected.</p>
                        <p style="font-size: 0.8rem;">Database Status: ${data.db_status} | Error: ${data.db_error || 'None'}</p>
                        <a href="/authorize" class="btn-primary" style="display:inline-block; margin-top:20px;">Connect Your First Account</a>
                    </div>
                `;
                return;
            }

            let html = '';
            results.forEach(acc => {
                html += `
                    <div class="account-row">
                        <div class="account-info">
                            <img src="https://ssl.gstatic.com/ui/v1/icons/mail/rfr/gmail.ico">
                            <h3>${acc.email}</h3>
                            <p>Google Workspace</p>
                        </div>
                        <div class="email-feed">
                            ${(acc.emails || []).map(e => `
                                <div class="email-box ${e.folder === 'Spam' ? 'is-spam' : 'is-inbox'}">
                                    <div class="sender">${e.from}</div>
                                    <div class="subject">${e.subject}</div>
                                    <div class="status-row">
                                        <span class="label-pill ${e.folder === 'Spam' ? 'pill-spam' : 'pill-inbox'}">
                                            ${e.folder === 'Spam' ? 'Spam' : 'Primary Inbox'}
                                        </span>
                                        <span class="time">${formatDate(e.timestamp)}</span>
                                    </div>
                                </div>
                            `).join('') || '<div class="email-box" style="justify-content:center; color:#999; font-size:0.7rem;">No recent activity</div>'}
                        </div>
                    </div>
                `;
            });
            feedContainer.innerHTML = html;
            renderManageList(results);
        } catch (e) { console.error("Feed Error:", e); }
    }

    function formatDate(timestamp) {
        if (!timestamp) return '';
        const date = new Date(parseInt(timestamp));
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function renderManageList(accounts) {
        accountList.innerHTML = accounts.map(acc => `
            <div class="account-list-item">
                <span>${acc.email}</span>
                <button class="btn-delete" onclick="deleteAccount('${acc.email}')">Remove</button>
            </div>
        `).join('') || '<p style="text-align:center; color:#999; padding:20px;">No accounts to manage</p>';
    }

    window.deleteAccount = async (email) => {
        if (!confirm(`Are you sure you want to remove ${email}?`)) return;
        try {
            await fetch(`/api/delete?email=${email}`, { method: 'DELETE' });
            fetchFeed();
        } catch (e) { alert("Delete failed"); }
    };

    manageBtn.onclick = () => modal.style.display = "block";
    closeModal.onclick = () => modal.style.display = "none";
    window.onclick = (e) => { if (e.target == modal) modal.style.display = "none"; };

    fetchFeed();
    setInterval(fetchFeed, 8000); // Refresh every 8s
});
