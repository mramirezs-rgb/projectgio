import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getIncidentes = (params = {}) => api.get('/incidentes/', { params });
export const createIncidente = (data) => api.post('/incidentes/', data);
export const updateIncidente = (id, data) => api.put(`/incidentes/${id}/`, data);
export const patchIncidente = (id, data) => api.patch(`/incidentes/${id}/`, data);
export const deleteIncidente = (id) => api.delete(`/incidentes/${id}/`);

export const getTecnicos = () => api.get('/tecnicos/');
export const getCentrales = () => api.get('/centrales/');

export default api;