const API_URL = 'http://meme.192.168.0.220.nip.io';

let allTemplates = [];
let displayedCount = 0;
const LOAD_STEP = 15;

let currentTemplate = null;
let layers = [];
let activeLayerId = null;
let layerCounter = 1;

let isDragging = false;
let dragOffsetX = 0;
let dragOffsetY = 0;
let dragTargetId = null;

document.addEventListener('DOMContentLoaded', () => {
    loadTemplates();
    
    const slider = document.getElementById('template-slider');
    let isSliderDown = false;
    let startX;
    let scrollLeft;

    slider.addEventListener('mousedown', (e) => {
        isSliderDown = true;
        slider.classList.add('active');
        startX = e.pageX - slider.offsetLeft;
        scrollLeft = slider.scrollLeft;
    });
    slider.addEventListener('mouseleave', () => { isSliderDown = false; slider.classList.remove('active'); });
    slider.addEventListener('mouseup', () => { isSliderDown = false; slider.classList.remove('active'); });
    slider.addEventListener('mousemove', (e) => {
        if (!isSliderDown) return;
        e.preventDefault();
        const x = e.pageX - slider.offsetLeft;
        const walk = (x - startX) * 2; 
        slider.scrollLeft = scrollLeft - walk;
    });
    slider.addEventListener('wheel', (e) => {
        e.preventDefault();
        slider.scrollLeft += e.deltaY * 3;
    });

    document.addEventListener('mouseup', () => isDragging = false);
    document.addEventListener('mousemove', handleDragMove);

    document.getElementById('rocket-icon').onclick = (e) => {
        e.stopPropagation();
        const audio = document.getElementById('rocket-sound');
        if (audio) {
            audio.currentTime = 0;
            audio.play().catch(e => {});
        }
    };
});

async function loadTemplates() {
    const errorDiv = document.getElementById('error-message');
    const slider = document.getElementById('template-slider');
    try {
        const res = await fetch(`${API_URL}/templates`);
        if (!res.ok) throw new Error("Failed to fetch");
        allTemplates = await res.json();
        errorDiv.style.display = 'none';
        renderBatch(); 
    } catch (e) {
        slider.innerHTML = '';
        errorDiv.style.display = 'block';
        errorDiv.innerText = `API ERROR: Is backend running?`;
    }
}

function renderBatch() {
    const slider = document.getElementById('template-slider');
    if (displayedCount === 0) slider.innerHTML = '';
    const existingLoadMore = document.getElementById('load-more-card');
    if (existingLoadMore) existingLoadMore.remove();

    const nextBatch = allTemplates.slice(displayedCount, displayedCount + LOAD_STEP);
    nextBatch.forEach((tpl, idx) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'thumb-wrapper';
        wrapper.onclick = () => selectTemplate(tpl, wrapper);
        const img = document.createElement('img');
        img.src = tpl.url;
        img.className = 'template-thumb';
        wrapper.appendChild(img);
        slider.appendChild(wrapper);
        if (displayedCount === 0 && idx === 0) selectTemplate(tpl, wrapper);
    });

    displayedCount += nextBatch.length;
    if (displayedCount < allTemplates.length) {
        const loadMore = document.createElement('div');
        loadMore.id = 'load-more-card';
        loadMore.className = 'load-more-card';
        loadMore.innerHTML = "Load<br>More";
        loadMore.onclick = () => renderBatch();
        slider.appendChild(loadMore);
    }
}

function filterTemplates() {
    const query = document.getElementById('search-input').value.toLowerCase();
    const slider = document.getElementById('template-slider');
    slider.innerHTML = '';
    if (query.trim() === "") {
        displayedCount = 0;
        renderBatch();
        return;
    }
    const filtered = allTemplates.filter(t => t.name.toLowerCase().includes(query));
    if (filtered.length === 0) slider.innerHTML = '<p style="color: #aaa; padding: 20px;">No memes found :(</p>';
    else {
        filtered.forEach(tpl => {
            const wrapper = document.createElement('div');
            wrapper.className = 'thumb-wrapper';
            wrapper.onclick = () => selectTemplate(tpl, wrapper);
            const img = document.createElement('img');
            img.src = tpl.url;
            img.className = 'template-thumb';
            wrapper.appendChild(img);
            slider.appendChild(wrapper);
        });
    }
}

function selectTemplate(tpl, wrapperEl) {
    currentTemplate = tpl;
    document.querySelectorAll('.thumb-wrapper').forEach(el => el.classList.remove('selected'));
    if(wrapperEl) wrapperEl.classList.add('selected');

    const mainImg = document.getElementById('meme-image');
    mainImg.src = tpl.url;
    
    layers.forEach(l => l.element.remove());
    layers = [];
    activeLayerId = null;
    layerCounter = 1;
    updateControlsUI();
    setTimeout(() => { addNewLayer("YOUR TEXT"); }, 200);
}

function addNewLayer(textOverride = null) {
    const id = Date.now() + Math.random();
    let text = textOverride ? textOverride : `YOUR TEXT ${++layerCounter}`;

    const container = document.getElementById('meme-canvas');
    const el = document.createElement('div');
    el.className = 'meme-text-layer';
    el.innerText = text;
    el.style.fontSize = '50px';
    el.style.color = '#ffffff';
    el.style.webkitTextStroke = '2px #000000'; 
    el.style.left = '20px';
    el.style.top = '20px';

    el.onmousedown = (e) => {
        setActiveLayer(id);
        isDragging = true;
        dragTargetId = id;
        const rect = el.getBoundingClientRect();
        dragOffsetX = e.clientX - rect.left;
        dragOffsetY = e.clientY - rect.top;
        e.stopPropagation();
    };

    container.appendChild(el);
    layers.push({ id, text, size: 50, color: '#ffffff', opacity: 100, borderColor: '#000000', element: el });
    setActiveLayer(id);
}

function handleDragMove(e) {
    if (!isDragging || !dragTargetId) return;
    const layer = layers.find(l => l.id === dragTargetId);
    if (!layer) return;
    
    const container = document.getElementById('meme-canvas');
    const containerRect = container.getBoundingClientRect();
    
    let newX = e.clientX - containerRect.left - dragOffsetX;
    let newY = e.clientY - containerRect.top - dragOffsetY;

    const maxX = container.offsetWidth - layer.element.offsetWidth;
    const maxY = container.offsetHeight - layer.element.offsetHeight;

    if (newX < 0) newX = 0;
    if (newX > maxX) newX = maxX;
    if (newY < 0) newY = 0;
    if (newY > maxY) newY = maxY;

    layer.element.style.left = newX + 'px';
    layer.element.style.top = newY + 'px';
}

function setActiveLayer(id) {
    activeLayerId = id;
    document.querySelectorAll('.meme-text-layer').forEach(el => el.classList.remove('active'));
    const layer = layers.find(l => l.id === id);
    if (layer) {
        layer.element.classList.add('active');
        document.getElementById('ctrl-text').value = layer.text;
        document.getElementById('ctrl-size').value = layer.size;
        document.getElementById('ctrl-color').value = layer.color;
        document.getElementById('ctrl-opacity').value = layer.opacity;
        document.getElementById('ctrl-border-color').value = layer.borderColor;
        const borderEnabled = document.getElementById('textBorder').checked;
        document.getElementById('ctrl-border-color').disabled = !borderEnabled;
    }
    updateControlsUI();
}

function updateActiveLayer(prop, value) {
    if (!activeLayerId) return;
    const layer = layers.find(l => l.id === activeLayerId);
    if (layer) {
        if (prop === 'text') { layer.text = value; layer.element.innerText = value; }
        if (prop === 'size') { layer.size = value; layer.element.style.fontSize = value + 'px'; }
        if (prop === 'color') { layer.color = value; layer.element.style.color = value; }
        if (prop === 'opacity') { layer.opacity = value; layer.element.style.opacity = value / 100; }
        if (prop === 'border') { 
            layer.borderColor = value; 
            if (document.getElementById('textBorder').checked) layer.element.style.webkitTextStroke = `2px ${value}`;
        }
    }
}

function toggleGlobalBorder(enabled) {
    const borderColorInput = document.getElementById('ctrl-border-color');
    borderColorInput.disabled = !enabled;
    const borderColor = borderColorInput.value;
    document.querySelectorAll('.meme-text-layer').forEach(el => {
        el.style.webkitTextStroke = enabled ? `2px ${borderColor}` : '0px';
    });
}

function deleteActiveLayer() {
    if (!activeLayerId) return;
    const idx = layers.findIndex(l => l.id === activeLayerId);
    if (idx > -1) {
        layers[idx].element.remove();
        layers.splice(idx, 1);
        activeLayerId = null;
        document.getElementById('ctrl-text').value = '';
    }
}

function updateControlsUI() {
    const group = document.getElementById('layer-controls');
    if (activeLayerId) group.classList.add('enabled');
    else group.classList.remove('enabled');
}

async function generateMeme() {
    if (!currentTemplate) return;

    const displayedImg = document.getElementById('meme-image');
    if (!displayedImg.complete || displayedImg.naturalWidth === 0) {
        alert("Image not loaded yet."); return;
    }
    
    const elevatorMusic = document.getElementById('elevator-sound');
    if (elevatorMusic) {
        elevatorMusic.currentTime = 0;
        elevatorMusic.play().catch(e => {});
    }

    const scaleFactor = displayedImg.naturalWidth / displayedImg.offsetWidth;
    const imgRect = displayedImg.getBoundingClientRect();

    const payloadLayers = layers.map(l => {
        const elRect = l.element.getBoundingClientRect();
        const x = elRect.left - imgRect.left;
        const y = elRect.top - imgRect.top;

        return {
            text: l.text,
            color: l.color,
            size: Math.round(l.size * scaleFactor * 0.8), 
            x_pos: Math.round(x * scaleFactor),
            y_pos: Math.round(y * scaleFactor),
            opacity: parseInt(l.opacity),
            border_color_hex: l.borderColor
        };
    });

    const overlay = document.getElementById('result-overlay');
    const loader = document.getElementById('loader');
    const img = document.getElementById('result-img');
    const status = document.getElementById('status-text');

    overlay.style.display = 'flex';
    loader.style.display = 'block';
    img.style.display = 'none';
    status.innerText = "Processing...";

    try {
        const res = await fetch(`${API_URL}/memes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                template_id: currentTemplate.id,
                text_border: document.getElementById('textBorder').checked,
                text_lines: payloadLayers
            })
        });
        const data = await res.json();
        pollStatus(data.task_id);
    } catch (e) {
        status.innerText = "Error: " + e.message;
        loader.style.display = 'none';
        if (elevatorMusic) elevatorMusic.pause();
    }
}

function pollStatus(taskId) {
    const status = document.getElementById('status-text');
    const img = document.getElementById('result-img');
    const loader = document.getElementById('loader');
    const elevatorMusic = document.getElementById('elevator-sound');

    const interval = setInterval(async () => {
        try {
            const res = await fetch(`${API_URL}/memes/${taskId}`);
            const data = await res.json();
            if (data.status === 'Done') {
                clearInterval(interval);
                loader.style.display = 'none';
                status.innerText = "Done!";
                img.src = data.url;
                img.style.display = 'block';
                if (elevatorMusic) {
                    elevatorMusic.pause();
                    elevatorMusic.currentTime = 0;
                }
            } else if (data.status === 'Failed') {
                clearInterval(interval);
                status.innerText = "Generation Failed";
                loader.style.display = 'none';
                if (elevatorMusic) elevatorMusic.pause();
            }
        } catch (e) { console.error(e); }
    }, 1000);
}

function activateRickRoll() {
    window.open("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "_blank");
}

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
    const elevatorMusic = document.getElementById('elevator-sound');
    if (elevatorMusic) {
        elevatorMusic.pause();
        elevatorMusic.currentTime = 0;
    }
}
