import Dropzone from 'dropzone'

export default (maxFiles = 1) => ({
  instance: null,
  init() {
    Dropzone.autoDiscover = false
    this.instance = new Dropzone(this.$el, {
      maxFiles,
      acceptedFiles: 'image/png,image/jpeg,image/webp',
      maxFileSize: 10,
      dictDefaultMessage: 'Drop image here or click to upload',
      addRemoveLinks: true,
      dictRemoveFile: 'Remove',
    })
  },
  destroy() {
    if (this.instance) this.instance.destroy()
  },
})
