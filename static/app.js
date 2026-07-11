document.addEventListener('DOMContentLoaded', () => {
    // Tabs
    const tabUploadBtn = document.getElementById('tabUploadBtn');
    const tabPasteBtn = document.getElementById('tabPasteBtn');
    const tabUpload = document.getElementById('tabUpload');
    const tabPaste = document.getElementById('tabPaste');
    
    // File Upload Elements
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    
    // Paste Elements
    const pasteInput = document.getElementById('pasteInput');
    
    // Action Elements
    const summarizeBtn = document.getElementById('summarizeBtn');
    const uploadSection = document.getElementById('uploadSection');
    const resultSection = document.getElementById('resultSection');
    const loadingState = document.getElementById('loadingState');
    const summaryContent = document.getElementById('summaryContent');
    const summaryText = document.getElementById('summaryText');
    const resetBtn = document.getElementById('resetBtn');
    const statsChartCtx = document.getElementById('statsChart');
    const mediaStatsContainer = document.getElementById('mediaStatsContainer');
    const stickerCount = document.getElementById('stickerCount');
    const gifCount = document.getElementById('gifCount');
    const topEmojis = document.getElementById('topEmojis');
    
    // New Elements
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const exportPdfBtn = document.getElementById('exportPdfBtn');
    const exportExcelBtn = document.getElementById('exportExcelBtn');
    const pdfCaptureArea = document.getElementById('pdfCaptureArea');
    
    // Chat Widget
    const chatWidget = document.getElementById('chatWidget');
    const chatHistory = document.getElementById('chatHistory');
    const chatInput = document.getElementById('chatInput');
    const sendChatBtn = document.getElementById('sendChatBtn');
    const dateFrom = document.getElementById('dateFrom');
    const dateTo = document.getElementById('dateTo');
    const profilesContainer = document.getElementById('profilesContainer');
    const profilesText = document.getElementById('profilesText');
    const exportChatPdfBtn = document.getElementById('exportChatPdfBtn');
    const expandChatBtn = document.getElementById('expandChatBtn');
    let currentChatId = null;

    let currentFile = null;
    let chartInstance = null;
    let activeMode = 'upload'; // 'upload' or 'paste'
    let loaderInterval = null;
    
    // Global data for exports
    let globalStats = null;
    let globalFilteredStats = null;
    let globalTimeSeries = null;
    let globalMediaStats = null;
    let globalEmojis = null;
    let globalLinks = null;

    // Tab Switching Logic
    tabUploadBtn.addEventListener('click', () => {
        activeMode = 'upload';
        tabUploadBtn.classList.add('active');
        tabPasteBtn.classList.remove('active');
        tabUpload.classList.add('active-tab');
        tabPaste.classList.remove('active-tab');
        validateInput();
    });

    tabPasteBtn.addEventListener('click', () => {
        activeMode = 'paste';
        tabPasteBtn.classList.add('active');
        tabUploadBtn.classList.remove('active');
        tabPaste.classList.add('active-tab');
        tabUpload.classList.remove('active-tab');
        validateInput();
    });

    // File Drag and Drop Handlers
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleFile(e.target.files[0]);
        }
    });
    
    pasteInput.addEventListener('input', () => {
        validateInput();
    });

    function validateInput() {
        if (activeMode === 'upload') {
            summarizeBtn.disabled = !currentFile;
        } else {
            summarizeBtn.disabled = pasteInput.value.trim().length === 0;
        }
    }

    // Handle the uploaded text file or zip file
    function handleFile(file) {
        const validTypes = ['text/plain', 'application/zip', 'application/x-zip-compressed', 'application/pdf'];
        const validExts = ['.txt', '.zip', '.pdf'];
        const isValid = validTypes.includes(file.type) || validExts.some(ext => file.name.toLowerCase().endsWith(ext));
        
        if (!isValid) {
            alert('Please upload a .txt, .zip, or .pdf file');
            return;
        }

        if (file.size > 100 * 1024 * 1024) {
            alert('File exceeds the 100MB maximum limit.');
            return;
        }

        currentFile = file;
        dropZone.querySelector('h3').textContent = file.name;
        dropZone.querySelector('p').textContent = 'File ready to process';
        validateInput();
    }

    // Call Backend API
    summarizeBtn.addEventListener('click', async () => {
        // Transition UI
        uploadSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
        loadingState.classList.remove('hidden');
        summaryContent.classList.add('hidden');
        
        // Progress Loader Logic
        let progress = 0;
        progressFill.style.width = '0%';
        progressText.textContent = '0%';
        
        if (loaderInterval) clearInterval(loaderInterval);
        loaderInterval = setInterval(() => {
            if (progress < 30) {
                progress += 5; // Fast initial upload
            } else if (progress < 90) {
                progress += 1; // Slow AI processing
            }
            progressFill.style.width = `${progress}%`;
            progressText.textContent = `${progress}%`;
        }, 300);

        const formData = new FormData();
        const summaryTypeSelect = document.getElementById('summaryType');
        if (summaryTypeSelect) {
            formData.append('summary_type', summaryTypeSelect.value);
        }
        
        if (activeMode === 'upload') {
            formData.append('file', currentFile);
        } else {
            formData.append('raw_text', pasteInput.value);
        }

        try {
            const apiUrl = (window.TOOL_CONFIG && window.TOOL_CONFIG.apiEndpoint) || '/api/summarize';
            
            // 1. Kick off concurrent requests
            const statsPromise = fetch(apiUrl + '/stats', {
                method: 'POST',
                body: formData
            }).then(async res => {
                const json = await res.json();
                if (!res.ok) throw new Error(json.error || 'Stats Error');
                return json;
            }).catch(e => {
                console.warn("Fast stats failed:", e);
                return null;
            });

            const aiPromise = fetch(apiUrl, {
                method: 'POST',
                body: formData
            }).then(async res => {
                const json = await res.json();
                if (!res.ok) throw new Error(json.error || 'Server Error');
                return json;
            });

            // 2. Await Fast Stats and Render
            const statsData = await statsPromise;
            const toolName = window.TOOL_CONFIG ? window.TOOL_CONFIG.name : 'summarize';

            if (statsData && !statsData.error) {
                globalStats = statsData.stats;
                globalTimeSeries = statsData.time_series;
                globalFilteredStats = statsData.stats;
                globalMediaStats = statsData.media;
                globalEmojis = statsData.emojis;
                globalLinks = statsData.links;
                
                loadingState.classList.add('hidden');
                
                if (toolName === 'statistics') {
                    document.getElementById('analyticsGrid').style.display = 'flex';
                    renderAnalyticsDashboard(statsData);
                    clearInterval(loaderInterval);
                } else if (toolName !== 'search') {
                    const dashboardEl = document.querySelector('.dashboard');
                    if(dashboardEl) dashboardEl.style.display = 'flex';
                    
                    const sumCont = document.getElementById('summaryContent');
                    if(sumCont) sumCont.classList.remove('hidden');
                    
                    summaryText.innerHTML = '<div style="text-align:center; padding: 40px;"><div class="spinner" style="border-top-color: var(--primary); margin: 0 auto 16px auto;"></div><p style="color:var(--text-muted);">AI is reading your chat to generate deep insights...</p></div>';
                    
                    const statsCol = document.getElementById('statsColumn');
                    const toolShowsStats = window.TOOL_CONFIG ? window.TOOL_CONFIG.showStats : true;
                    if (!statsData.is_document && toolShowsStats && statsData.stats && Object.keys(statsData.stats).length > 0) {
                        if (statsCol) statsCol.classList.remove('hidden');
                        if(exportExcelBtn) exportExcelBtn.classList.remove('hidden');
                        
                        if (statsData.time_series && Object.keys(statsData.time_series).length > 0) {
                            const dates = Object.keys(statsData.time_series).sort();
                            if (dates.length > 0) {
                                dateFrom.value = dates[0];
                                dateTo.value = dates[dates.length - 1];
                                dateFrom.min = dates[0];
                                dateFrom.max = dates[dates.length - 1];
                                dateTo.min = dates[0];
                                dateTo.max = dates[dates.length - 1];
                            }
                            updateChartFromDates();
                        } else if (statsData.stats && Object.keys(statsData.stats).length > 0) {
                            renderChart(statsData.stats);
                        }
                        if (statsData.media || statsData.emojis) {
                            renderMediaStats(statsData.media, statsData.emojis);
                        }
                    }
                }
            }

            // 3. Await Deep AI Analysis
            const data = await aiPromise;
            
            // Finish loader
            clearInterval(loaderInterval);
            progressFill.style.width = '100%';
            progressText.textContent = '100%';
            loadingState.classList.add('hidden');
            
            currentChatId = data.chat_id;
            
            if (toolName === 'search') {
                document.getElementById('focusChatLayout').style.display = 'flex';
                document.getElementById('chatWidget').classList.remove('hidden');
            } else if (toolName !== 'statistics') {
                const sumCont = document.getElementById('summaryContent');
                if(sumCont) sumCont.classList.remove('hidden');
                document.getElementById('chatWidget').classList.remove('hidden');
                
                if (toolName === 'action-items') {
                    summaryText.innerHTML = renderChecklists(data.response || "No action items found.");
                } else {
                    summaryText.innerHTML = marked.parse(data.response || "No summary generated.");
                }
                
                if (data.profiles) {
                    profilesText.innerHTML = marked.parse(data.profiles);
                    profilesContainer.classList.remove('hidden');
                } else {
                    profilesContainer.classList.add('hidden');
                }
            }

        } catch (error) {
            clearInterval(loaderInterval);
            alert('Error: ' + error.message);
            resetUI();
        }
    });
    
    function updateChartFromDates() {
        if (!globalTimeSeries) return;
        const fromD = dateFrom.value;
        const toD = dateTo.value;
        
        let newStats = {};
        for (const [date, users] of Object.entries(globalTimeSeries)) {
            if (date >= fromD && date <= toD) {
                for (const [user, count] of Object.entries(users)) {
                    newStats[user] = (newStats[user] || 0) + count;
                }
            }
        }
        
        // Sort
        const sortedArray = Object.entries(newStats).sort((a, b) => b[1] - a[1]);
        globalFilteredStats = Object.fromEntries(sortedArray);
        renderChart(globalFilteredStats);
    }
    
    if (dateFrom) dateFrom.addEventListener('change', updateChartFromDates);
    if (dateTo) dateTo.addEventListener('change', updateChartFromDates);

    function renderChart(statsData, canvasId = 'statsChart', chartType = 'bar') {
        const entries = Object.entries(statsData).slice(0, 10);
        const labels = entries.map(e => e[0]);
        const data = entries.map(e => e[1]);
        
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;
        
        // Destroy existing chart on this canvas if any
        if (window[`${canvasId}Instance`]) {
            window[`${canvasId}Instance`].destroy();
        }
        
        const config = {
            type: chartType,
            data: {
                labels: labels,
                datasets: [{
                    label: 'Messages',
                    data: data,
                    backgroundColor: window.TOOL_CONFIG ? window.TOOL_CONFIG.color : '#4f46e5',
                    borderRadius: chartType === 'bar' ? 4 : 0,
                    maxBarThickness: 40,
                    borderColor: chartType === 'line' ? (window.TOOL_CONFIG ? window.TOOL_CONFIG.color : '#4f46e5') : undefined,
                    tension: 0.3,
                    fill: chartType === 'line' ? {target: 'origin', above: 'rgba(79, 70, 229, 0.1)'} : false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: chartType !== 'doughnut' ? {
                    y: { 
                        beginAtZero: true,
                        grid: { color: '#f3f4f6' },
                        ticks: { color: '#6b7280', font: { size: 11 } },
                        border: { display: false }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#6b7280', font: { size: 11 } },
                        border: { display: false }
                    }
                } : {}
            }
        };
        
        window[`${canvasId}Instance`] = new Chart(ctx, config);
        return window[`${canvasId}Instance`];
    }
    
    function renderAnalyticsDashboard(data) {
        if (!data.advanced_stats) return;
        
        const adv = data.advanced_stats;
        
        // 1. Populate Advanced KPIs
        document.getElementById('kpiFirstDate').textContent = adv.kpis.first_date || '-';
        document.getElementById('kpiLastDate').textContent = adv.kpis.last_date || '-';
        document.getElementById('kpiDays').textContent = adv.kpis.days_chatted.toLocaleString();
        document.getElementById('kpiTotalMessages').textContent = adv.kpis.total_messages.toLocaleString();
        document.getElementById('kpiPeople').textContent = adv.kpis.people_count.toLocaleString();
        
        // Color palette for users
        const colors = ['#0f766e', '#0d9488', '#14b8a6', '#5eead4', '#f59e0b', '#d97706', '#b45309', '#db2777', '#be185d', '#3b82f6'];
        
        const users = Object.keys(adv.user_stats);
        const userColors = {};
        users.forEach((u, i) => { userColors[u] = colors[i % colors.length]; });
        
        // 2. Timeline Chart (Messages per Day)
        const dailyCounts = {};
        if (data.time_series) {
            for (const [date, u_counts] of Object.entries(data.time_series)) {
                dailyCounts[date] = Object.values(u_counts).reduce((a, b) => a + b, 0);
            }
        }
        renderChart(dailyCounts, 'timelineChart', 'line');
        
        // Helper to destroy and init charts
        const initChart = (id, config) => {
            if (window[`${id}Instance`]) window[`${id}Instance`].destroy();
            const ctx = document.getElementById(id);
            if (ctx) window[`${id}Instance`] = new Chart(ctx, config);
        };
        
        // 3. Donut Chart (Messages per Person)
        initChart('donutChart', {
            type: 'doughnut',
            data: {
                labels: users,
                datasets: [{
                    data: users.map(u => adv.user_stats[u].messages),
                    backgroundColor: users.map(u => userColors[u]),
                    borderWidth: 0
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, cutout: '60%' }
        });
        
        // 4. Stacked Bar Chart (Time of Day)
        const hours = Array.from({length: 24}, (_, i) => String(i).padStart(2, '0'));
        const hourlyDatasets = users.map(u => {
            return {
                label: u,
                data: hours.map(h => (data.hourly_activity[h] && data.hourly_activity[h][u]) || 0),
                backgroundColor: userColors[u]
            };
        });
        
        initChart('hourlyStackedChart', {
            type: 'bar',
            data: { labels: hours.map(h => h + ':00'), datasets: hourlyDatasets },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, border: { display: false } } }
            }
        });
        
        // 5. Radar Chart (Month)
        const months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const monthDatasets = users.map(u => {
            return {
                label: u,
                data: months.map(m => (adv.monthly[m] && adv.monthly[m][u]) || 0),
                borderColor: userColors[u],
                backgroundColor: userColors[u] + '33', // 20% opacity
                borderWidth: 2
            };
        });
        
        initChart('monthRadarChart', {
            type: 'radar',
            data: { labels: monthNames, datasets: monthDatasets },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, scales: { r: { ticks: { display: false } } } }
        });
        
        // 6. Radar Chart (Weekday)
        const weekdays = ['0', '1', '2', '3', '4', '5', '6'];
        const weekdayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const weekdayDatasets = users.map(u => {
            return {
                label: u,
                data: weekdays.map(d => (adv.weekday[d] && adv.weekday[d][u]) || 0),
                borderColor: userColors[u],
                backgroundColor: userColors[u] + '33', // 20% opacity
                borderWidth: 2
            };
        });
        
        initChart('weekdayRadarChart', {
            type: 'radar',
            data: { labels: weekdayNames, datasets: weekdayDatasets },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, scales: { r: { ticks: { display: false } } } }
        });
        
        // 7. Participant Cards
        const cardsContainer = document.getElementById('participantCards');
        cardsContainer.innerHTML = '';
        users.forEach(u => {
            const uData = adv.user_stats[u];
            let emojisHtml = '';
            for (const [emoji, count] of Object.entries(uData.top_emojis)) {
                emojisHtml += `<span title="${count} times" style="font-size: 1.2rem; margin-right: 4px;">${emoji}</span>`;
            }
            if(!emojisHtml) emojisHtml = '<span style="color:var(--text-muted);">None</span>';
            
            cardsContainer.innerHTML += `
                <div class="card" style="border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); background: white;">
                    <div style="background: ${userColors[u]}; padding: 16px 20px;">
                        <h3 style="color: white; margin: 0; font-size: 18px; text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">${u}</h3>
                    </div>
                    <div style="padding: 20px; color: var(--text-secondary); font-size: 15px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 12px; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px;">
                            <span>Total words:</span> <strong style="color: var(--text-primary);">${uData.words.toLocaleString()}</strong>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 12px; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px; align-items: center;">
                            <span>Most used emojis:</span> <div>${emojisHtml}</div>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 12px; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px;">
                            <span>Longest message:</span> <strong style="color: var(--text-primary);">${uData.longest} words</strong>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 12px; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px;">
                            <span>Wordstock (unique words):</span> <strong style="color: var(--text-primary);">${uData.unique_words.toLocaleString()}</strong>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span>Average words per message:</span> <strong style="color: var(--text-primary);">${uData.avg_words}</strong>
                        </div>
                    </div>
                </div>
            `;
        });
    }
    
    function renderChecklists(text) {
        // Convert markdown checkboxes and lists to custom styled checkboxes
        const html = marked.parse(text);
        return html.replace(/<li>/g, '<li class="checklist-item"><input type="checkbox" class="task-checkbox">');
    }
    
    function renderMediaStats(mediaStats, emojis) {
        mediaStatsContainer.classList.remove('hidden');
        
        // Stickers and GIFs
        if (mediaStats) {
            stickerCount.textContent = mediaStats.stickers || 0;
            gifCount.textContent = mediaStats.gifs || 0;
        }
        
        // Emojis
        topEmojis.innerHTML = '';
        if (emojis && Object.keys(emojis).length > 0) {
            Object.entries(emojis).forEach(([emoji, count]) => {
                const badge = document.createElement('div');
                badge.className = 'emoji-badge';
                badge.innerHTML = `<span class="emoji-char">${emoji}</span> <span class="emoji-count">${count}</span>`;
                topEmojis.appendChild(badge);
            });
        } else {
            topEmojis.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem;">No emojis found in this chat.</p>';
        }
    }

    // Export functionality — generate a clean PDF from a stored template
    exportPdfBtn.addEventListener('click', () => {
        exportPdfBtn.disabled = true;
        exportPdfBtn.textContent = 'Generating PDF...';

        const summaryHTML = document.getElementById('summaryText').innerHTML;
        const profilesEl = document.getElementById('profilesText');
        const profilesHTML = (profilesEl && profilesEl.innerHTML.trim()) ? profilesEl.innerHTML : '';

        // Store everything in a variable and build a good UI for the PDF
        const printContainer = document.createElement('div');
        printContainer.innerHTML = `
            <div style="font-family: 'Inter', sans-serif; color: #0f172a; padding: 40px; background: white;">
                <h1 style="font-size: 24px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; margin-bottom: 20px;">
                    ChatRecap - WhatsApp Summary Report
                </h1>
                
                <div style="font-size: 14px; line-height: 1.6; color: #334155;">
                    ${summaryHTML}
                </div>
                
                ${profilesHTML ? `
                <h2 style="font-size: 18px; color: #334155; margin-top: 30px; margin-bottom: 10px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">Personality Profiles</h2>
                <div style="font-size: 14px; line-height: 1.6; color: #334155;">
                    ${profilesHTML}
                </div>
                ` : ''}
                
                <div style="margin-top: 40px; text-align: center; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 10px;">
                    Generated by ChatRecap on ${new Date().toLocaleString()}
                </div>
            </div>
        `;

        const opt = {
            margin:       0,
            filename:     'AI_Summary_Report.pdf',
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2, useCORS: true },
            jsPDF:        { unit: 'in', format: 'a4', orientation: 'portrait' }
        };

        html2pdf().set(opt).from(printContainer).save().then(() => {
            exportPdfBtn.disabled = false;
            exportPdfBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg> Export to PDF`;
        });
    });

    if(exportExcelBtn) exportExcelBtn.addEventListener('click', () => {
        if (!globalFilteredStats) return;
        
        const wb = XLSX.utils.book_new();
        
        // Users Sheet
        const userRows = Object.entries(globalFilteredStats).map(([user, count]) => ({ User: user, Messages: count }));
        const wsUsers = XLSX.utils.json_to_sheet(userRows);
        XLSX.utils.book_append_sheet(wb, wsUsers, "Users");
        
        // Media Sheet
        if (globalMediaStats) {
            const wsMedia = XLSX.utils.json_to_sheet([globalMediaStats]);
            XLSX.utils.book_append_sheet(wb, wsMedia, "Media");
        }
        
        // Emojis Sheet
        if (globalEmojis) {
            const emojiRows = Object.entries(globalEmojis).map(([emoji, count]) => ({ Emoji: emoji, Count: count }));
            const wsEmojis = XLSX.utils.json_to_sheet(emojiRows);
            XLSX.utils.book_append_sheet(wb, wsEmojis, "Top Emojis");
        }
        
        // Timeline & Top Active Days
        if (globalTimeSeries) {
            const dailyCounts = [];
            for (const [date, users] of Object.entries(globalTimeSeries)) {
                const total = Object.values(users).reduce((a, b) => a + b, 0);
                dailyCounts.push({ Date: date, 'Total Messages': total });
            }
            
            // Timeline (chronological)
            dailyCounts.sort((a, b) => a.Date.localeCompare(b.Date));
            const wsTimeline = XLSX.utils.json_to_sheet(dailyCounts);
            XLSX.utils.book_append_sheet(wb, wsTimeline, "Timeline");
            
            // Top Active Days (by count)
            const topDays = [...dailyCounts].sort((a, b) => b['Total Messages'] - a['Total Messages']);
            const wsTopDays = XLSX.utils.json_to_sheet(topDays);
            XLSX.utils.book_append_sheet(wb, wsTopDays, "Top Active Days");
        }

        // Shared Links
        if (typeof globalLinks !== 'undefined' && globalLinks && Object.keys(globalLinks).length > 0) {
            const linkRows = Object.entries(globalLinks).map(([url, data]) => ({ 
                URL: url, 
                Count: data.count, 
                Senders: data.senders.join(", ") 
            }));
            const wsLinks = XLSX.utils.json_to_sheet(linkRows);
            XLSX.utils.book_append_sheet(wb, wsLinks, "Shared Links");
        }

        // Personality Profiles
        const profilesEl = document.getElementById('profilesText');
        if (profilesEl && profilesEl.innerText.trim()) {
            const profilesRows = profilesEl.innerText.split('\n').filter(line => line.trim() !== '').map(line => ({ Profile: line.trim() }));
            const wsProfiles = XLSX.utils.json_to_sheet(profilesRows);
            XLSX.utils.book_append_sheet(wb, wsProfiles, "Personality Profiles");
        }
        
        XLSX.writeFile(wb, "WhatsApp_Analytics.xlsx");
    });

    // Chat Widget Logic
    document.querySelectorAll('.chat-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            if(chatInput) chatInput.value = chip.textContent;
            sendChatMessage();
        });
    });

    if (sendChatBtn) {
        sendChatBtn.addEventListener('click', sendChatMessage);
    }
    
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendChatMessage();
        });
    }

    async function sendChatMessage() {
        const text = chatInput.value.trim();
        if (!text || !currentChatId) return;
        
        // Add user message
        const userMsg = document.createElement('div');
        userMsg.className = 'chat-message user-message';
        userMsg.textContent = text;
        chatHistory.appendChild(userMsg);
        
        chatInput.value = '';
        chatInput.disabled = true;
        sendChatBtn.disabled = true;
        
        // Add loading bubble
        const loadingMsg = document.createElement('div');
        loadingMsg.className = 'chat-message ai-message';
        loadingMsg.textContent = '...';
        chatHistory.appendChild(loadingMsg);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chat_id: currentChatId, message: text })
            });
            const data = await response.json();
            
            chatHistory.removeChild(loadingMsg);
            
            if (!response.ok) throw new Error(data.error || 'Chat Error');
            
            const aiMsg = document.createElement('div');
            aiMsg.className = 'chat-message ai-message';
            aiMsg.innerHTML = marked.parse(data.response); // Use markdown for AI response
            chatHistory.appendChild(aiMsg);
            
        } catch (error) {
            chatHistory.removeChild(loadingMsg);
            const errorMsg = document.createElement('div');
            errorMsg.className = 'chat-message ai-message';
            errorMsg.style.color = 'red';
            errorMsg.textContent = 'Error: ' + error.message;
            chatHistory.appendChild(errorMsg);
        }
        
        chatInput.disabled = false;
        sendChatBtn.disabled = false;
        chatInput.focus();
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    if(exportChatPdfBtn) exportChatPdfBtn.addEventListener('click', () => {
        document.querySelector('.chat-input-container').classList.add('hidden');
        const historyOriginalHeight = chatHistory.style.height;
        const historyOriginalMaxHeight = chatHistory.style.maxHeight;
        const historyOriginalOverflow = chatHistory.style.overflow;
        const historyOriginalOverflowY = chatHistory.style.overflowY;
        
        chatHistory.style.height = 'auto';
        chatHistory.style.maxHeight = 'none';
        chatHistory.style.overflow = 'visible';
        chatHistory.style.overflowY = 'visible';
        
        const opt = {
            margin:       0.5,
            filename:     'QA_Chat_Log.pdf',
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2 },
            jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
        };
        html2pdf().set(opt).from(chatWidget).save().then(() => {
            document.querySelector('.chat-input-container').classList.remove('hidden');
            chatHistory.style.height = historyOriginalHeight;
            chatHistory.style.maxHeight = historyOriginalMaxHeight;
            chatHistory.style.overflow = historyOriginalOverflow;
            chatHistory.style.overflowY = historyOriginalOverflowY;
        });
    });

    if(expandChatBtn) expandChatBtn.addEventListener('click', () => {
        chatWidget.classList.toggle('fullscreen');
        if (chatWidget.classList.contains('fullscreen')) {
            document.body.style.overflow = 'hidden';
            chatHistory.style.height = 'calc(100vh - 120px)';
        } else {
            document.body.style.overflow = 'auto';
            chatHistory.style.height = '300px';
        }
    });

    // Reset Flow
    resetBtn.addEventListener('click', () => {
        resetUI();
    });

    function resetUI() {
        currentFile = null;
        fileInput.value = '';
        pasteInput.value = '';
        dropZone.querySelector('h3').textContent = 'Drag & Drop your chat.txt or .zip';
        dropZone.querySelector('p').textContent = 'or click to browse';
        validateInput();
        
        if (chartInstance) {
            chartInstance.destroy();
            chartInstance = null;
        }
        
        resultSection.classList.add('hidden');
        uploadSection.classList.remove('hidden');
        summaryText.innerHTML = '';
        mediaStatsContainer.classList.add('hidden');
    }
});
