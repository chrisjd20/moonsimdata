// Terrain Overlay Editor - Canvas Editor Logic

class TerrainEditor {
    constructor() {
        // Canvas elements
        this.backgroundCanvas = document.getElementById('backgroundCanvas');
        this.objectCanvas = document.getElementById('objectCanvas');
        this.overlayCanvas = document.getElementById('overlayCanvas');
        this.cursorCanvas = document.getElementById('cursorCanvas');
        
        this.bgCtx = this.backgroundCanvas.getContext('2d');
        this.objCtx = this.objectCanvas.getContext('2d');
        this.overlayCtx = this.overlayCanvas.getContext('2d');
        this.cursorCtx = this.cursorCanvas.getContext('2d');
        
        // Temporary canvas for non-compounding strokes
        this.tempCanvas = document.createElement('canvas');
        this.tempCtx = this.tempCanvas.getContext('2d');
        
        // State
        this.currentItem = null;
        this.currentItemType = 'objects';
        this.itemImage = null;
        this.objects = [];
        this.backgrounds = [];
        this.config = { objects: {}, backgrounds: {} };
        
        // Tool state
        this.currentTool = 'brush';
        this.brushSize = 20;
        this.currentColor = '#FF6B6B';
        this.overlayOpacity = 0.3;  // Default 30%
        this.isDrawing = false;
        this.lastX = 0;
        this.lastY = 0;
        this.objectVisible = true;
        
        // Shape tool state
        this.shapeStartX = 0;
        this.shapeStartY = 0;
        this.shiftPressed = false;
        
        // Overlay dimensions
        this.overlayWidth = 400;
        this.overlayHeight = 400;
        
        // Object properties
        this.isFlying = false;
        
        // Undo/Redo history
        this.history = [];
        this.historyIndex = -1;
        this.maxHistory = 50;
        
        // Track used colors for config
        this.usedColors = new Set();
        
        // Extended color palette - pleasing, diverse colors
        this.highlightColors = [
            // Warm tones
            '#FF6B6B', '#FF8E72', '#FFA94D', '#FFD93D',
            // Cool tones  
            '#6BCB77', '#4ECDC4', '#45B7D1', '#5E60CE',
            // Purple/Pink
            '#9B5DE5', '#F15BB5', '#FF70A6', '#E056FD',
            // Earth tones
            '#D4A574', '#A8D8B9', '#98C1D9', '#B8B8D1',
            // Neon accents
            '#00F5D4', '#00BBF9', '#FEE440', '#F72585',
            // Pastels
            '#FFEAA7', '#DFE6E9', '#A29BFE', '#FD79A8',
            // Rich colors
            '#E17055', '#00CEC9', '#6C5CE7', '#FDCB6E',
        ];
        
        this.init();
    }
    
    async init() {
        this.setupColorPalette();
        this.setupEventListeners();
        await Promise.all([
            this.loadObjects(),
            this.loadBackgrounds(),
            this.loadConfig()
        ]);
        this.updateAssetGrid();
    }
    
    setupColorPalette() {
        const palette = document.getElementById('colorPalette');
        palette.innerHTML = '';
        
        this.highlightColors.forEach((color, index) => {
            const swatch = document.createElement('div');
            swatch.className = 'color-swatch' + (index === 0 ? ' selected' : '');
            swatch.style.backgroundColor = color;
            swatch.dataset.color = color;
            swatch.addEventListener('click', () => this.selectColor(color, swatch));
            palette.appendChild(swatch);
        });
        
        this.currentColor = this.highlightColors[0];
    }
    
    selectColor(color, swatch) {
        document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('selected'));
        swatch.classList.add('selected');
        this.currentColor = color;
    }
    
    setupEventListeners() {
        // Tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });

        // Tool buttons
        document.querySelectorAll('.tool-btn[data-tool]').forEach(btn => {
            btn.addEventListener('click', () => this.selectTool(btn.dataset.tool));
        });
        
        // Brush size
        const brushSizeSlider = document.getElementById('brushSize');
        brushSizeSlider.addEventListener('input', (e) => {
            this.brushSize = parseInt(e.target.value);
            document.getElementById('brushSizeValue').textContent = this.brushSize;
        });
        
        // Overlay opacity - slider
        const overlayOpacitySlider = document.getElementById('overlayOpacity');
        const overlayOpacityInput = document.getElementById('overlayOpacityInput');
        
        if (overlayOpacitySlider) {
            overlayOpacitySlider.addEventListener('input', (e) => {
                this.overlayOpacity = parseInt(e.target.value) / 100;
                if (overlayOpacityInput) overlayOpacityInput.value = e.target.value;
                this.overlayCanvas.style.opacity = this.overlayOpacity;
            });
        }
        
        // Overlay opacity - input
        if (overlayOpacityInput) {
            overlayOpacityInput.addEventListener('change', (e) => {
                let val = parseInt(e.target.value) || 30;
                val = Math.max(5, Math.min(100, val));
                e.target.value = val;
                this.overlayOpacity = val / 100;
                if (overlayOpacitySlider) overlayOpacitySlider.value = val;
                this.overlayCanvas.style.opacity = this.overlayOpacity;
            });
        }
        
        // Overlay width
        const overlayWidthInput = document.getElementById('overlayWidth');
        if (overlayWidthInput) {
            overlayWidthInput.addEventListener('change', (e) => {
                this.overlayWidth = parseInt(e.target.value) || 400;
                if (this.currentItem) this.setupCanvas();
            });
        }
        
        // Overlay height
        const overlayHeightInput = document.getElementById('overlayHeight');
        if (overlayHeightInput) {
            overlayHeightInput.addEventListener('change', (e) => {
                this.overlayHeight = parseInt(e.target.value) || 400;
                if (this.currentItem) this.setupCanvas();
            });
        }
        
        // Match object size button
        const matchObjectBtn = document.getElementById('matchObjectSize');
        if (matchObjectBtn) {
            matchObjectBtn.addEventListener('click', () => this.matchObjectSize());
        }
        
        // Add padding button
        const addPaddingBtn = document.getElementById('addPadding');
        if (addPaddingBtn) {
            addPaddingBtn.addEventListener('click', () => this.addPadding());
        }
        
        // Auto fill button
        const autoFillBtn = document.getElementById('autoFillBtn');
        if (autoFillBtn) {
            autoFillBtn.addEventListener('click', () => this.autoFillObject());
        }
        
        // Clear overlay button
        document.getElementById('clearOverlay').addEventListener('click', () => {
            this.saveToHistory();
            this.clearOverlay();
        });
        
        // Toggle object visibility
        document.getElementById('toggleObject').addEventListener('click', () => this.toggleObjectVisibility());
        
        // Undo/Redo buttons
        document.getElementById('undoBtn').addEventListener('click', () => this.undo());
        document.getElementById('redoBtn').addEventListener('click', () => this.redo());
        
        // Save button
        document.getElementById('saveBtn').addEventListener('click', () => this.saveOverlay());
        
        // Search filter
        document.getElementById('assetSearch').addEventListener('input', (e) => {
            this.filterAssets(e.target.value);
        });
        
        // Flying toggle
        document.getElementById('flyingToggle').addEventListener('click', () => this.toggleFlying());
        
        // Canvas drawing events
        this.overlayCanvas.addEventListener('mousedown', (e) => this.startDrawing(e));
        this.overlayCanvas.addEventListener('mousemove', (e) => this.draw(e));
        this.overlayCanvas.addEventListener('mouseup', (e) => this.stopDrawing(e));
        this.overlayCanvas.addEventListener('mouseleave', (e) => this.stopDrawing(e));
        
        // Cursor preview
        this.overlayCanvas.addEventListener('mousemove', (e) => this.updateCursor(e));
        this.overlayCanvas.addEventListener('mouseleave', () => this.clearCursor());
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
        document.addEventListener('keyup', (e) => {
            if (e.key === 'Shift') this.shiftPressed = false;
        });
    }
    
    selectTool(tool) {
        this.currentTool = tool;
        document.querySelectorAll('.tool-btn[data-tool]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tool === tool);
        });
    }
    
    handleKeyboard(e) {
        // Shift key for aspect ratio lock
        if (e.key === 'Shift') {
            this.shiftPressed = true;
        }
        
        // Undo/Redo
        if (e.ctrlKey || e.metaKey) {
            if (e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                this.undo();
                return;
            }
            if (e.key === 'y' || (e.key === 'z' && e.shiftKey)) {
                e.preventDefault();
                this.redo();
                return;
            }
        }
        
        if (e.target.tagName === 'INPUT') return;
        
        switch(e.key.toLowerCase()) {
            case 'b':
                this.selectTool('brush');
                break;
            case 'g':
                this.selectTool('bucket');
                break;
            case 'e':
                this.selectTool('eraser');
                break;
            case 'r':
                this.selectTool('rectangle');
                break;
            case 'o':
                this.selectTool('ellipse');
                break;
            case '[':
                this.brushSize = Math.max(1, this.brushSize - 5);
                document.getElementById('brushSize').value = this.brushSize;
                document.getElementById('brushSizeValue').textContent = this.brushSize;
                break;
            case ']':
                this.brushSize = Math.min(100, this.brushSize + 5);
                document.getElementById('brushSize').value = this.brushSize;
                document.getElementById('brushSizeValue').textContent = this.brushSize;
                break;
        }
    }
    
    // History management
    saveToHistory() {
        if (!this.overlayCanvas.width) return;
        
        // Remove any redo states
        this.history = this.history.slice(0, this.historyIndex + 1);
        
        // Save current state
        const imageData = this.overlayCtx.getImageData(
            0, 0, this.overlayCanvas.width, this.overlayCanvas.height
        );
        this.history.push(imageData);
        
        // Limit history size
        if (this.history.length > this.maxHistory) {
            this.history.shift();
        }
        
        this.historyIndex = this.history.length - 1;
    }
    
    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            this.overlayCtx.putImageData(this.history[this.historyIndex], 0, 0);
        } else if (this.historyIndex === 0 && this.history.length > 0) {
            // Clear to initial state
            this.overlayCtx.clearRect(0, 0, this.overlayCanvas.width, this.overlayCanvas.height);
            this.historyIndex = -1;
        }
    }
    
    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            this.overlayCtx.putImageData(this.history[this.historyIndex], 0, 0);
        }
    }
    
    async loadObjects() {
        try {
            const response = await fetch('/api/objects');
            this.objects = await response.json();
        } catch (error) {
            console.error('Failed to load objects:', error);
            this.showToast('Failed to load objects', 'error');
        }
    }
    
    async loadBackgrounds() {
        try {
            const response = await fetch('/api/backgrounds');
            this.backgrounds = await response.json();
        } catch (error) {
            console.error('Failed to load backgrounds:', error);
            this.showToast('Failed to load backgrounds', 'error');
        }
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            this.config = await response.json();
            if (!this.config.objects) this.config.objects = {};
            if (!this.config.backgrounds) this.config.backgrounds = {};
        } catch (error) {
            console.error('Failed to load config:', error);
            this.config = { objects: {}, backgrounds: {} };
        }
    }
    
    switchTab(tabName) {
        this.currentItemType = tabName;
        
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });
        
        this.updateAssetGrid();
    }
    
    getCurrentAssets() {
        return this.currentItemType === 'objects' ? this.objects : this.backgrounds;
    }
    
    updateAssetGrid() {
        const grid = document.getElementById('assetGrid');
        grid.innerHTML = '';
        
        const assets = this.getCurrentAssets();
        const configSection = this.config[this.currentItemType] || {};
        
        document.getElementById('assetCount').textContent = assets.length;
        
        assets.forEach(asset => {
            const item = document.createElement('div');
            item.className = 'asset-item';
            
            if (configSection[asset.name]?.overlay) {
                item.classList.add('has-overlay');
            }
            
            item.innerHTML = `
                <img src="${asset.path}" alt="${asset.name}" loading="lazy">
                <span class="asset-name">${asset.name}</span>
            `;
            
            item.addEventListener('click', () => this.selectAsset(asset, item));
            grid.appendChild(item);
        });
    }
    
    filterAssets(query) {
        const items = document.querySelectorAll('.asset-item');
        const lowerQuery = query.toLowerCase();
        const assets = this.getCurrentAssets();
        
        items.forEach((item, index) => {
            if (index < assets.length) {
                const name = assets[index].name.toLowerCase();
                item.style.display = name.includes(lowerQuery) ? '' : 'none';
            }
        });
    }
    
    async selectAsset(asset, element) {
        document.querySelectorAll('.asset-item').forEach(el => el.classList.remove('selected'));
        element.classList.add('selected');
        
        this.currentItem = asset;
        this.usedColors = new Set();
        this.history = [];
        this.historyIndex = -1;
        
        this.itemImage = new Image();
        this.itemImage.crossOrigin = 'anonymous';
        
        await new Promise((resolve, reject) => {
            this.itemImage.onload = resolve;
            this.itemImage.onerror = reject;
            this.itemImage.src = asset.path;
        });
        
        const itemConfig = this.config[this.currentItemType][asset.name] || {};
        this.overlayWidth = itemConfig.overlayWidth || this.itemImage.width + 100;
        this.overlayHeight = itemConfig.overlayHeight || this.itemImage.height + 100;
        this.isFlying = itemConfig.flying || false;
        
        document.getElementById('overlayWidth').value = this.overlayWidth;
        document.getElementById('overlayHeight').value = this.overlayHeight;
        this.updateFlyingToggle();
        
        this.setupCanvas();
        
        if (itemConfig.overlay) {
            await this.loadExistingOverlay(itemConfig.overlay);
        }
        
        this.updateItemInfo();
        document.getElementById('emptyState').classList.add('hidden');
    }
    
    setupCanvas() {
        if (!this.itemImage) return;
        
        const width = this.overlayWidth;
        const height = this.overlayHeight;
        
        [this.backgroundCanvas, this.objectCanvas, this.overlayCanvas, this.cursorCanvas].forEach(canvas => {
            canvas.width = width;
            canvas.height = height;
            canvas.style.width = width + 'px';
            canvas.style.height = height + 'px';
        });
        
        // Setup temp canvas
        this.tempCanvas.width = width;
        this.tempCanvas.height = height;
        
        const container = document.getElementById('canvasContainer');
        container.style.width = width + 'px';
        container.style.height = height + 'px';
        
        // Apply layer opacity
        this.overlayCanvas.style.opacity = this.overlayOpacity;
        
        this.drawCheckerboard();
        this.redrawCanvas();
        this.overlayCtx.clearRect(0, 0, width, height);
        
        // Apply current overlay opacity
        this.overlayCanvas.style.opacity = this.overlayOpacity;
        
        document.getElementById('canvasSize').textContent = `${width}×${height}`;
    }
    
    drawCheckerboard() {
        const size = 10;
        const width = this.backgroundCanvas.width;
        const height = this.backgroundCanvas.height;
        
        this.bgCtx.fillStyle = '#2a2a32';
        this.bgCtx.fillRect(0, 0, width, height);
        
        this.bgCtx.fillStyle = '#222228';
        for (let y = 0; y < height; y += size) {
            for (let x = 0; x < width; x += size) {
                if ((x / size + y / size) % 2 === 0) {
                    this.bgCtx.fillRect(x, y, size, size);
                }
            }
        }
    }
    
    redrawCanvas() {
        if (!this.itemImage) return;
        
        const width = this.objectCanvas.width;
        const height = this.objectCanvas.height;
        
        this.objCtx.clearRect(0, 0, width, height);
        
        if (!this.objectVisible) return;
        
        // Center the object in the overlay
        const x = (width - this.itemImage.width) / 2;
        const y = (height - this.itemImage.height) / 2;
        
        this.objCtx.drawImage(this.itemImage, x, y);
    }
    
    async loadExistingOverlay(overlayFilename) {
        try {
            const overlayImg = new Image();
            overlayImg.crossOrigin = 'anonymous';
            
            await new Promise((resolve, reject) => {
                overlayImg.onload = resolve;
                overlayImg.onerror = reject;
                overlayImg.src = `/api/image/overlays/${overlayFilename}`;
            });
            
            const x = (this.overlayCanvas.width - overlayImg.width) / 2;
            const y = (this.overlayCanvas.height - overlayImg.height) / 2;
            this.overlayCtx.drawImage(overlayImg, x, y);
            
            // Save initial state to history
            this.saveToHistory();
            
        } catch (error) {
            console.log('No existing overlay found');
        }
    }
    
    updateItemInfo() {
        if (!this.currentItem || !this.itemImage) return;
        
        const typeLabel = this.currentItemType === 'objects' ? 'Object' : 'Background';
        
        document.getElementById('itemInfo').textContent = this.currentItem.name;
        document.getElementById('infoType').textContent = typeLabel;
        document.getElementById('infoName').textContent = this.currentItem.name;
        document.getElementById('infoDimensions').textContent = 
            `${this.itemImage.width}×${this.itemImage.height}`;
        
        const hasOverlay = this.config[this.currentItemType][this.currentItem.name]?.overlay;
        document.getElementById('infoOverlay').textContent = hasOverlay ? 'Yes' : 'No';
    }
    
    toggleObjectVisibility() {
        this.objectVisible = !this.objectVisible;
        this.redrawCanvas();
    }
    
    toggleFlying() {
        this.isFlying = !this.isFlying;
        this.updateFlyingToggle();
    }
    
    updateFlyingToggle() {
        const btn = document.getElementById('flyingToggle');
        btn.dataset.active = this.isFlying ? 'true' : 'false';
    }
    
    matchObjectSize() {
        if (!this.itemImage) return;
        this.overlayWidth = this.itemImage.width;
        this.overlayHeight = this.itemImage.height;
        document.getElementById('overlayWidth').value = this.overlayWidth;
        document.getElementById('overlayHeight').value = this.overlayHeight;
        this.setupCanvas();
    }
    
    addPadding() {
        if (!this.itemImage) return;
        this.overlayWidth = this.itemImage.width + 200;  // 100px each side
        this.overlayHeight = this.itemImage.height + 200;
        document.getElementById('overlayWidth').value = this.overlayWidth;
        document.getElementById('overlayHeight').value = this.overlayHeight;
        this.setupCanvas();
    }
    
    autoFillObject() {
        if (!this.itemImage) {
            this.showToast('No object selected', 'error');
            return;
        }
        
        this.saveToHistory();
        
        // Get threshold from input (default 50%)
        const thresholdInput = document.getElementById('autoFillThreshold');
        const threshold = (parseInt(thresholdInput?.value) || 50) * 2.55; // Convert % to 0-255
        
        // Create a temp canvas to read the object image pixels
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = this.itemImage.width;
        tempCanvas.height = this.itemImage.height;
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.drawImage(this.itemImage, 0, 0);
        
        const imageData = tempCtx.getImageData(0, 0, tempCanvas.width, tempCanvas.height);
        const pixels = imageData.data;
        
        // Calculate offset to center object in overlay
        const offsetX = (this.overlayWidth - this.itemImage.width) / 2;
        const offsetY = (this.overlayHeight - this.itemImage.height) / 2;
        
        // Parse current color
        const color = this.hexToRgba(this.currentColor, 1.0);
        const colorMatch = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        const r = parseInt(colorMatch[1]);
        const g = parseInt(colorMatch[2]);
        const b = parseInt(colorMatch[3]);
        
        // Get overlay image data
        const overlayData = this.overlayCtx.getImageData(0, 0, this.overlayWidth, this.overlayHeight);
        const overlayPixels = overlayData.data;
        
        // Fill overlay pixels where object has opacity >= threshold
        for (let y = 0; y < this.itemImage.height; y++) {
            for (let x = 0; x < this.itemImage.width; x++) {
                const srcIdx = (y * this.itemImage.width + x) * 4;
                const alpha = pixels[srcIdx + 3];
                
                if (alpha >= threshold) {
                    // Calculate position in overlay
                    const destX = Math.floor(offsetX + x);
                    const destY = Math.floor(offsetY + y);
                    
                    if (destX >= 0 && destX < this.overlayWidth && destY >= 0 && destY < this.overlayHeight) {
                        const destIdx = (destY * this.overlayWidth + destX) * 4;
                        overlayPixels[destIdx] = r;
                        overlayPixels[destIdx + 1] = g;
                        overlayPixels[destIdx + 2] = b;
                        overlayPixels[destIdx + 3] = 255;
                    }
                }
            }
        }
        
        this.overlayCtx.putImageData(overlayData, 0, 0);
        this.usedColors.add(this.currentColor);
        this.showToast('Auto fill complete', 'success');
    }
    
    clearOverlay() {
        if (!this.overlayCanvas) return;
        this.overlayCtx.clearRect(0, 0, this.overlayCanvas.width, this.overlayCanvas.height);
        this.usedColors = new Set();
    }
    
    getCanvasCoords(e) {
        const rect = this.overlayCanvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }
    
    startDrawing(e) {
        if (!this.currentItem) return;
        
        this.isDrawing = true;
        const coords = this.getCanvasCoords(e);
        this.lastX = coords.x;
        this.lastY = coords.y;
        this.shapeStartX = coords.x;
        this.shapeStartY = coords.y;
        
        // Save state before drawing
        this.saveToHistory();
        
        if (this.currentTool === 'bucket') {
            this.bucketFill(coords.x, coords.y);
            this.isDrawing = false;
        } else if (this.currentTool === 'brush' || this.currentTool === 'eraser') {
            // Clear temp canvas and start stroke
            this.tempCtx.clearRect(0, 0, this.tempCanvas.width, this.tempCanvas.height);
            this.drawBrushStroke(coords.x, coords.y, coords.x, coords.y);
        }
    }
    
    draw(e) {
        if (!this.isDrawing || !this.currentItem) return;
        
        const coords = this.getCanvasCoords(e);
        
        if (this.currentTool === 'brush' || this.currentTool === 'eraser') {
            this.drawBrushStroke(this.lastX, this.lastY, coords.x, coords.y);
            this.lastX = coords.x;
            this.lastY = coords.y;
        } else if (this.currentTool === 'rectangle' || this.currentTool === 'ellipse') {
            this.previewShape(coords.x, coords.y);
        }
    }
    
    drawBrushStroke(fromX, fromY, toX, toY) {
        this.overlayCtx.beginPath();
        this.overlayCtx.lineCap = 'round';
        this.overlayCtx.lineJoin = 'round';
        this.overlayCtx.lineWidth = this.brushSize;
        
        if (this.currentTool === 'eraser') {
            // Eraser removes pixels completely
            this.overlayCtx.globalCompositeOperation = 'destination-out';
            this.overlayCtx.strokeStyle = 'rgba(0,0,0,1)';
        } else {
            // Brush paints solid color (no compounding - binary on/off)
            this.overlayCtx.globalCompositeOperation = 'source-over';
            this.overlayCtx.strokeStyle = this.currentColor;
            this.usedColors.add(this.currentColor);
        }
        
        this.overlayCtx.moveTo(fromX, fromY);
        this.overlayCtx.lineTo(toX, toY);
        this.overlayCtx.stroke();
        this.overlayCtx.globalCompositeOperation = 'source-over';
    }
    
    previewShape(currentX, currentY) {
        // Restore from history to preview
        if (this.historyIndex >= 0) {
            this.overlayCtx.putImageData(this.history[this.historyIndex], 0, 0);
        } else {
            this.overlayCtx.clearRect(0, 0, this.overlayCanvas.width, this.overlayCanvas.height);
        }
        
        let width = currentX - this.shapeStartX;
        let height = currentY - this.shapeStartY;
        
        // Shift key locks aspect ratio (1:1)
        if (this.shiftPressed) {
            const size = Math.max(Math.abs(width), Math.abs(height));
            width = width >= 0 ? size : -size;
            height = height >= 0 ? size : -size;
        }
        
        // Draw solid color shape (no opacity compounding)
        this.overlayCtx.fillStyle = this.currentColor;
        
        if (this.currentTool === 'rectangle') {
            this.overlayCtx.fillRect(this.shapeStartX, this.shapeStartY, width, height);
        } else if (this.currentTool === 'ellipse') {
            const centerX = this.shapeStartX + width / 2;
            const centerY = this.shapeStartY + height / 2;
            const radiusX = Math.abs(width / 2);
            const radiusY = Math.abs(height / 2);
            
            this.overlayCtx.beginPath();
            this.overlayCtx.ellipse(centerX, centerY, radiusX, radiusY, 0, 0, Math.PI * 2);
            this.overlayCtx.fill();
        }
    }
    
    stopDrawing(e) {
        if (!this.isDrawing) return;
        
        if (this.currentTool === 'rectangle' || this.currentTool === 'ellipse') {
            // Shape is already drawn in preview, just finalize
            const coords = this.getCanvasCoords(e);
            this.previewShape(coords.x, coords.y);
            this.usedColors.add(this.currentColor);
        }
        
        this.isDrawing = false;
        
        // Save state after drawing
        this.saveToHistory();
    }
    
    bucketFill(startX, startY) {
        const width = this.overlayCanvas.width;
        const height = this.overlayCanvas.height;
        const imageData = this.overlayCtx.getImageData(0, 0, width, height);
        const data = imageData.data;
        
        const startPos = (Math.floor(startY) * width + Math.floor(startX)) * 4;
        const startR = data[startPos];
        const startG = data[startPos + 1];
        const startB = data[startPos + 2];
        const startA = data[startPos + 3];
        
        // Fill with solid color (full opacity)
        const fillColor = this.hexToRgbaValues(this.currentColor, 1.0);
        
        // Don't fill if clicking on same color
        if (startR === fillColor.r && startG === fillColor.g && 
            startB === fillColor.b && startA === 255) {
            return;
        }
        
        const stack = [[Math.floor(startX), Math.floor(startY)]];
        const visited = new Set();
        const tolerance = 30;
        
        while (stack.length > 0) {
            const [x, y] = stack.pop();
            const key = `${x},${y}`;
            
            if (visited.has(key) || x < 0 || x >= width || y < 0 || y >= height) {
                continue;
            }
            
            const pos = (y * width + x) * 4;
            const r = data[pos];
            const g = data[pos + 1];
            const b = data[pos + 2];
            const a = data[pos + 3];
            
            if (Math.abs(r - startR) > tolerance || 
                Math.abs(g - startG) > tolerance ||
                Math.abs(b - startB) > tolerance ||
                Math.abs(a - startA) > tolerance) {
                continue;
            }
            
            visited.add(key);
            
            // Fill with solid color (255 alpha)
            data[pos] = fillColor.r;
            data[pos + 1] = fillColor.g;
            data[pos + 2] = fillColor.b;
            data[pos + 3] = 255;
            
            stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
        }
        
        this.overlayCtx.putImageData(imageData, 0, 0);
        this.usedColors.add(this.currentColor);
    }
    
    updateCursor(e) {
        if (!this.currentItem) return;
        
        const coords = this.getCanvasCoords(e);
        const ctx = this.cursorCtx;
        const width = this.cursorCanvas.width;
        const height = this.cursorCanvas.height;
        
        ctx.clearRect(0, 0, width, height);
        
        if (this.currentTool === 'brush' || this.currentTool === 'eraser') {
            ctx.beginPath();
            ctx.arc(coords.x, coords.y, this.brushSize / 2, 0, Math.PI * 2);
            ctx.strokeStyle = this.currentTool === 'eraser' ? '#ffffff' : this.currentColor;
            ctx.lineWidth = 2;
            ctx.stroke();
            
            ctx.beginPath();
            ctx.arc(coords.x, coords.y, 2, 0, Math.PI * 2);
            ctx.fillStyle = '#ffffff';
            ctx.fill();
        } else {
            // Crosshair for shape tools
            ctx.strokeStyle = this.currentColor;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(coords.x - 10, coords.y);
            ctx.lineTo(coords.x + 10, coords.y);
            ctx.moveTo(coords.x, coords.y - 10);
            ctx.lineTo(coords.x, coords.y + 10);
            ctx.stroke();
        }
    }
    
    clearCursor() {
        this.cursorCtx.clearRect(0, 0, this.cursorCanvas.width, this.cursorCanvas.height);
    }
    
    hexToRgba(hex, opacity) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    }
    
    hexToRgbaValues(hex, opacity) {
        return {
            r: parseInt(hex.slice(1, 3), 16),
            g: parseInt(hex.slice(3, 5), 16),
            b: parseInt(hex.slice(5, 7), 16),
            a: Math.round(opacity * 255)
        };
    }
    
    async saveOverlay() {
        if (!this.currentItem) {
            this.showToast('No item selected', 'error');
            return;
        }
        
        const overlayData = this.overlayCanvas.toDataURL('image/png');
        
        const imageData = this.overlayCtx.getImageData(
            0, 0, this.overlayCanvas.width, this.overlayCanvas.height
        );
        const hasContent = imageData.data.some((val, i) => i % 4 === 3 && val > 0);
        
        const payload = {
            itemName: this.currentItem.name,
            itemType: this.currentItemType,
            overlayData: hasContent ? overlayData : null,
            overlayWidth: this.overlayWidth,
            overlayHeight: this.overlayHeight,
            flying: this.isFlying,
            colors: Array.from(this.usedColors)
        };
        
        try {
            const response = await fetch('/api/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast('Overlay saved successfully!', 'success');
                
                this.config[this.currentItemType][this.currentItem.name] = result.config;
                this.updateAssetGrid();
                
                const items = document.querySelectorAll('.asset-item');
                const assets = this.getCurrentAssets();
                items.forEach((item, index) => {
                    if (index < assets.length && assets[index].name === this.currentItem.name) {
                        item.classList.add('selected');
                    }
                });
                
                this.updateItemInfo();
            } else {
                this.showToast('Failed to save: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Save error:', error);
            this.showToast('Failed to save overlay', 'error');
        }
    }
    
    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}

// Initialize editor when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.editor = new TerrainEditor();
});
