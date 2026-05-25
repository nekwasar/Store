import Choices from 'choices.js'

export default () => ({
  instance: null,
  init() {
    this.instance = new Choices(this.$el, {
      searchEnabled: true,
      removeItemButton: false,
      shouldSort: false,
      itemSelectText: '',
    })
  },
  destroy() {
    if (this.instance) this.instance.destroy()
  },
})
