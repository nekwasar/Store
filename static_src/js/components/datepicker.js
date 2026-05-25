import flatpickr from 'flatpickr'

export default (options = {}) => ({
  instance: null,
  init() {
    const config = {
      enableTime: false,
      dateFormat: 'Y-m-d',
      minDate: 'today',
      allowInput: true,
      ...options,
    }
    this.instance = flatpickr(this.$el, config)
  },
  destroy() {
    if (this.instance) this.instance.destroy()
  },
})
