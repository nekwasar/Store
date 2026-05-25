export default function (Alpine) {
    Alpine.data('authForm', () => ({
        loading: false,
        showPassword: false,
        showConfirm: false,
        errors: {},
        form: {
            username: '',
            email: '',
            password: '',
            confirm: '',
            terms: false,
        },
        touched: {},

        init() {
            const els = this.$el.querySelectorAll('[data-validate]');
            els.forEach(el => {
                el.addEventListener('blur', () => {
                    this.touched[el.name] = true;
                    this.validateField(el.name);
                });
                el.addEventListener('input', () => {
                    if (this.touched[el.name]) {
                        this.errors[el.name] = '';
                    }
                });
            });
        },

        validateField(name) {
            const val = (this.form[name] || '').trim();
            if (name === 'username') {
                if (val.length > 0 && val.length < 3) this.errors.username = 'Must be at least 3 characters.';
                else if (val.length > 32) this.errors.username = 'Must be 32 characters or fewer.';
                else this.errors.username = '';
            } else if (name === 'email') {
                if (val.length > 0 && (!val.includes('@') || val.length < 5)) this.errors.email = 'Enter a valid email.';
                else this.errors.email = '';
            } else if (name === 'password') {
                if (val.length > 0 && val.length < 8) this.errors.password = 'Must be at least 8 characters.';
                else this.errors.password = '';
                if (this.form.confirm && this.touched.confirm) this.validateField('confirm');
            } else if (name === 'confirm') {
                if (val && val !== this.form.password) this.errors.confirm = 'Passwords do not match.';
                else this.errors.confirm = '';
            }
        },

        get passwordStrength() {
            const pwd = this.form.password || '';
            let score = 0;
            if (pwd.length >= 8) score++;
            if (pwd.length >= 12) score++;
            if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++;
            if (/\d/.test(pwd)) score++;
            if (/[^a-zA-Z0-9]/.test(pwd)) score++;
            return Math.min(score, 4);
        },

        get strengthClass() {
            const levels = ['', 'danger', 'warning', 'info', 'success'];
            return levels[this.passwordStrength] || '';
        },

        get strengthLabel() {
            const labels = ['', 'Weak', 'Fair', 'Good', 'Strong'];
            return labels[this.passwordStrength] || '';
        },

        get strengthPercent() {
            return (this.passwordStrength / 4) * 100;
        },

        submit(e) {
            if (!this.$el.checkValidity()) {
                e.preventDefault();
                return;
            }
            this.loading = true;
        },
    }));
}
