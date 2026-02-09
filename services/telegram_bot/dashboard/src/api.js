import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '',
    headers: {
        'Content-Type': 'application/json',
    },
});

export const authWithTelegram = async () => {
    let initData = window.Telegram?.WebApp?.initData || '';

    // Dev bypass for local development
    if (!initData && import.meta.env.DEV) {
        console.log("Using DEV BYPASS initData");
        initData = "dev_user_1821014162";
    }

    const response = await api.post('/internal/webapp/auth', { init_data: initData });
    return response.data;
};

export default api;
