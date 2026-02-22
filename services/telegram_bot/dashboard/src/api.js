import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add Telegram initData to headers
api.interceptors.request.use((config) => {
    let initData = window.Telegram?.WebApp?.initData || '';

    // Dev bypass for local development
    if (!initData && import.meta.env.DEV) {
        initData = "dev_user_1821014162";
    }

    if (initData) {
        config.headers['X-TG-Init-Data'] = initData;
    }
    return config;
});

export const authWithTelegram = async () => {
    // webapp/auth expects init_data in the body, but it's also in the headers now
    // we keep it as is to not break existing backend logic
    let initData = window.Telegram?.WebApp?.initData || '';
    if (!initData && import.meta.env.DEV) {
        initData = "dev_user_1821014162";
    }
    const response = await api.post('/internal/webapp/auth', { init_data: initData });
    return response.data;
};

export default api;
