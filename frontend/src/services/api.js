import axios from 'axios';
export const getEvaluadores = () => api.get('/evaluadores/');
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});
// Interceptor para inyectar Token JWT
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('gio_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
export const loginApi = (credentials) => api.post('/auth/login/', credentials);
export const getIncidentes = (params) => api.get('/incidentes/', { params });
export const getTecnicos = () => api.get('/tecnicos/');
export const getCentrales = () => api.get('/centrales/');
export const createIncidente = (data) => api.post('/incidentes/', data);
export const updateIncidente = (id, data) => api.put(`/incidentes/${id}/`, data);
export default api;