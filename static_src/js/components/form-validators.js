export const validatePrice = (value) => {
  const num = parseFloat(value)
  if (isNaN(num)) return 'Please enter a valid number.'
  if (num < 0) return 'Please enter a number from 0.01'
  return ''
}

export const validateQuantity = (value) => {
  const num = parseInt(value, 10)
  if (isNaN(num)) return 'Please enter a valid number.'
  if (num < 1) return 'Please enter a number from 1'
  return ''
}

export const validateDiscount = (value) => {
  const num = parseInt(value, 10)
  if (isNaN(num)) return 'Please enter a valid number.'
  if (num < 1 || num > 100) return 'Please enter a number between 0 and 100.'
  return ''
}
