/*
 * Almanac, blog and wiki for the GreenPi dashboard.
 * Relies on globals from index.html: showSection(), csrfToken(), escapeHtml(),
 * loadClimate(), loadSensors(), loadNetworkConfig().
 *
 * Routes (hash based, so links and the Back button work):
 *   #/climate  #/sensors  #/config
 *   #/almanac  #/almanac/2026-11  #/almanac/2026-11-16
 *   #/blog     #/blog/12
 *   #/wiki     #/wiki/some-page   #/wiki/some-page/history
 */
(function () {
    'use strict';

    // ------------------------------------------------------------------ helpers

    const $ = id => document.getElementById(id);
    const esc = s => escapeHtml(s == null ? '' : s);
    let canEdit = false;

    async function api(url, { method = 'GET', body, form } = {}) {
        const opts = { method, headers: {} };
        if (method !== 'GET') opts.headers['X-CSRFToken'] = csrfToken();
        if (form) opts.body = form;
        else if (body !== undefined) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }
        let res, data = {};
        try {
            res = await fetch(url, opts);
            data = await res.json().catch(() => ({}));
        } catch (e) {
            return { ok: false, status: 0, data: { message: 'Could not reach the greenhouse controller.' } };
        }
        return { ok: res.ok, status: res.status, data };
    }

    function dayLabel(iso, opts = { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }) {
        return new Date(iso + 'T12:00:00').toLocaleDateString(undefined, opts);
    }

    function localToday() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }

    function setCanEdit(v) {
        canEdit = !!v;
        document.querySelectorAll('.staff-only').forEach(el => el.classList.toggle('hidden', !canEdit));
    }

    const KIND_STYLE = {
        frost: '❄️', planting: '🌱', harvest: '🧺', task: '✅', note: '📝',
    };

    // ------------------------------------------------------------------ editor

    let editorState = null;

    function openEditor(cfg) {
        // cfg: {heading, title, body, meta: html, photos: bool, onSave(vals) -> {ok,message}, onDelete?}
        editorState = cfg;
        $('ed-heading').innerText = cfg.heading;
        $('ed-title').value = cfg.title || '';
        $('ed-body').value = cfg.body || '';
        $('ed-meta').innerHTML = cfg.meta || '';
        $('ed-photo-label').classList.toggle('hidden', cfg.photos === false);
        $('ed-preview').classList.add('hidden');
        $('ed-body').classList.remove('hidden');
        $('ed-preview-btn').innerText = 'Preview';
        $('ed-status').innerText = '';
        $('ed-delete').classList.toggle('hidden', !cfg.onDelete);
        $('editor').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        $('ed-title').focus();
    }

    function closeEditor() {
        $('editor').classList.add('hidden');
        document.body.style.overflow = '';
        editorState = null;
    }

    function insertAtCursor(textarea, text) {
        const { selectionStart: s, selectionEnd: e, value } = textarea;
        const before = value.slice(0, s), after = value.slice(e);
        const pad = before && !before.endsWith('\n') ? '\n' : '';
        textarea.value = before + pad + text + '\n' + after;
        textarea.selectionStart = textarea.selectionEnd = (before + pad + text + '\n').length;
        textarea.focus();
    }

    $('ed-cancel').addEventListener('click', closeEditor);
    $('editor').addEventListener('click', e => { if (e.target === $('editor')) closeEditor(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && editorState) closeEditor(); });

    $('ed-preview-btn').addEventListener('click', async () => {
        const showing = !$('ed-preview').classList.contains('hidden');
        if (showing) {
            $('ed-preview').classList.add('hidden');
            $('ed-body').classList.remove('hidden');
            $('ed-preview-btn').innerText = 'Preview';
            return;
        }
        const r = await api('/api/preview/', { method: 'POST', body: { body: $('ed-body').value } });
        $('ed-preview').innerHTML = r.ok ? r.data.html : `<p class="text-red-700">${esc(r.data.message || 'Preview failed')}</p>`;
        $('ed-preview').classList.remove('hidden');
        $('ed-body').classList.add('hidden');
        $('ed-preview-btn').innerText = 'Edit';
    });

    $('ed-photo').addEventListener('change', async () => {
        const file = $('ed-photo').files[0];
        $('ed-photo').value = '';
        if (!file) return;
        const caption = prompt('Caption for this photo (optional):', '') || '';
        $('ed-status').innerText = `Uploading ${file.name}…`;
        const form = new FormData();
        form.append('photo', file);
        form.append('caption', caption);
        const r = await api('/api/photos/', { method: 'POST', form });
        if (!r.ok) { $('ed-status').innerText = 'Upload failed: ' + (r.data.message || r.status); return; }
        insertAtCursor($('ed-body'), r.data.markdown);
        $('ed-status').innerText = `Added photo (${r.data.width}×${r.data.height}).`;
    });

    $('ed-save').addEventListener('click', async () => {
        if (!editorState) return;
        $('ed-status').innerText = 'Saving…';
        const vals = { title: $('ed-title').value.trim(), body: $('ed-body').value };
        $('ed-meta').querySelectorAll('[data-field]').forEach(el => {
            vals[el.dataset.field] = el.type === 'checkbox' ? el.checked : el.value;
        });
        const res = await editorState.onSave(vals);
        if (res && res.ok) closeEditor();
        else $('ed-status').innerText = 'Not saved: ' + ((res && res.message) || 'error');
    });

    $('ed-delete').addEventListener('click', async () => {
        if (!editorState || !editorState.onDelete) return;
        if (!confirm('Delete this permanently?')) return;
        await editorState.onDelete();
        closeEditor();
    });

    // ------------------------------------------------------------------ almanac

    let almMonth = localToday().slice(0, 7);
    let almSelected = null;

    function shiftMonth(ym, delta) {
        const [y, m] = ym.split('-').map(Number);
        const d = new Date(y, m - 1 + delta, 1);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    }

    $('alm-prev').addEventListener('click', () => { location.hash = `#/almanac/${shiftMonth(almMonth, -1)}`; });
    $('alm-next').addEventListener('click', () => { location.hash = `#/almanac/${shiftMonth(almMonth, 1)}`; });
    $('alm-today').addEventListener('click', () => { location.hash = `#/almanac/${localToday()}`; });
    $('alm-add-event').addEventListener('click', () => editEvent(null, almSelected || localToday()));

    async function showAlmanac(month, day) {
        almMonth = month;
        almSelected = day || null;
        const r = await api(`/api/almanac/month/?month=${month}`);
        if (!r.ok) { $('alm-grid').innerHTML = `<p class="col-span-7 p-4 text-red-700">${esc(r.data.message || 'Could not load the almanac.')}</p>`; return; }
        const d = r.data;
        setCanEdit(d.can_edit);
        $('alm-title').innerText = d.title;
        $('alm-location-note').classList.toggle('hidden', d.location_set);

        const cells = [];
        for (let i = 0; i < d.first_weekday; i++) cells.push('<div></div>');
        d.days.forEach(day => {
            const c = day.climate;
            const isToday = day.date === d.today, isSel = day.date === almSelected;
            const marks = day.events.map(e => KIND_STYLE[e.kind] || '•').join('') + (day.posts.length ? '📓' : '');
            cells.push(`<a href="#/almanac/${day.date}" class="block rounded-lg p-1 md:p-2 min-h-[4.2rem] text-left border
                    ${isSel ? 'border-green-600 bg-green-50' : 'border-gray-100 hover:bg-green-50'}">
                <div class="flex justify-between items-start text-xs">
                    <span class="${isToday ? 'bg-green-600 text-white rounded-full px-1.5' : 'font-semibold'}">${Number(day.date.slice(8))}</span>
                    <span title="${esc(day.moon.name)}">${day.moon.emoji}</span>
                </div>
                ${c ? `<div class="text-[11px] md:text-xs mt-1 leading-tight"><span class="text-blue-700">${Math.round(c.temp_min)}°</span>/<span class="text-red-700">${Math.round(c.temp_max)}°</span></div>` : ''}
                <div class="text-[11px] leading-tight mt-0.5 truncate">${marks}</div>
            </a>`);
        });
        $('alm-grid').innerHTML = cells.join('');
        if (day) showAlmanacDay(day); else $('alm-day').classList.add('hidden');
    }

    async function showAlmanacDay(day) {
        const box = $('alm-day');
        box.classList.remove('hidden');
        box.innerHTML = '<p class="text-gray-500">Loading…</p>';
        const r = await api(`/api/almanac/day/${day}/`);
        if (!r.ok) { box.innerHTML = `<p class="text-red-700">${esc(r.data.message || 'Could not load this day.')}</p>`; return; }
        const d = r.data, c = d.climate, s = d.sun, m = d.moon;

        const climate = c ? `
            <div class="grid grid-cols-3 gap-3 text-center">
                <div class="bg-blue-50 rounded-lg p-3"><div class="text-xs text-gray-500">Low</div><div class="text-2xl font-bold text-blue-700">${c.temp_min}°F</div></div>
                <div class="bg-red-50 rounded-lg p-3"><div class="text-xs text-gray-500">High</div><div class="text-2xl font-bold text-red-700">${c.temp_max}°F</div></div>
                <div class="bg-gray-50 rounded-lg p-3"><div class="text-xs text-gray-500">Humidity</div><div class="text-2xl font-bold">${c.rh_avg != null ? Math.round(c.rh_avg) + '%' : '–'}</div></div>
            </div>
            <p class="text-xs text-gray-500 mt-1">Swing ${(c.temp_max - c.temp_min).toFixed(1)} °F · ${c.readings} readings</p>`
            : '<p class="text-gray-500 text-sm">No greenhouse readings for this day.</p>';

        const fmtMins = n => `${Math.floor(n / 60)} h ${n % 60} min`;
        const sun = s ? `
            <div class="text-sm space-y-1">
                <div>🌅 Sunrise <b>${s.sunrise}</b> · 🌇 Sunset <b>${s.sunset}</b></div>
                <div>Daylight ${fmtMins(s.daylight_minutes)}${s.daylight_change_minutes != null ? ` (${s.daylight_change_minutes >= 0 ? '+' : ''}${s.daylight_change_minutes} min vs. yesterday)` : ''}</div>
                <div class="text-gray-500">Dawn ${s.dawn} · Solar noon ${s.noon} · Dusk ${s.dusk}</div>
            </div>` : '<p class="text-xs text-gray-500">Sun times appear once the greenhouse location is set.</p>';

        const events = d.events.map(e => `
            <div class="border rounded-lg p-3">
                <div class="flex justify-between gap-2">
                    <div class="font-semibold">${KIND_STYLE[e.kind] || ''} ${esc(e.title)} ${e.yearly ? '<span class="text-xs text-gray-500">(every year)</span>' : ''}</div>
                    ${d.can_edit ? `<button data-edit-event="${e.id}" class="text-sm text-green-700 underline">Edit</button>` : ''}
                </div>
                ${e.notes_html ? `<div class="prose text-sm">${e.notes_html}</div>` : ''}
            </div>`).join('');

        const posts = d.posts.map(p => `
            <a href="#/blog/${p.id}" class="block border rounded-lg p-3 hover:bg-green-50">
                <div class="font-semibold">📓 ${esc(p.title)} ${p.published ? '' : '<span class="text-xs text-orange-700">(draft)</span>'}</div>
                <div class="text-sm text-gray-600">${esc(p.excerpt)}</div>
            </a>`).join('');

        box.innerHTML = `
            <div class="flex justify-between items-start flex-wrap gap-2 mb-4">
                <h3 class="text-2xl font-bold text-green-800">${dayLabel(d.date)}</h3>
                <div class="text-sm">${m.emoji} ${esc(m.name)} · ${m.illumination_pct}% lit</div>
            </div>
            <div class="grid md:grid-cols-2 gap-6">
                <div><h4 class="font-semibold mb-2">Greenhouse</h4>${climate}</div>
                <div><h4 class="font-semibold mb-2">Sun</h4>${sun}</div>
            </div>
            <div class="mt-6">
                <div class="flex justify-between items-center mb-2"><h4 class="font-semibold">Events</h4>
                    ${d.can_edit ? `<button id="day-add-event" class="text-sm text-green-700 underline">+ Add event</button>` : ''}</div>
                ${events || '<p class="text-sm text-gray-500">None.</p>'}
            </div>
            <div class="mt-6">
                <div class="flex justify-between items-center mb-2"><h4 class="font-semibold">Journal</h4>
                    ${d.can_edit ? `<button id="day-new-post" class="text-sm text-green-700 underline">+ Write about this day</button>` : ''}</div>
                <div class="space-y-2">${posts || '<p class="text-sm text-gray-500">No entries.</p>'}</div>
            </div>`;

        box.querySelectorAll('[data-edit-event]').forEach(b => b.addEventListener('click', async () => {
            const er = await api(`/api/almanac/events/${b.dataset.editEvent}/`);
            if (er.ok) editEvent(er.data, d.date);
        }));
        const addEv = $('day-add-event');
        if (addEv) addEv.addEventListener('click', () => editEvent(null, d.date));
        const newPost = $('day-new-post');
        if (newPost) newPost.addEventListener('click', () => editPost(null, d.date));
        box.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function editEvent(ev, dateIso) {
        const kinds = [['frost', 'Frost'], ['planting', 'Planting'], ['harvest', 'Harvest'], ['task', 'Task'], ['note', 'Note']];
        const kind = ev ? ev.kind : 'note';
        openEditor({
            heading: ev ? 'Edit almanac event' : 'New almanac event',
            title: ev ? ev.title : '',
            body: ev ? ev.notes : '',
            photos: false,
            meta: `
                <label>Date <input data-field="date" type="date" value="${esc(ev ? ev.date : dateIso)}" class="border rounded p-1"></label>
                <label>Kind <select data-field="kind" class="border rounded p-1">
                    ${kinds.map(([v, l]) => `<option value="${v}" ${v === kind ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
                <label class="flex items-center gap-1"><input data-field="yearly" type="checkbox" ${ev && ev.yearly ? 'checked' : ''}> Repeats every year</label>`,
            onSave: async v => {
                const payload = { title: v.title, date: v.date, kind: v.kind, yearly: v.yearly, notes: v.body };
                const r = ev ? await api(`/api/almanac/events/${ev.id}/`, { method: 'PUT', body: payload })
                             : await api('/api/almanac/events/', { method: 'POST', body: payload });
                if (r.ok) showAlmanac(v.date.slice(0, 7), v.date);
                return { ok: r.ok, message: r.data.message };
            },
            onDelete: ev ? async () => {
                await api(`/api/almanac/events/${ev.id}/`, { method: 'DELETE' });
                showAlmanac(almMonth, almSelected);
            } : null,
        });
    }

    // ------------------------------------------------------------------ blog

    let blogPage = 1;
    let blogSearchTimer = null;
    $('blog-new').addEventListener('click', () => editPost(null, localToday()));
    $('blog-search').addEventListener('input', () => {
        clearTimeout(blogSearchTimer);
        blogSearchTimer = setTimeout(() => { blogPage = 1; showBlogList(); }, 300);
    });

    async function showBlogList() {
        const q = $('blog-search').value.trim();
        const r = await api(`/api/blog/?page=${blogPage}&q=${encodeURIComponent(q)}`);
        const view = $('blog-view');
        if (!r.ok) { view.innerHTML = `<p class="text-red-700">${esc(r.data.message || 'Could not load posts.')}</p>`; return; }
        const d = r.data;
        setCanEdit(d.can_edit);
        const cards = d.posts.map(p => `
            <a href="#/blog/${p.id}" class="card overflow-hidden block hover:shadow-lg transition">
                ${p.cover ? `<img src="${esc(p.cover)}" alt="" loading="lazy" class="w-full h-44 object-cover">` : ''}
                <div class="p-4">
                    <div class="text-xs text-gray-500 flex flex-wrap items-center gap-x-2">${dayLabel(p.date, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
                        ${p.published ? '' : ' · <span class="text-orange-700">draft</span>'}${p.author ? ' · ' + byLine(p.author) : ''}</div>
                    <h3 class="text-lg font-bold">${esc(p.title)}</h3>
                    <p class="text-sm text-gray-600 mt-1">${esc(p.excerpt)}</p>
                </div>
            </a>`).join('');
        const pager = d.pages > 1 ? `
            <div class="flex justify-center items-center gap-3 mt-6">
                <button ${d.page <= 1 ? 'disabled' : ''} data-blog-page="${d.page - 1}" class="px-3 py-1 rounded bg-white shadow disabled:opacity-40">‹ Newer</button>
                <span class="text-sm text-gray-500">Page ${d.page} of ${d.pages}</span>
                <button ${d.page >= d.pages ? 'disabled' : ''} data-blog-page="${d.page + 1}" class="px-3 py-1 rounded bg-white shadow disabled:opacity-40">Older ›</button>
            </div>` : '';
        view.innerHTML = cards
            ? `<div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">${cards}</div>${pager}`
            : `<div class="card p-6 text-gray-600">${q ? 'No posts match.' : 'No posts yet.'}${d.can_edit && !q ? ' Use <b>+ New post</b> to write the first one.' : ''}</div>`;
        view.querySelectorAll('[data-blog-page]').forEach(b => b.addEventListener('click', () => {
            blogPage = Number(b.dataset.blogPage);
            showBlogList();
            window.scrollTo(0, 0);
        }));
    }

    async function showBlogPost(id) {
        const view = $('blog-view');
        const r = await api(`/api/blog/${id}/`);
        if (!r.ok) {
            view.innerHTML = `<a href="#/blog" class="text-green-700 underline">← All posts</a><p class="mt-4 text-gray-600">That post doesn't exist (or is a draft).</p>`;
            return;
        }
        const p = r.data;
        setCanEdit(p.can_edit);
        view.innerHTML = `
            <a href="#/blog" class="inline-flex items-center gap-2 mb-4 px-4 py-2 rounded-lg bg-white shadow text-green-800 font-semibold hover:bg-green-100 border border-green-200">← All posts</a>
            <article class="card p-5 md:p-8">
                <div class="flex justify-between items-start gap-2 flex-wrap">
                    <div>
                        <a href="#/almanac/${p.date}" class="text-sm text-green-700 underline">${dayLabel(p.date)}</a>
                        ${p.published ? '' : ' <span class="text-xs text-orange-700">(draft)</span>'}
                        <h3 class="text-3xl font-bold mt-1">${esc(p.title)}</h3>
                        ${p.author ? `<div class="text-sm text-gray-600 mt-1">by ${byLine(p.author)}</div>` : ''}
                    </div>
                    ${p.can_edit ? '<button id="post-edit" class="px-4 py-2 rounded border border-green-600 text-green-700 hover:bg-green-50">Edit</button>' : ''}
                </div>
                <div class="prose mt-4">${p.html}</div>
            </article>`;
        const editBtn = $('post-edit');
        if (editBtn) editBtn.addEventListener('click', () => editPost(p));
        window.scrollTo(0, 0);
    }

    function editPost(post, dateIso) {
        openEditor({
            heading: post ? 'Edit post' : 'New journal post',
            title: post ? post.title : '',
            body: post ? post.body : '',
            meta: `
                <label>Day <input data-field="date" type="date" value="${esc(post ? post.date : dateIso)}" class="border rounded p-1"></label>
                <label class="flex items-center gap-1"><input data-field="published" type="checkbox" ${!post || post.published ? 'checked' : ''}> Published</label>`,
            onSave: async v => {
                const payload = { title: v.title, date: v.date, body: v.body, published: v.published };
                const r = post ? await api(`/api/blog/${post.id}/`, { method: 'PUT', body: payload })
                               : await api('/api/blog/', { method: 'POST', body: payload });
                if (r.ok) {
                    const id = post ? post.id : r.data.id;
                    if (location.hash === `#/blog/${id}`) showBlogPost(id); else location.hash = `#/blog/${id}`;
                }
                return { ok: r.ok, message: r.data.message };
            },
            onDelete: post ? async () => {
                await api(`/api/blog/${post.id}/`, { method: 'DELETE' });
                location.hash = '#/blog';
            } : null,
        });
    }

    // ------------------------------------------------------------------ wiki

    let wikiSearchTimer = null;
    $('wiki-new').addEventListener('click', () => {
        const title = prompt('Title of the new page:');
        if (!title) return;
        const slug = title.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'page';
        editWiki({ slug, title, body: '', exists: false });
    });
    $('wiki-search').addEventListener('input', () => {
        clearTimeout(wikiSearchTimer);
        wikiSearchTimer = setTimeout(showWikiIndex, 300);
    });

    async function showWikiIndex() {
        const q = $('wiki-search').value.trim();
        const r = await api(`/api/wiki/?q=${encodeURIComponent(q)}`);
        const view = $('wiki-view');
        if (!r.ok) { view.innerHTML = `<p class="text-red-700">${esc(r.data.message || 'Could not load the wiki.')}</p>`; return; }
        setCanEdit(r.data.can_edit);
        const rows = r.data.pages.map(p => `
            <a href="#/wiki/${esc(p.slug)}" class="block p-4 border-b last:border-0 hover:bg-green-50">
                <div class="font-semibold text-green-800">${esc(p.title)}</div>
                <div class="text-sm text-gray-600">${esc(p.excerpt)}</div>
            </a>`).join('');
        view.innerHTML = `<div class="card">${rows || `<p class="p-6 text-gray-600">${q ? 'No pages match.' : 'No pages yet.'}${r.data.can_edit && !q ? ' Use <b>+ New page</b> to start one.' : ''}</p>`}</div>`;
    }

    async function showWikiPage(slug) {
        const view = $('wiki-view');
        const r = await api(`/api/wiki/${encodeURIComponent(slug)}/`);
        const back = `<a href="#/wiki" class="inline-flex items-center gap-2 mb-4 px-4 py-2 rounded-lg bg-white shadow text-green-800 font-semibold hover:bg-green-100 border border-green-200">← All pages</a>`;
        if (r.status === 404) {
            setCanEdit(r.data.can_edit);
            view.innerHTML = `${back}<div class="card p-6"><h3 class="text-2xl font-bold">${esc(r.data.title)}</h3>
                <p class="text-gray-600 mt-2">This page doesn't exist yet.</p>
                ${r.data.can_edit ? '<button id="wiki-create" class="mt-4 px-4 py-2 rounded bg-green-600 text-white">Create it</button>' : ''}</div>`;
            const c = $('wiki-create');
            if (c) c.addEventListener('click', () => editWiki({ slug, title: r.data.title, body: '', exists: false }));
            return;
        }
        if (!r.ok) { view.innerHTML = `${back}<p class="text-red-700">${esc(r.data.message || 'Could not load the page.')}</p>`; return; }
        const p = r.data;
        setCanEdit(p.can_edit);
        const links = [
            ...p.backlinks.map(b => `<a href="#/wiki/${esc(b.slug)}" class="underline text-green-700">${esc(b.title)}</a>`),
            ...p.posts.map(b => `<a href="#/blog/${b.id}" class="underline text-green-700">📓 ${esc(b.title)}</a>`),
        ];
        view.innerHTML = `${back}
            <article class="card p-5 md:p-8">
                <div class="flex justify-between items-start gap-2 flex-wrap">
                    <h3 class="text-3xl font-bold">${esc(p.title)}</h3>
                    ${p.can_edit ? '<button id="wiki-edit" class="px-4 py-2 rounded border border-green-600 text-green-700 hover:bg-green-50">Edit</button>' : ''}
                </div>
                <div class="prose mt-4">${p.html || '<p class="text-gray-500">(empty page)</p>'}</div>
                <div class="mt-6 pt-4 border-t text-sm text-gray-600 space-y-1">
                    ${links.length ? `<div>Linked from: ${links.join(' · ')}</div>` : ''}
                    <div>Last edited ${new Date(p.updated_at).toLocaleString()}${p.updated_by ? ' by ' + byLine(p.updated_by) : ''}${p.revisions ? ` · <a href="#/wiki/${esc(p.slug)}/history" class="underline">${p.revisions} earlier version(s)</a>` : ''}</div>
                </div>
            </article>`;
        const e = $('wiki-edit');
        if (e) e.addEventListener('click', () => editWiki(p));
        window.scrollTo(0, 0);
    }

    async function showWikiHistory(slug) {
        const view = $('wiki-view');
        const r = await api(`/api/wiki/${encodeURIComponent(slug)}/history/`);
        const back = `<a href="#/wiki/${esc(slug)}" class="inline-flex items-center gap-2 mb-4 px-4 py-2 rounded-lg bg-white shadow text-green-800 font-semibold hover:bg-green-100 border border-green-200">← Back to page</a>`;
        if (!r.ok) { view.innerHTML = `${back}<p class="text-gray-600">No history.</p>`; return; }
        view.innerHTML = `${back}<div class="card p-5"><h3 class="text-xl font-bold mb-3">Earlier versions</h3>
            ${r.data.revisions.map(v => `<details class="border-b py-2"><summary class="cursor-pointer">${new Date(v.created_at).toLocaleString()} · ${esc(v.title)}${v.by ? ' · ' + esc(v.by) : ''}</summary>
                ${v.body != null ? `<pre class="whitespace-pre-wrap text-xs bg-gray-50 p-2 mt-2 rounded">${esc(v.body)}</pre>` : ''}</details>`).join('')}</div>`;
    }

    function editWiki(p) {
        openEditor({
            heading: p.exists === false ? 'New wiki page' : 'Edit wiki page',
            title: p.title,
            body: p.body,
            onSave: async v => {
                const r = await api(`/api/wiki/${encodeURIComponent(p.slug)}/`, { method: 'PUT', body: { title: v.title, body: v.body } });
                if (r.ok) {
                    if (location.hash === `#/wiki/${r.data.slug}`) showWikiPage(r.data.slug);
                    else location.hash = `#/wiki/${r.data.slug}`;
                }
                return { ok: r.ok, message: r.data.message };
            },
            onDelete: p.exists === false ? null : async () => {
                await api(`/api/wiki/${encodeURIComponent(p.slug)}/`, { method: 'DELETE' });
                location.hash = '#/wiki';
            },
        });
    }

    // ------------------------------------------------------------------ router

    function route() {
        const h = location.hash;
        if (!h.startsWith('#/')) {
            if (!h) { showSection('home'); loadClimate(); }
            return;  // e.g. #sensor-3 is handled by the sensors code
        }
        const [section, a, b] = h.slice(2).split('/');
        switch (section) {
            case 'almanac': {
                showSection('almanac');
                const today = localToday();
                if (a && /^\d{4}-\d{2}-\d{2}$/.test(a)) showAlmanac(a.slice(0, 7), a);
                else if (a && /^\d{4}-\d{2}$/.test(a)) showAlmanac(a, null);
                else showAlmanac(today.slice(0, 7), today);
                break;
            }
            case 'blog':
                showSection('blog');
                if (a) showBlogPost(a); else showBlogList();
                break;
            case 'wiki':
                showSection('wiki');
                if (a && b === 'history') showWikiHistory(a);
                else if (a) showWikiPage(decodeURIComponent(a));
                else showWikiIndex();
                break;
            case 'sensors':
                showSection('sensors');
                loadSensors();
                break;
            case 'config':
                showSection('config');
                loadNetworkConfig();
                break;
            case 'people':
                showSection('people');
                showPeople();
                break;
            default:
                showSection('home');
                loadClimate();
        }
    }


    // ------------------------------------------------------------------ people & logins

    let me = { authenticated: false };
    const avatarImg = (url, cls = 'w-6 h-6') => url ? `<img src="${esc(url)}" alt="" class="${cls} rounded-full inline-block align-middle">` : '';
    const byLine = a => a ? `<span class="inline-flex items-center gap-1">${avatarImg(a.avatar_url, 'w-5 h-5')}${esc(a.name)}</span>` : '';

    function renderNavUser() {
        const box = $('nav-user');
        if (me.authenticated && me.user) {
            box.innerHTML = `<button id="nav-me" type="button" title="You" class="flex items-center gap-2 rounded-full bg-white/15 hover:bg-white/25 pl-1 pr-3 py-1">
                ${avatarImg(me.user.avatar_url, 'w-8 h-8 bg-white')}<span class="text-sm font-semibold max-w-[8rem] truncate">${esc(me.user.display_name)}</span></button>`;
            $('nav-me').addEventListener('click', () => openAccount());
        } else {
            box.innerHTML = `<button id="nav-login" type="button" class="text-sm font-semibold rounded-full bg-white/15 hover:bg-white/25 px-4 py-1.5">Log in</button>`;
            $('nav-login').addEventListener('click', () => openLogin());
        }
        $('nav-people').classList.toggle('hidden', !me.is_staff);
    }

    async function refreshMe() {
        const r = await api('/api/me/');
        if (r.ok) me = r.data;
        renderNavUser();
        stagingBanner();
        return me;
    }

    function openLogin() {
        $('login-msg').textContent = '';
        $('login-pass').value = '';
        $('login-dlg').classList.remove('hidden');
        $('login-user').focus();
    }
    window.openLogin = openLogin;  // used by index.html (Config page)
    $('login-cancel').addEventListener('click', () => $('login-dlg').classList.add('hidden'));
    $('login-form').addEventListener('submit', async ev => {
        ev.preventDefault();
        const r = await api('/api/login/', { method: 'POST', body: { username: $('login-user').value, password: $('login-pass').value } });
        if (!r.ok) { $('login-msg').textContent = r.data.message || 'Could not log in.'; return; }
        me = r.data;
        $('login-dlg').classList.add('hidden');
        renderNavUser();
        if (me.user.must_change_password) openAccount(); else route();
    });

    let pickedAvatar = null;
    function openAccount() {
        if (!me.user) return;
        const welcome = me.user.must_change_password;
        pickedAvatar = me.user.avatar;
        $('acct-heading').textContent = welcome ? `Hello, ${me.user.display_name}!` : 'You';
        $('acct-welcome').classList.toggle('hidden', !welcome);
        $('acct-pw-legend').textContent = welcome ? 'Choose your password' : 'Change password (optional)';
        $('acct-cur').placeholder = welcome ? 'Temporary password you were given' : 'Current password';
        $('acct-cancel').classList.toggle('hidden', welcome);
        $('acct-name').value = me.user.display_name;
        ['acct-cur', 'acct-new', 'acct-new2'].forEach(id => { $(id).value = ''; });
        $('acct-msg').textContent = '';
        $('acct-avatars').innerHTML = (me.avatars || []).map(a => `
            <button type="button" data-avatar="${esc(a.slug)}" title="${esc(a.name)}" class="avatar-pick ${a.slug === pickedAvatar ? 'selected' : ''}">
                <img src="${esc(a.url)}" alt="${esc(a.name)}" class="w-full rounded-full"></button>`).join('');
        $('acct-avatars').querySelectorAll('[data-avatar]').forEach(b => b.addEventListener('click', () => {
            pickedAvatar = b.dataset.avatar;
            $('acct-avatars').querySelectorAll('.avatar-pick').forEach(x => x.classList.toggle('selected', x === b));
        }));
        $('account-dlg').classList.remove('hidden');
    }
    $('acct-cancel').addEventListener('click', () => $('account-dlg').classList.add('hidden'));
    $('acct-logout').addEventListener('click', async () => {
        const r = await api('/api/logout/', { method: 'POST' });
        if (r.ok) me = r.data;
        $('account-dlg').classList.add('hidden');
        renderNavUser();
        route();
    });
    $('account-form').addEventListener('submit', async ev => {
        ev.preventDefault();
        const msg = $('acct-msg');
        const cur = $('acct-cur').value, nw = $('acct-new').value, nw2 = $('acct-new2').value;
        const welcome = me.user.must_change_password;
        if ((welcome || nw || cur) && !(cur && nw)) { msg.textContent = 'Fill in the current and new password.'; return; }
        if (nw !== nw2) { msg.textContent = "The two new passwords don't match."; return; }
        let r = await api('/api/me/', { method: 'PUT', body: { display_name: $('acct-name').value, avatar: pickedAvatar } });
        if (!r.ok) { msg.textContent = r.data.message || 'Could not save.'; return; }
        me = r.data;
        if (nw) {
            r = await api('/api/me/password/', { method: 'POST', body: { current: cur, new: nw } });
            if (!r.ok) { msg.textContent = r.data.message || 'Could not change the password.'; renderNavUser(); return; }
            me = r.data;
        }
        $('account-dlg').classList.add('hidden');
        renderNavUser();
        route();
    });

    async function showPeople() {
        const view = $('people-view');
        const r = await api('/api/people/');
        if (!r.ok) {
            view.innerHTML = `<div class="card p-6 text-gray-700">Only admins can manage people.
                ${me.authenticated ? '' : '<button type="button" class="text-green-700 font-semibold underline" onclick="openLogin()">Log in</button>'}</div>`;
            return;
        }
        const rows = r.data.people.map(p => `
            <div class="flex flex-wrap items-center gap-3 p-4 border-b last:border-0 ${p.active ? '' : 'opacity-50'}">
                ${avatarImg(p.avatar_url, 'w-12 h-12')}
                <div class="flex-1 min-w-[10rem]">
                    <div class="font-semibold">${esc(p.display_name)} <span class="text-xs text-gray-500">@${esc(p.username)}</span></div>
                    <div class="text-xs text-gray-600">${p.role === 'admin' ? '🔑 Admin' : '🌱 Gardener'}${p.active ? '' : ' · disabled'}
                        · ${p.must_change_password ? 'hasn\'t logged in with their own password yet' : (p.last_login ? 'last seen ' + new Date(p.last_login).toLocaleDateString() : 'never logged in')}</div>
                </div>
                ${p.id === me.user.id ? '<span class="text-xs text-gray-500">(you)</span>' : `
                <div class="flex flex-wrap gap-2 text-sm">
                    <button data-pid="${p.id}" data-act="reset" class="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50">New temporary password</button>
                    <button data-pid="${p.id}" data-act="role" data-val="${p.role === 'admin' ? 'gardener' : 'admin'}" class="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50">Make ${p.role === 'admin' ? 'gardener' : 'admin'}</button>
                    <button data-pid="${p.id}" data-act="active" data-val="${p.active ? '' : '1'}" class="px-3 py-1 rounded border ${p.active ? 'border-red-300 text-red-700 hover:bg-red-50' : 'border-green-600 text-green-700 hover:bg-green-50'}">${p.active ? 'Disable' : 'Enable'}</button>
                </div>`}
            </div>`).join('');
        view.innerHTML = `
            <div id="people-secret"></div>
            <form id="people-add" class="card p-4 mb-6 flex flex-wrap gap-2 items-end">
                <label class="text-sm">Login name<br><input name="username" required pattern="[a-zA-Z0-9][a-zA-Z0-9_.\\-]{1,29}" autocapitalize="none" placeholder="e.g. corell" class="border border-gray-300 rounded-md p-2"></label>
                <label class="text-sm">Name shown<br><input name="display_name" placeholder="e.g. Corell" class="border border-gray-300 rounded-md p-2"></label>
                <label class="text-sm">Role<br><select name="role" class="border border-gray-300 rounded-md p-2"><option value="gardener">Gardener</option><option value="admin">Admin</option></select></label>
                <button class="px-4 py-2 rounded bg-green-600 text-white font-semibold hover:bg-green-700">+ Add person</button>
                <p id="people-msg" class="w-full text-sm text-red-700"></p>
            </form>
            <div class="card">${rows}</div>`;
        const showSecret = (p, pw) => {
            $('people-secret').innerHTML = `<div class="card p-4 mb-6 border-2 border-amber-300 bg-amber-50">
                <div class="font-semibold">Temporary password for ${esc(p.display_name)} (login <b>${esc(p.username)}</b>):</div>
                <div class="text-2xl font-mono my-2 select-all">${esc(pw)}</div>
                <div class="text-sm text-gray-700">Give it to them in person or by text. It's shown only this once; they'll choose their own password and avatar when they first log in.</div></div>`;
            window.scrollTo(0, 0);
        };
        $('people-add').addEventListener('submit', async ev => {
            ev.preventDefault();
            const f = new FormData(ev.target);
            const r2 = await api('/api/people/', { method: 'POST', body: Object.fromEntries(f) });
            if (!r2.ok) { $('people-msg').textContent = r2.data.message || 'Could not add.'; return; }
            await showPeople();
            showSecret(r2.data.person, r2.data.temporary_password);
        });
        view.querySelectorAll('[data-act]').forEach(b => b.addEventListener('click', async () => {
            const body = b.dataset.act === 'reset' ? { reset_password: true }
                : b.dataset.act === 'role' ? { role: b.dataset.val } : { active: !!b.dataset.val };
            if (b.dataset.act === 'reset' && !confirm('Give this person a new temporary password? Their old one stops working.')) return;
            const r2 = await api(`/api/people/${b.dataset.pid}/`, { method: 'PUT', body });
            if (!r2.ok) { alert(r2.data.message || 'Could not change that.'); return; }
            await showPeople();
            if (r2.data.temporary_password) showSecret(r2.data.person, r2.data.temporary_password);
        }));
    }

    // Staging copy (pve): say so on every page, with how fresh the real data is.
    function stagingBanner() {
        const st = me.staging;
        if (!st || !$('staging-banner').classList.contains('hidden')) return;
        const snap = st.snapshot;
        const el = document.getElementById('staging-banner');
        el.innerHTML = '<b>STAGING COPY</b>, not the greenhouse. ' + (snap
            ? `Real greenhouse data up to <b>${escapeHtml(new Date(snap.last_reading_at || snap.loaded_at).toLocaleString())}</b>` +
              ` (from ${escapeHtml(snap.source || 'the Pi')}); readings after that are simulated.`
            : 'All sensor readings are simulated; no data has been copied from the Pi yet.');
        el.classList.remove('hidden');
        if (!document.title.startsWith('[staging]')) document.title = '[staging] ' + document.title;
    }

    window.addEventListener('hashchange', route);
    route();
    refreshMe();
})();
