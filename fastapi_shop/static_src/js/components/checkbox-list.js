export default () => ({
  get anyChecked() {
    return Array.from(this.$el.querySelectorAll('.childCheckbox')).some(cb => cb.checked)
  },
  toggleAll() {
    const cbs = this.$el.querySelectorAll('.childCheckbox')
    const allChecked = Array.from(cbs).every(cb => cb.checked)
    cbs.forEach(cb => cb.checked = !allChecked)
    this.$el.dispatchEvent(new Event('change', { bubbles: true }))
  },
  onChildChange() {
    const master = this.$el.querySelector('#masterCheckbox')
    if (master) {
      const cbs = this.$el.querySelectorAll('.childCheckbox')
      master.checked = Array.from(cbs).every(cb => cb.checked)
    }
    this.$el.querySelector('.submit-button').disabled = !this.anyChecked
  },
})
