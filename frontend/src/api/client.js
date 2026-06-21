import axios from 'axios'

// No global timeout: the analyze/recommend calls can legitimately run long
// (model inference, cold start). Per-call timeouts are applied where needed.
const api = axios.create({ baseURL: '/api' })

// Retry a request a few times with backoff. The Render free tier spins the API
// down after ~15 min idle; the first hit then takes ~50s to wake, so a single
// fetch can time out. Without this the dropdown-filling calls failed silently
// and the State picker fell back to its single default option (only "Punjab").
async function withRetry(fn, { attempts = 4, delay = 4000 } = {}) {
  let last
  for (let i = 0; i < attempts; i++) {
    try { return await fn() }
    catch (e) {
      last = e
      if (i < attempts - 1) await new Promise((r) => setTimeout(r, delay))
    }
  }
  throw last
}

export const getStateMarkup   = () => api.get('/states/markup').then(r => r.data)
export const getCropMarkup    = (crop) => api.get(`/crops/${crop}/markup`).then(r => r.data)
export const getTrendFilters  = () => withRetry(() => api.get('/trends/filters', { timeout: 25000 }).then(r => r.data))
export const getPriceTrend    = (state, commodity) => api.get('/trends', { params: { state, commodity } }).then(r => r.data)
export const getRevenueLoss   = () => api.get('/revenue-loss').then(r => r.data)
export const getForecast      = (state, commodity) => api.get('/forecast', { params: { state, commodity } }).then(r => r.data)
export const getForecastAvailable = () => api.get('/forecast/available').then(r => r.data)
export const recommendCrop    = (body) => api.post('/recommend/crop', body).then(r => r.data)
export const recommendSmart   = (body) => api.post('/recommend/smart', body).then(r => r.data)
export const planProfit       = (body) => api.post('/profit/plan', body).then(r => r.data)
export const getPriceReference = (state, commodity) =>
  api.get('/profit/price-reference', { params: { state, commodity } }).then(r => r.data)
export const getMandiCommodities = () => api.get('/mandi/commodities').then(r => r.data)
export const compareMandis    = (params) => api.get('/mandi/compare', { params }).then(r => r.data)
export const fpoBulkPlan       = (body) => api.post('/fpo/bulk-plan', body).then(r => r.data)
export const locateByGps      = (lat, lon) => api.post('/geo/locate', { lat, lon }).then(r => r.data)
export const resolvePincode   = (pin) => api.get(`/geo/pincode/${pin}`).then(r => r.data)
export const compareChannels  = (params) => api.get('/compare/channels', { params }).then((r) => r.data)
