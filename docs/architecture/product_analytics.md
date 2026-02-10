# Product Analytics Architecture (PostHog Cloud) 🦔

We use PostHog Cloud for product analytics (user behavior, funnels, and retention). This document defines the standard event schema and integration guidelines for the frontend.

## 1. Integration Guide

- **SDK**: `posthog-js`
- **Instance**: `app.posthog.com` (PostHog Cloud)
- **Environment Variables**:
    - `NEXT_PUBLIC_POSTHOG_KEY`: Obtain from PostHog Project Settings.
    - `NEXT_PUBLIC_POSTHOG_HOST`: `https://app.posthog.com`

### Initialization
```javascript
posthog.init('<YOUR_PROJECT_API_KEY>', {
  api_host: 'https://app.posthog.com',
  autocapture: false // We prefer explicit tracking for better data quality
})
```

---

## 2. Global Properties
These properties should be included in *every* event if available:
- `user_id`: Unique identifier (if logged in).
- `algorithm_version`: Current recommendation engine version (e.g., `v1.2-qwen`).
- `test_group`: A/B testing group (e.g., `control`, `variant_a`).

---

## 3. Event Schema (The "Golden Path")

| Event Name | Trigger Context | Key Properties |
| :--- | :--- | :--- |
| `survey_started` | User clicks the "Start Quiz" button. | `entry_point` (home, header, ad) |
| `survey_step_completed` | User clicks "Next" on a quiz question. | `step_number`, `question_id`, `answer_value` |
| `survey_completed` | User reaches the final step of the quiz. | `duration_seconds` |
| `recommendation_viewed` | The results page is successfully rendered. | `result_count`, `top_category` |
| `gift_clicked` | User clicks a product link to an external store. | `product_id`, `merchant_name`, `price`, `rank` |

---

## 4. User Identity Management

1. **On Login**:
   ```javascript
   posthog.identify(user.id, {
     email: user.email,
     plan: 'free'
   });
   ```
2. **On Logout**:
   ```javascript
   posthog.reset();
   ```

## 5. Privacy (GDPR/152-FZ)
- Ensure IP collection is disabled in PostHog settings if required.
- Do not send PII (names, phone numbers) in event properties unless explicitly justified.
