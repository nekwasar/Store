export default function (Alpine) {
    Alpine.data('searchSuggestions', () => ({
        query: '',
        suggestions: [],
        open: false,
        loading: false,
        selectedIndex: -1,
        debounceTimer: null,

        init() {
            this.$watch('query', () => {
                if (this.debounceTimer) clearTimeout(this.debounceTimer);
                this.selectedIndex = -1;
                if (this.query.length < 2) {
                    this.suggestions = [];
                    this.open = false;
                    return;
                }
                this.debounceTimer = setTimeout(() => this.fetchSuggestions(), 200);
            });

            this.$watch('open', (val) => {
                if (!val) this.selectedIndex = -1;
            });
        },

        async fetchSuggestions() {
            this.loading = true;
            try {
                const resp = await fetch(`/product/suggest?q=${encodeURIComponent(this.query)}`);
                if (!resp.ok) throw new Error('Failed to fetch');
                this.suggestions = await resp.json();
                this.open = this.suggestions.length > 0;
            } catch {
                this.suggestions = [];
                this.open = false;
            } finally {
                this.loading = false;
            }
        },

        select(index) {
            const item = this.suggestions[index];
            if (item) {
                window.location.href = `/product/${item._id}/${item.slug}`;
            }
        },

        onKeydown(e) {
            if (!this.open) return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, this.suggestions.length - 1);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
            } else if (e.key === 'Enter' && this.selectedIndex >= 0) {
                e.preventDefault();
                this.select(this.selectedIndex);
            } else if (e.key === 'Escape') {
                this.open = false;
                this.$refs.input.blur();
            }
        },

        close() {
            setTimeout(() => { this.open = false; }, 150);
        },
    }));
}
