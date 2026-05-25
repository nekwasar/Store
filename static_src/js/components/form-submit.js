export default () => ({
  nextPage: '',
  submitting: false,
  submitWithPage(page) {
    this.nextPage = page
    const required = this.$el.querySelectorAll('input[required]')
    const unfilled = Array.from(required).filter(input => !input.value.trim())
    if (unfilled.length > 0) {
      window.notify('Please fill in all required fields before submitting the form.', 'danger')
      return
    }
    this.submitting = true
    this.$el.submit()
  },
})
