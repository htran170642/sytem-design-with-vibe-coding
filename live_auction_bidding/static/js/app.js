// Live Auction System - Frontend JavaScript
// Handles dynamic content loading and updates

// API Base URL
const API_BASE = '';

// ============================================================================
// INITIALIZATION
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Live Auction System - Frontend Loaded');
    
    // Load initial data
    loadServerStats();
    loadSystemStats();
    loadAuctions();
    loadMonitoringData();
    
    // Set up auto-refresh (every 5 seconds)
    setInterval(loadServerStats, 5000);
    setInterval(loadSystemStats, 5000);
    setInterval(loadAuctions, 10000);
    setInterval(loadMonitoringData, 5000);
    
    // Set up navigation
    setupNavigation();
});

// ============================================================================
// SERVER STATS
// ============================================================================
async function loadServerStats() {
    try {
        const response = await fetch(`${API_BASE}/`);
        const data = await response.json();
        
        // Update header stats
        document.getElementById('serverStatus').textContent = data.status;
        document.getElementById('serverStatus').style.color = 
            data.status === 'running' ? '#48bb78' : '#f56565';
        
        document.getElementById('activeAuctions').textContent = data.active_auctions;
        document.getElementById('totalBids').textContent = data.total_bids;
        
        // Update system stats
        document.getElementById('queuedBids').textContent = data.queued_bids;
        document.getElementById('dbStatus').textContent = 
            data.database.includes('✅') ? '✅' : '❌';
        document.getElementById('redisStatus').textContent = 
            data.redis.includes('✅') ? '✅' : '❌';
        
    } catch (error) {
        console.error('Error loading server stats:', error);
        document.getElementById('serverStatus').textContent = 'Error';
        document.getElementById('serverStatus').style.color = '#f56565';
    }
}

// ============================================================================
// SYSTEM STATS
// ============================================================================
async function loadSystemStats() {
    try {
        // Load cache stats
        const cacheResponse = await fetch(`${API_BASE}/admin/cache-stats`);
        const cacheData = await cacheResponse.json();
        
        document.getElementById('cacheHitRate').textContent = cacheData.hit_rate;
        
    } catch (error) {
        console.error('Error loading system stats:', error);
    }
}

// ============================================================================
// AUCTIONS
// ============================================================================
async function loadAuctions() {
    try {
        const response = await fetch(`${API_BASE}/auctions?status=ACTIVE`);
        const data = await response.json();
        
        const container = document.getElementById('auctionsList');
        
        if (data.auctions.length === 0) {
            container.innerHTML = `
                <div class="card">
                    <div class="card-body" style="text-align: center; padding: 3rem;">
                        <h3 style="color: var(--gray-600);">No active auctions</h3>
                        <p style="color: var(--gray-500); margin-top: 1rem;">
                            Create an auction using the API or curl commands below
                        </p>
                    </div>
                </div>
            `;
            return;
        }
        
        container.innerHTML = data.auctions.map(auction => `
            <div class="card">
                <div class="card-header">
                    <h3>${auction.title}</h3>
                </div>
                <div class="card-body">
                    <p style="color: var(--gray-600); margin-bottom: 1rem;">
                        ${auction.description}
                    </p>
                    
                    <div class="stats-grid">
                        <div class="stat-box">
                            <div class="stat-box-label">Current Price</div>
                            <div class="stat-box-value">$${auction.current_price.toFixed(2)}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-box-label">Total Bids</div>
                            <div class="stat-box-value">${auction.total_bids}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-box-label">Queued</div>
                            <div class="stat-box-value">${auction.queued_bids}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-box-label">Status</div>
                            <div class="stat-box-value" style="font-size: 1rem;">
                                ${auction.status}
                            </div>
                        </div>
                    </div>
                    
                    ${auction.current_winner_id ? `
                        <div style="margin-top: 1rem; padding: 0.5rem; background: var(--success); color: white; border-radius: var(--radius-md); text-align: center;">
                            🏆 Leading: User ${auction.current_winner_id}
                        </div>
                    ` : ''}
                    
                    <div style="margin-top: 1rem; display: flex; gap: 0.5rem;">
                        <a href="/auctions/${auction.auction_id}" target="_blank" 
                           class="button-primary" style="flex: 1; text-align: center; padding: 0.5rem;">
                            View Details
                        </a>
                        <a href="/docs#/bids/place_bid_async_bids_auctions__auction_id__bids_async_post" 
                           target="_blank" class="button-primary" 
                           style="flex: 1; text-align: center; padding: 0.5rem; background: var(--success);">
                            Place Bid
                        </a>
                    </div>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading auctions:', error);
        document.getElementById('auctionsList').innerHTML = `
            <div class="loading" style="color: #f56565;">
                Error loading auctions
            </div>
        `;
    }
}

// ============================================================================
// MONITORING DATA
// ============================================================================
async function loadMonitoringData() {
    try {
        // Cache Stats
        const cacheResponse = await fetch(`${API_BASE}/admin/cache-stats`);
        const cacheData = await cacheResponse.json();
        document.getElementById('cacheStats').textContent = 
            JSON.stringify(cacheData, null, 2);
        
        // Queue Stats
        const queueResponse = await fetch(`${API_BASE}/admin/queue-stats`);
        const queueData = await queueResponse.json();
        document.getElementById('queueStats').textContent = 
            JSON.stringify(queueData, null, 2);
        
        // Pub/Sub Stats
        const pubsubResponse = await fetch(`${API_BASE}/admin/pubsub-stats`);
        const pubsubData = await pubsubResponse.json();
        document.getElementById('pubsubStats').textContent = 
            JSON.stringify(pubsubData, null, 2);
        
    } catch (error) {
        console.error('Error loading monitoring data:', error);
    }
}

// ============================================================================
// NAVIGATION
// ============================================================================
function setupNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            // Remove active class from all links
            navLinks.forEach(l => l.classList.remove('active'));
            
            // Add active class to clicked link
            link.classList.add('active');
        });
    });
}