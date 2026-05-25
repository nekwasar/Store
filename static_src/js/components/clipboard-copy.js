export default (id) => ({
  id: id,
  copy() {
    navigator.clipboard.writeText(this.id).then(() => {
      window.notify('ID Copied!', 'success')
    }).catch(err => {
      window.notify('Failed to copy ID', 'danger')
    })
  },
})
