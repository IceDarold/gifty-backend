# Analytics Frontend Integration Guide

## Обзор

Бэкенд предоставляет три эндпоинта для отображения аналитики на дашборде `analytics.giftyai.ru`. Все эндпоинты используют **Redis кэширование** (5-15 минут), поэтому данные обновляются не мгновенно, но запросы очень быстрые.

**Base URL:** `https://api.giftyai.ru` (production) или `http://localhost:8000` (local)

---

## 🔑 Аутентификация

Эндпоинты **публичные** (пока), но в будущем могут потребовать авторизацию. Рекомендуется добавить заголовок:

```http
Authorization: Bearer <admin_token>
```

*(Пока не требуется, но будет добавлено позже)*

---

## 📊 Эндпоинт 1: KPI Statistics

### `GET /analytics/stats`

Возвращает основные метрики для карточек на дашборде.

#### Request

```bash
curl https://api.giftyai.ru/analytics/stats
```

#### Response

```json
{
  "dau": 127,
  "quiz_completion_rate": 68.5,
  "gift_ctr": 42.3,
  "total_sessions": 1543,
  "last_updated": "2026-02-04T13:15:42.123456"
}
```

#### Поля ответа

| Поле | Тип | Описание |
|------|-----|----------|
| `dau` | `int` | Daily Active Users за последние 24 часа |
| `quiz_completion_rate` | `float` | Процент завершённых квизов (за 7 дней) |
| `gift_ctr` | `float` | Click-Through Rate на подарки (% кликов от показов) |
| `total_sessions` | `int` | Общее количество начатых квизов (за 7 дней) |
| `last_updated` | `string` | ISO timestamp последнего обновления данных |

#### Пример использования (React)

```typescript
interface AnalyticsStats {
  dau: number;
  quiz_completion_rate: number;
  gift_ctr: number;
  total_sessions: number;
  last_updated: string;
}

const fetchStats = async (): Promise<AnalyticsStats> => {
  const response = await fetch('https://api.giftyai.ru/analytics/stats');
  if (!response.ok) throw new Error('Failed to fetch stats');
  return response.json();
};

// Использование в компоненте
const StatsCards = () => {
  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  
  useEffect(() => {
    fetchStats().then(setStats);
    // Обновлять каждые 5 минут
    const interval = setInterval(() => fetchStats().then(setStats), 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);
  
  if (!stats) return <Spinner />;
  
  return (
    <div className="stats-grid">
      <StatCard title="DAU" value={stats.dau} />
      <StatCard title="Quiz Completion" value={`${stats.quiz_completion_rate}%`} />
      <StatCard title="Gift CTR" value={`${stats.gift_ctr}%`} />
      <StatCard title="Total Sessions" value={stats.total_sessions} />
    </div>
  );
};
```

---

## 📈 Эндпоинт 2: Trends Data

### `GET /analytics/trends?days=7`

Возвращает данные для графиков трендов (временные ряды).

#### Request Parameters

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `days` | `int` | `7` | Количество дней для отображения (max: 90) |

#### Request

```bash
curl "https://api.giftyai.ru/analytics/trends?days=14"
```

#### Response

```json
{
  "dates": [
    "21-Jan-2026",
    "22-Jan-2026",
    "23-Jan-2026",
    "24-Jan-2026",
    "25-Jan-2026",
    "26-Jan-2026",
    "27-Jan-2026"
  ],
  "dau_trend": [45, 52, 48, 67, 89, 103, 127],
  "quiz_starts": [23, 31, 28, 42, 56, 71, 89],
  "last_updated": "2026-02-04T13:15:42.123456"
}
```

#### Поля ответа

| Поле | Тип | Описание |
|------|-----|----------|
| `dates` | `string[]` | Массив дат в формате "DD-MMM-YYYY" |
| `dau_trend` | `int[]` | Массив значений DAU по дням (соответствует `dates`) |
| `quiz_starts` | `int[]` | Массив количества запусков квиза по дням |
| `last_updated` | `string` | ISO timestamp последнего обновления |

#### Пример использования (Chart.js)

```typescript
import { Line } from 'react-chartjs-2';

interface TrendsData {
  dates: string[];
  dau_trend: number[];
  quiz_starts: number[];
  last_updated: string;
}

const TrendsChart = () => {
  const [trends, setTrends] = useState<TrendsData | null>(null);
  
  useEffect(() => {
    fetch('https://api.giftyai.ru/analytics/trends?days=30')
      .then(res => res.json())
      .then(setTrends);
  }, []);
  
  if (!trends) return <Spinner />;
  
  const chartData = {
    labels: trends.dates,
    datasets: [
      {
        label: 'Daily Active Users',
        data: trends.dau_trend,
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
      },
      {
        label: 'Quiz Starts',
        data: trends.quiz_starts,
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
      }
    ]
  };
  
  return <Line data={chartData} options={{ responsive: true }} />;
};
```

---

## 🎯 Эндпоинт 3: Conversion Funnel

### `GET /analytics/funnel`

Возвращает данные для визуализации воронки конверсии.

#### Request

```bash
curl https://api.giftyai.ru/analytics/funnel
```

#### Response

```json
{
  "steps": [
    {
      "name": "quiz_started",
      "count": 1543,
      "conversion_rate": 100.0
    },
    {
      "name": "quiz_completed",
      "count": 1057,
      "conversion_rate": 68.5
    },
    {
      "name": "results_shown",
      "count": 1042,
      "conversion_rate": 67.5
    },
    {
      "name": "gift_clicked",
      "count": 441,
      "conversion_rate": 28.6
    }
  ],
  "last_updated": "2026-02-04T13:15:42.123456"
}
```

#### Поля ответа

| Поле | Тип | Описание |
|------|-----|----------|
| `steps` | `array` | Массив шагов воронки (в порядке выполнения) |
| `steps[].name` | `string` | Название события |
| `steps[].count` | `int` | Количество пользователей, достигших этого шага |
| `steps[].conversion_rate` | `float` | Процент конверсии от первого шага |
| `last_updated` | `string` | ISO timestamp последнего обновления |

#### Пример использования (Funnel Chart)

```typescript
interface FunnelStep {
  name: string;
  count: number;
  conversion_rate: number;
}

interface FunnelData {
  steps: FunnelStep[];
  last_updated: string;
}

const FunnelChart = () => {
  const [funnel, setFunnel] = useState<FunnelData | null>(null);
  
  useEffect(() => {
    fetch('https://api.giftyai.ru/analytics/funnel')
      .then(res => res.json())
      .then(setFunnel);
  }, []);
  
  if (!funnel) return <Spinner />;
  
  // Маппинг названий для UI
  const stepLabels: Record<string, string> = {
    quiz_started: 'Начали квиз',
    quiz_completed: 'Завершили квиз',
    results_shown: 'Увидели результаты',
    gift_clicked: 'Кликнули на подарок'
  };
  
  return (
    <div className="funnel">
      {funnel.steps.map((step, index) => (
        <div key={step.name} className="funnel-step">
          <div className="step-label">{stepLabels[step.name]}</div>
          <div className="step-bar" style={{ width: `${step.conversion_rate}%` }}>
            <span>{step.count} ({step.conversion_rate}%)</span>
          </div>
          {index < funnel.steps.length - 1 && (
            <div className="drop-off">
              ↓ {funnel.steps[index].count - step.count} ушло
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
```

---

## 🛡️ Обработка ошибок

Все эндпоинты возвращают **graceful fallback** при ошибках:

```json
{
  "dau": 0,
  "quiz_completion_rate": 0.0,
  "gift_ctr": 0.0,
  "total_sessions": 0,
  "last_updated": "2026-02-04T13:15:42.123456",
  "error": "PostHog API error: ..."
}
```

Если поле `error` присутствует, показывайте пользователю сообщение:

```typescript
if (stats.error) {
  return <Alert severity="warning">Данные временно недоступны</Alert>;
}
```

---

## ⚡ Оптимизация

### Кэширование на фронте

Данные обновляются каждые 5-15 минут на бэке. Не делайте запросы чаще, чем раз в 5 минут:

```typescript
const CACHE_TTL = 5 * 60 * 1000; // 5 минут

const useCachedFetch = <T,>(url: string) => {
  const [data, setData] = useState<T | null>(null);
  const [lastFetch, setLastFetch] = useState(0);
  
  const fetchData = async () => {
    const now = Date.now();
    if (now - lastFetch < CACHE_TTL && data) return;
    
    const response = await fetch(url);
    const json = await response.json();
    setData(json);
    setLastFetch(now);
  };
  
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, CACHE_TTL);
    return () => clearInterval(interval);
  }, [url]);
  
  return data;
};
```

### Loading States

Показывайте скелетоны во время загрузки:

```typescript
if (!stats) {
  return <Skeleton variant="rectangular" width={300} height={120} />;
}
```

---

## 🎨 UI/UX Рекомендации

### 1. KPI Cards

```tsx
<Card>
  <CardHeader>
    <Icon name="users" />
    <Title>Daily Active Users</Title>
  </CardHeader>
  <CardBody>
    <BigNumber>{stats.dau}</BigNumber>
    <Trend>+12% vs yesterday</Trend>
  </CardBody>
</Card>
```

### 2. Trends Chart

- Используйте **Chart.js** или **Recharts**
- Добавьте легенду для каждой линии
- Tooltip при наведении на точку
- Возможность переключения периода (7d / 30d / 90d)

### 3. Funnel Visualization

- Горизонтальная воронка с уменьшающимися барами
- Показывайте процент drop-off между шагами
- Цветовое кодирование (зелёный → жёлтый → красный)

---

## 🔄 Обновление данных

### Автоматическое обновление

```typescript
const AnalyticsDashboard = () => {
  const [autoRefresh, setAutoRefresh] = useState(true);
  
  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(() => {
      // Обновить все данные
      refetchStats();
      refetchTrends();
      refetchFunnel();
    }, 5 * 60 * 1000); // каждые 5 минут
    
    return () => clearInterval(interval);
  }, [autoRefresh]);
  
  return (
    <div>
      <Toggle 
        checked={autoRefresh} 
        onChange={setAutoRefresh}
        label="Auto-refresh (5 min)"
      />
      {/* ... */}
    </div>
  );
};
```

---

## 📱 Responsive Design

Адаптируйте дашборд под мобильные устройства:

```css
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
```

---

## 🧪 Тестирование

### Mock данные для разработки

```typescript
const mockStats: AnalyticsStats = {
  dau: 127,
  quiz_completion_rate: 68.5,
  gift_ctr: 42.3,
  total_sessions: 1543,
  last_updated: new Date().toISOString()
};

// В dev режиме
const fetchStats = async () => {
  if (process.env.NODE_ENV === 'development') {
    return mockStats;
  }
  return fetch('/analytics/stats').then(r => r.json());
};
```

---

## 🚀 Deployment Checklist

- [ ] Заменить `localhost:8000` на `https://api.giftyai.ru`
- [ ] Добавить обработку ошибок для всех запросов
- [ ] Настроить кэширование на фронте (5 мин)
- [ ] Добавить loading states (скелетоны)
- [ ] Протестировать на мобильных устройствах
- [ ] Добавить мониторинг ошибок (Sentry)

---

## 📞 Поддержка

Если данные не приходят или есть вопросы:

1. Проверьте консоль браузера на ошибки CORS
2. Убедитесь, что бэкенд доступен: `curl https://api.giftyai.ru/health`
3. Свяжитесь с бэкенд-командой в Slack: `#gifty-backend`

---

## 🔮 Будущие улучшения

В следующих версиях планируется добавить:

- **Real-time updates** через WebSocket
- **Фильтры по датам** (custom date range)
- **Сегментация** (по источникам трафика, устройствам)
- **A/B тесты** (сравнение вариантов квиза)
- **Retention cohorts** (когортный анализ)
- **Export в CSV/Excel**

---

**Версия документа:** 1.0  
**Последнее обновление:** 2026-02-04  
**Автор:** Backend Team
