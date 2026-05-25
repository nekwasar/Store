import { Notyf } from 'notyf'

const notyf = new Notyf({
  position: { x: 'right', y: 'top' },
  duration: 4000,
  ripple: true,
  types: [
    {
      type: 'info',
      background: '#3B82F6',
      icon: {
        className: 'bi bi-info-circle',
        tagName: 'i',
      },
    },
  ],
})

export function notify(message, type = 'info') {
  switch (type) {
    case 'danger':
    case 'error':
      notyf.error(message)
      break
    case 'success':
      notyf.success(message)
      break
    default:
      notyf.open({ type: 'info', message })
  }
}

export default notyf
