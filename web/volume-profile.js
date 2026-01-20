/**
 * BASTION Volume Profile Overlay
 * Draws VPVR histogram on chart edge
 */

class VolumeProfileOverlay {
    constructor(chartContainer, options = {}) {
        this.container = chartContainer;
        this.canvas = null;
        this.data = null;
        this.width = options.width || 50;
        this.priceRange = null;
        
        this.colors = {
            hvn: '#238636',      // High volume node - muted green
            lvn: '#30363d',      // Low volume node - dark gray
            poc: '#388bfd',      // Point of control - muted blue
            vah: '#bb8009',      // Value area boundary - muted amber
        };
        
        this.createCanvas();
    }
    
    createCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.id = 'volumeProfileOverlay';
        this.canvas.style.cssText = `
            position: absolute;
            top: 0;
            right: 52px;
            width: ${this.width}px;
            height: 100%;
            pointer-events: none;
            z-index: 5;
        `;
        
        // Ensure container is relative
        if (this.container.style.position !== 'relative' && 
            this.container.style.position !== 'absolute') {
            this.container.style.position = 'relative';
        }
        
        this.container.appendChild(this.canvas);
    }
    
    setData(vpvrData, priceRange) {
        /*
        vpvrData = {
            price_bins: [92000, 92500, 93000, ...],
            volume_at_price: [1000, 5000, 2000, ...],
            hvn_indices: [3, 7, 12],
            lvn_indices: [5, 10],
            poc_index: 7,
            value_area: { vah: 98000, val: 93500 }
        }
        
        priceRange = { min: 90000, max: 100000 }
        */
        this.data = vpvrData;
        this.priceRange = priceRange;
        this.render();
    }
    
    setPriceRange(min, max) {
        this.priceRange = { min, max };
        this.render();
    }
    
    render() {
        if (!this.data || !this.canvas) return;
        
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = this.width * window.devicePixelRatio;
        this.canvas.height = rect.height * window.devicePixelRatio;
        this.canvas.style.width = `${this.width}px`;
        this.canvas.style.height = `${rect.height}px`;
        
        const ctx = this.canvas.getContext('2d');
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        ctx.clearRect(0, 0, this.width, rect.height);
        
        const { price_bins, volume_at_price, hvn_indices, lvn_indices, poc_index, value_area } = this.data;
        
        if (!price_bins || price_bins.length === 0 || !volume_at_price) return;
        
        const maxVolume = Math.max(...volume_at_price);
        if (maxVolume === 0) return;
        
        // Use provided price range or calculate from data
        const minPrice = this.priceRange?.min || Math.min(...price_bins);
        const maxPrice = this.priceRange?.max || Math.max(...price_bins);
        const priceRangeVal = maxPrice - minPrice;
        
        if (priceRangeVal <= 0) return;
        
        const chartHeight = rect.height;
        const topMargin = 10;
        const bottomMargin = 30;
        const usableHeight = chartHeight - topMargin - bottomMargin;
        
        // Draw each volume bar
        for (let i = 0; i < price_bins.length; i++) {
            const price = price_bins[i];
            const volume = volume_at_price[i];
            
            if (price < minPrice || price > maxPrice) continue;
            
            // Calculate Y position (inverted - higher price = lower Y)
            const priceRatio = (price - minPrice) / priceRangeVal;
            const y = topMargin + usableHeight - (priceRatio * usableHeight);
            
            // Calculate bar width based on volume
            const barWidth = (volume / maxVolume) * this.width * 0.85;
            
            // Determine color
            let color = this.colors.lvn;
            if (hvn_indices && hvn_indices.includes(i)) {
                color = this.colors.hvn;
            }
            if (i === poc_index) {
                color = this.colors.poc;
            }
            
            // Opacity based on value area
            const inValueArea = value_area && 
                price >= (value_area.val || 0) && 
                price <= (value_area.vah || Infinity);
            ctx.globalAlpha = inValueArea ? 0.85 : 0.45;
            
            // Draw bar (from right edge)
            ctx.fillStyle = color;
            const barHeight = Math.max(2, usableHeight / price_bins.length * 0.8);
            ctx.fillRect(this.width - barWidth, y - barHeight / 2, barWidth, barHeight);
        }
        
        ctx.globalAlpha = 1.0;
        
        // Draw POC indicator
        if (poc_index !== undefined && poc_index < price_bins.length) {
            const pocPrice = price_bins[poc_index];
            const pocRatio = (pocPrice - minPrice) / priceRangeVal;
            const pocY = topMargin + usableHeight - (pocRatio * usableHeight);
            
            ctx.fillStyle = this.colors.poc;
            ctx.font = '9px JetBrains Mono, monospace';
            ctx.fillText('POC', 2, pocY + 3);
        }
        
        // Draw VAH/VAL lines
        if (value_area) {
            ctx.strokeStyle = this.colors.vah;
            ctx.lineWidth = 1;
            ctx.setLineDash([2, 2]);
            
            if (value_area.vah) {
                const vahRatio = (value_area.vah - minPrice) / priceRangeVal;
                const vahY = topMargin + usableHeight - (vahRatio * usableHeight);
                ctx.beginPath();
                ctx.moveTo(0, vahY);
                ctx.lineTo(this.width, vahY);
                ctx.stroke();
            }
            
            if (value_area.val) {
                const valRatio = (value_area.val - minPrice) / priceRangeVal;
                const valY = topMargin + usableHeight - (valRatio * usableHeight);
                ctx.beginPath();
                ctx.moveTo(0, valY);
                ctx.lineTo(this.width, valY);
                ctx.stroke();
            }
        }
    }
    
    clear() {
        if (this.canvas) {
            const ctx = this.canvas.getContext('2d');
            ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
        this.data = null;
    }
    
    destroy() {
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
    }
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VolumeProfileOverlay;
}

