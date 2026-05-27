import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const getStateMarkup   = () => api.get('/states/markup').then(r => r.data)
export const getCropMarkup    = (crop) => api.get(`/crops/${crop}/markup`).then(r => r.data)
export const getTrendFilters  = () => api.get('/trends/filters').then(r => r.data)
export const getPriceTrend    = (state, commodity) => api.get('/trends', { params: { state, commodity } }).then(r => r.data)
export const getRevenueLoss   = () => api.get('/revenue-loss').then(r => r.data)
export const getForecast      = (state, commodity) => api.get('/forecast', { params: { state, commodity } }).then(r => r.data)
