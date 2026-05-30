import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const getStateMarkup   = () => api.get('/states/markup').then(r => r.data)
export const getCropMarkup    = (crop) => api.get(`/crops/${crop}/markup`).then(r => r.data)
export const getTrendFilters  = () => api.get('/trends/filters').then(r => r.data)
export const getPriceTrend    = (state, commodity) => api.get('/trends', { params: { state, commodity } }).then(r => r.data)
export const getRevenueLoss   = () => api.get('/revenue-loss').then(r => r.data)
export const getForecast      = (state, commodity) => api.get('/forecast', { params: { state, commodity } }).then(r => r.data)
export const getForecastAvailable = () => api.get('/forecast/available').then(r => r.data)
export const recommendCrop    = (body) => api.post('/recommend/crop', body).then(r => r.data)
export const planProfit       = (body) => api.post('/profit/plan', body).then(r => r.data)
export const getPriceReference = (state, commodity) =>
  api.get('/profit/price-reference', { params: { state, commodity } }).then(r => r.data)
export const getMandiCommodities = () => api.get('/mandi/commodities').then(r => r.data)
export const compareMandis    = (params) => api.get('/mandi/compare', { params }).then(r => r.data)
