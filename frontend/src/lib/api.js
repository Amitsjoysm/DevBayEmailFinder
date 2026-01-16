import axios from 'axios';

const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API_URL,
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
};

export const verifyApi = {
  single: (email) => api.post('/verify/single', { email }),
  bulk: (emails, threads = 10, delay = 0) => api.post('/verify/bulk', { emails, threads, delay }),
  upload: (file, threads = 10, delay = 0) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/verify/upload?threads=${threads}&delay=${delay}`, formData);
  },
};

export const finderApi = {
  single: (data) => api.post('/find/single', data),
  upload: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/find/upload', formData);
  },
};

export const jobApi = {
  list: () => api.get('/jobs'),
  get: (jobId) => api.get(`/jobs/${jobId}`),
  pause: (jobId) => api.post(`/jobs/${jobId}/pause`),
  resume: (jobId) => api.post(`/jobs/${jobId}/resume`),
  stop: (jobId) => api.post(`/jobs/${jobId}/stop`),
};

export const resultsApi = {
  get: (jobId, skip = 0, limit = 100, status = null, provider = null) => {
    let url = `/results/${jobId}?skip=${skip}&limit=${limit}`;
    if (status) url += `&status=${status}`;
    if (provider) url += `&provider=${provider}`;
    return api.get(url);
  },
  export: (jobId, format = 'csv', status = null) => {
    let url = `/results/${jobId}/export?format=${format}`;
    if (status) url += `&status=${status}`;
    return api.get(url);
  },
};

export const settingsApi = {
  get: () => api.get('/settings'),
  update: (settings) => api.put('/settings', settings),
};

export const proxyApi = {
  list: () => api.get('/proxies'),
  add: (proxy) => api.post('/proxies', proxy),
  delete: (proxyId) => api.delete(`/proxies/${proxyId}`),
};

export const analyticsApi = {
  dashboard: () => api.get('/analytics/dashboard'),
};
