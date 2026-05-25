export default function (Alpine) {
    Alpine.data('cartOffcanvas', () => ({
        open: false,
        loading: false,
        html: '',

        init() {
            const cookies = document.cookie.split(';').map(c => c.trim());
            const cartUpdated = cookies.find(c => c.startsWith('cart_updated='));
            if (cartUpdated && cartUpdated.split('=')[1] === '1') {
                document.cookie = 'cart_updated=; Max-Age=0; path=/';
                setTimeout(() => {
                    this.open = true;
                    this.fetchContent();
                }, 300);
            }
        },

        async fetchContent() {
            this.loading = true;
            try {
                const resp = await fetch('/cart/offcanvas');
                if (!resp.ok) throw new Error('Failed to fetch');
                this.html = await resp.text();
            } catch {
                this.html = '<div class="p-4 text-center text-muted">Failed to load cart.</div>';
            } finally {
                this.loading = false;
            }
        },

        toggle() {
            this.open = !this.open;
            if (this.open) this.fetchContent();
        },

        openCart() {
            this.open = true;
            this.fetchContent();
        },

        closeCart() {
            this.open = false;
        },

        async updateQuantity(productId, change) {
            try {
                const resp = await fetch('/cart/offcanvas-update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ product_id: productId, change: String(change) }),
                });
                if (!resp.ok) throw new Error('Failed to update');
                await this.fetchContent();
            } catch {
                window.notify && window.notify('Failed to update quantity.', 'error');
            }
        },

        async removeItem(productId) {
            try {
                const resp = await fetch('/cart/offcanvas-remove', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ product_id: productId }),
                });
                if (!resp.ok) throw new Error('Failed to remove');
                await this.fetchContent();
            } catch {
                window.notify && window.notify('Failed to remove item.', 'error');
            }
        },
    }));
}
