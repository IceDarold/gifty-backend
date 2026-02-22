document.addEventListener("DOMContentLoaded", function () {
    const trackers = document.querySelectorAll(".weeek-tracker");

    trackers.forEach(async (tracker) => {
        const tags = tracker.getAttribute("data-tags");
        const tagNames = tracker.getAttribute("data-tag-names");
        const projectId = tracker.getAttribute("data-project-id");

        try {
            // Loading state
            tracker.innerHTML = `
                <div class="weeek-loading">
                    <div class="weeek-loading-spinner"></div>
                    <div>Загрузка задач...</div>
                </div>
            `;

            // Use absolute URL to point to the backend API on port 8000
            let data;

            // Check if static data is available (for GH Pages / Static builds)
            if (window.WEEEK_STATIC_DATA) {
                // console.log("Using static Weeek data");
                data = filterStaticData(window.WEEEK_STATIC_DATA, tags, tagNames, projectId);
            } else {
                // Fallback to local development API
                let url = "http://localhost:8000/api/v1/integrations/weeek/tasks";
                const params = new URLSearchParams();
                if (tags) params.append("tags", tags);
                if (tagNames) params.append("tagNames", tagNames);
                if (projectId) params.append("projectId", projectId);

                if (params.toString()) {
                    url += "?" + params.toString();
                }

                const response = await fetch(url);
                data = await response.json();
            }

            if (data.success && data.tasks) {
                console.log("Weeek data loaded:", data);
                if (!data.columns) console.warn("Weeek columns missing");
                renderTracker(tracker, data.tasks, data.workspaceId, data.members, data);
            } else {
                console.error("Weeek API error:", data);
                tracker.innerHTML = "<p style='color: red;'>Ошибка загрузки задач</p>";
            }
        } catch (e) {
            console.error("Weeek fetch error:", e);
            tracker.innerHTML = `<p style='color: red;'>Ошибка: ${e.message}</p>`;
        }
    });
});

function renderTracker(container, tasks, workspaceId, membersMap, data) {
    // Sort: Active first, then completed
    tasks.sort((a, b) => {
        if (a.isCompleted === b.isCompleted) return 0;
        return a.isCompleted ? 1 : -1;
    });

    const total = tasks.length;
    const completed = tasks.filter(t => t.isCompleted).length;
    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

    // Use a unique ID for this tracker instance to manage modals/events
    const trackerId = Math.random().toString(36).substr(2, 9);
    window[`weeek_tasks_${trackerId}`] = tasks;
    window[`weeek_members_${trackerId}`] = membersMap;
    window[`weeek_ws_${trackerId}`] = workspaceId;
    window[`weeek_cols_${trackerId}`] = data.columns || {};

    // Extract Columns
    const uniqueCols = new Set();
    if (data.columns) {
        tasks.forEach(t => {
            if (t.boardColumnId && data.columns[t.boardColumnId]) {
                uniqueCols.add(data.columns[t.boardColumnId]);
            }
        });
    }

    // Sort columns? Maybe alphabetical for now.
    const sortedCols = Array.from(uniqueCols).sort();

    // Generate Tabs HTML
    let tabsHtml = '';
    let initialFilter = 'all';

    if (sortedCols.length > 0) {
        initialFilter = sortedCols[0]; // Default to first column

        sortedCols.forEach((colName, index) => {
            // Beautify: capitalize
            const displayName = colName.charAt(0).toUpperCase() + colName.slice(1).toLowerCase();
            const activeClass = index === 0 ? 'active' : '';
            tabsHtml += `<button class="weeek-tab-btn ${activeClass}" onclick="filterWeeekTasks('${trackerId}', '${colName}', this)">${displayName}</button>`;
        });
        tabsHtml = `<div class="weeek-tabs">${tabsHtml}</div>`;
    }

    // Find Project ID for the link (take from first task)
    let projectLink = '#';
    if (workspaceId && tasks.length > 0 && tasks[0].projectId) {
        projectLink = `https://app.weeek.net/ws/${workspaceId}/project/${tasks[0].projectId}/calendar`;
    }

    let html = `
        <div class="weeek-tracker-container">
            <div class="weeek-header">
                <div>
                    <h4>Статус выполнения</h4>
                </div>
                <div class="weeek-header-actions">
                     ${projectLink !== '#' ? `<a href="${projectLink}" target="_blank" class="weeek-open-link">Open in Weeek ↗</a>` : ''}
                     <span>${completed} / ${total} (${percent}%)</span>
                </div>
            </div>
            <div class="weeek-progress-bar">
                <div class="weeek-progress-fill" style="width: ${percent}%"></div>
            </div>
            
            ${tabsHtml}
            
            <div class="weeek-list-wrapper collapsed" id="wrapper-${trackerId}" data-expanded="false">
                <ul class="weeek-task-list" id="list-${trackerId}">
                    ${renderTaskList(tasks, workspaceId, membersMap, trackerId)}
                </ul>
                
                <div class="weeek-list-mask" onclick="toggleWeeekList('${trackerId}')" id="mask-${trackerId}">
                    <button class="weeek-show-more-btn" id="btn-${trackerId}">
                        See more tasks <span class="arrow">›</span>
                    </button>
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;

    // Initial hide logic if needed handled by CSS 'collapsed' class and mask
    // We only show first 5 initially?
    // The CSS .collapsed sets max-height to ~190px which is about 1 row.
    // User wants "Show only first 5". Card height ~150px. Grid 280px wide.
    // It's a grid, so "first 5" might be 2 rows or 1 row depending on width.
    // CSS-only "height" truncation is tricky for exact count.

    // Let's implement JS-based filtering for "Show More"
    // Initial filter
    const activeBtn = container.querySelector('.weeek-tab-btn.active');
    filterWeeekTasks(trackerId, initialFilter, activeBtn);
}

function renderTaskList(tasks, workspaceId, membersMap, trackerId) {
    return tasks.map((task) => {
        const isVerified = task.isCompleted;
        const checkClass = isVerified ? "checked" : "";
        const completeClass = isVerified ? "completed" : "";
        const taskId = `#${task.id}`;
        let titleHtml = task.title;

        // Assignees
        let assigneesHtml = '';
        if (task.assignees && task.assignees.length > 0) {
            const avatars = task.assignees.map(uid => {
                const member = membersMap && membersMap[uid];
                if (member && member.logo) {
                    return `<img src="${member.logo}" class="weeek-assignee-avatar" title="${member.firstName} ${member.lastName}">`;
                }
                const initials = member ? (member.firstName[0] + (member.lastName ? member.lastName[0] : '')) : '??';
                return `<div class="weeek-no-assignee" title="${uid}">${initials}</div>`;
            }).join('');
            assigneesHtml = `<div class="weeek-assignees">${avatars}</div>`;
        }

        // Date Fix
        let dateHtml = '';
        let dStr = task.date || task.dueDate || task.dateStart;
        if (dStr) {
            if (dStr.includes(".")) {
                // DD.MM.YYYY
                const parts = dStr.split(".");
                if (parts.length === 3) dStr = `${parts[2]}-${parts[1]}-${parts[0]}`;
            }
            const d = new Date(dStr);
            if (!isNaN(d.getTime())) {
                const options = { day: 'numeric', month: 'short' };
                const prettyDate = d.toLocaleDateString('en-US', options);
                dateHtml = `<span>${prettyDate}</span>`;
            }
        }

        // Tags
        let tagHtml = `<span class="weeek-tag">Task</span>`;

        return `
            <li class="weeek-task-card ${completeClass}" onclick="openWeeekModal('${trackerId}', '${task.id}')">
                <div class="weeek-card-header">
                    <span class="weeek-task-id">${taskId}</span>
                    <div class="weeek-card-title">${titleHtml}</div>
                </div>
                <div class="weeek-card-content">
                    ${assigneesHtml}
                    <div class="weeek-card-footer" style="margin-top:0; width: auto; gap: 10px;">
                        ${dateHtml}
                        <div class="weeek-check-circle ${checkClass}"></div>
                    </div>
                </div>
                <div style="margin-top: 12px;">${tagHtml}</div>
            </li>
        `;
    }).join("");
}


function filterWeeekTasks(trackerId, colName, btn) {
    // Update active tab
    let container;
    if (btn) {
        container = btn.closest('.weeek-tracker-container');
        container.querySelectorAll('.weeek-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    } else {
        // Fallback if no button provided
        const wrapper = document.getElementById(`wrapper-${trackerId}`);
        if (wrapper) container = wrapper.closest('.weeek-tracker-container');
    }

    const tasks = window[`weeek_tasks_${trackerId}`];
    const columnsMap = window[`weeek_cols_${trackerId}`];

    // Filter
    let filtered = tasks;
    if (colName !== 'all') {
        filtered = tasks.filter(t => {
            const cName = columnsMap[t.boardColumnId];
            return cName === colName;
        });
    }

    // Save state for toggle
    window[`weeek_filtered_${trackerId}`] = filtered;

    // Render (Limit to 5 initially if collapsed)
    const wrapper = document.getElementById(`wrapper-${trackerId}`);
    // Ensure we respect current state or default to false
    const isExpanded = wrapper.getAttribute("data-expanded") === "true";

    renderFiltered(trackerId, filtered, isExpanded);
}

function renderFiltered(trackerId, tasks, isExpanded) {
    const list = document.getElementById(`list-${trackerId}`);
    const mask = document.getElementById(`mask-${trackerId}`);
    const wsId = window[`weeek_ws_${trackerId}`];
    const members = window[`weeek_members_${trackerId}`];
    const wrapper = document.getElementById(`wrapper-${trackerId}`);

    // Render ALL filtered tasks
    list.innerHTML = renderTaskList(tasks, wsId, members, trackerId);

    // Show/Hide Mask/Button logic
    if (tasks.length > 1) {
        mask.style.display = 'flex';
        mask.style.opacity = '1';
    } else {
        mask.style.display = 'none';
    }

    // Manage max-height for transition
    if (isExpanded) {
        // Use timeout to allow DOM to flow before measuring height if needed,
        // but usually synchronous after innerHTML is fine for scrollHeight
        wrapper.style.maxHeight = wrapper.scrollHeight + "px";
    } else {
        wrapper.style.maxHeight = null; // Revert to CSS class rule (170px)
    }

    const btnText = isExpanded ? "Show less" : "See more tasks";
    const arrowRot = isExpanded ? "-90deg" : "90deg";
    mask.querySelector('button').innerHTML = `${btnText} <span class="arrow" style="transform: rotate(${arrowRot}); display:inline-block">›</span>`;
}

function toggleWeeekList(trackerId) {
    const wrapper = document.getElementById(`wrapper-${trackerId}`);
    const isExpanded = wrapper.getAttribute("data-expanded") === "true";
    const newState = !isExpanded;

    wrapper.setAttribute("data-expanded", String(newState));
    wrapper.classList.toggle("collapsed", !newState);

    // Smooth transition
    if (newState) {
        wrapper.style.maxHeight = wrapper.scrollHeight + "px";
    } else {
        wrapper.style.maxHeight = null;
    }

    // Only update button text, no need to re-render entire list if filtering didn't change
    // But renderFiltered handles both.
    const tasks = window[`weeek_filtered_${trackerId}`];
    renderFiltered(trackerId, tasks, newState);

    // Mask style
    const mask = document.getElementById(`mask-${trackerId}`);
    if (newState) {
        mask.style.position = 'relative'; // Move to bottom
        mask.style.background = 'transparent';
    } else {
        mask.style.position = 'absolute';
        mask.style.background = 'linear-gradient(to bottom, transparent, var(--md-code-bg-color))';
    }
}

function openWeeekModal(trackerId, taskId) {
    const tasks = window[`weeek_tasks_${trackerId}`];
    // Robust comparisons for string/number IDs
    const task = tasks.find(t => String(t.id) === String(taskId));
    const membersMap = window[`weeek_members_${trackerId}`];
    const columnsMap = window[`weeek_cols_${trackerId}`];
    const workspaceId = window[`weeek_ws_${trackerId}`];

    if (!task) return;

    // Create Modal DOM if not exists
    let overlay = document.querySelector('.weeek-modal-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'weeek-modal-overlay';
        overlay.onclick = (e) => { if (e.target === overlay) closeWeeekModal(); };
        document.body.appendChild(overlay);
    }

    // Prepare Data
    const displayId = `#${task.id}`;
    // Get column name
    const colName = (columnsMap && columnsMap[task.boardColumnId]) || (task.isCompleted ? "Completed" : "Task");
    // Nicer Formatting: Capitalize
    const statusText = colName.charAt(0).toUpperCase() + colName.slice(1).toLowerCase();

    // Neutral Color Style
    const statusColor = "var(--md-typeset-color--light)";
    const statusBg = "var(--md-code-bg-color)";

    let assigneesList = "Unassigned";
    if (task.assignees && task.assignees.length > 0) {
        assigneesList = task.assignees.map(uid => {
            const m = membersMap && membersMap[uid];
            if (m) {
                const name = `${m.firstName} ${m.lastName || ''}`.trim();
                return `<div class="weeek-prop-value"><img src="${m.logo}" style="width:20px;height:20px;border-radius:50%"> ${name}</div>`;
            }
            return `<div class="weeek-prop-value">${uid}</div>`;
        }).join('');
    }

    const dateStr = (task.date || task.dueDate || '').split('T')[0] || 'No date';
    const link = workspaceId ? `https://app.weeek.net/ws/${workspaceId}/task/${task.id}` : '#';
    const description = task.description || '<span style="color:var(--md-typeset-color--light);font-style:italic">No description provided.</span>';

    overlay.innerHTML = `
        <div class="weeek-modal-card">
             <div class="weeek-modal-close" onclick="closeWeeekModal()">×</div>
             
             <div class="weeek-modal-header" style="padding-bottom: 20px; border-bottom: 1px solid var(--md-typeset-table-color);">
                 <!-- ID -->
                 <div style="color:var(--md-typeset-color--light); font-size:0.9em; margin-bottom: 8px;">${displayId}</div>

                 <!-- Title -->
                 <div class="weeek-modal-title" style="margin-bottom: 16px; margin-top: 0;">${task.title}</div>
                 
                 <!-- Meta Row: Assignees -> Date -->
                 <div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap; font-size: 0.95em;">
                     
                     <!-- Assignees -->
                     <div style="display:flex; align-items:center; gap:8px;">
                        ${assigneesList !== 'Unassigned' ? assigneesList : '<span style="color:var(--md-typeset-color--light)">Unassigned</span>'}
                     </div>

                     <!-- Divider -->
                     <span style="color:var(--md-typeset-table-color)">|</span>

                     <!-- Date -->
                     <div style="color: var(--md-typeset-color--light); display: flex; align-items: center; gap: 6px;">
                        <span>📅</span> ${dateStr}
                     </div>
                 </div>
             </div>
             
             <div class="weeek-modal-body" style="padding-top: 24px;">
                 <div class="weeek-modal-main">
                     ${description}
                 </div>
                 
                 <a href="${link}" target="_blank" class="weeek-action-btn" style="margin-top:32px; width:auto; display:inline-block">
                     Open in Weeek ↗
                 </a>
             </div>
        </div>
    `;

    overlay.classList.add('open');
    document.body.style.overflow = 'hidden'; // Prevent scrolling bg
}

function closeWeeekModal() {
    const overlay = document.querySelector('.weeek-modal-overlay');
    if (overlay) {
        overlay.classList.remove('open');
        overlay.innerHTML = '';
    }
    document.body.style.overflow = '';
}

function filterStaticData(data, tagsStr, tagNamesStr, projectIdStr) {
    let tasks = data.tasks || [];

    // 1. Filter by Project
    if (projectIdStr) {
        tasks = tasks.filter(t => String(t.projectId) === String(projectIdStr));
    }

    // 2. Filter by Tags
    const requiredTagIds = new Set();

    if (tagsStr) {
        tagsStr.split(',').forEach(s => {
            const id = parseInt(s.trim());
            if (!isNaN(id)) requiredTagIds.add(id);
        });
    }

    if (tagNamesStr && data.tags) {
        const names = tagNamesStr.split(',').map(s => s.trim().toLowerCase());
        data.tags.forEach(tag => {
            if (names.includes(tag.title.toLowerCase())) {
                requiredTagIds.add(tag.id);
            }
        });
    }

    if (requiredTagIds.size > 0) {
        tasks = tasks.filter(t => {
            if (!t.tags) return false;
            // Check intersection (ANY match)
            return t.tags.some(tid => requiredTagIds.has(tid));
        });
    }

    // Return structure matching API response
    return {
        success: true,
        tasks: tasks,
        hasMore: false,
        workspaceId: data.workspaceId,
        members: data.members,
        columns: data.columns
    };
}
