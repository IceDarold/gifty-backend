# Public API Reference 🌐

Gifty's Public API is designed for use by the external frontend (landing page). These endpoints are open and do not require authorization, but are protected from spam and abuse (Rate Limiting, Honeypot).

---

## 👥 Team

### 1. Get Team List (`/team`)
Returns a list of active Gifty team members to display on the landing page.

*   **URL**: `/api/v1/public/team`
*   **Method**: `GET`
*   **Response**: `List[TeamMemberSchema]`

---

## 📩 Leads and Feedback (Contacts)

All endpoints in this section support **Honeypot protection**. If the `hp` field is filled, the request is considered spam and ignored (success is returned, but data is not saved).

### 1. Investor Lead (`/investor-contact`)
Triggers a Telegram notification on the `investors` topic. Saves the contact to the database.

*   **URL**: `/api/v1/public/investor-contact`
*   **Method**: `POST`
*   **Body** (`InvestorContactCreate`):
    - `name` (string, min 2): Investor's name.
    - `company` (string, optional): Fund or company name.
    - `email` (EmailStr): Contact email.
    - `linkedin` (HttpUrl, optional): Profile link.
    - `hp` (string, optional): Honeypot (leave empty).

### 2. Partner Lead (`/partner-contact`)
Triggers a Telegram notification on the `partners` topic. Currently only notifies the team without saving to the DB.

*   **URL**: `/api/v1/public/partner-contact`
*   **Method**: `POST`
*   **Body** (`PartnerContactCreate`):
    - `name` (string): Representative's name.
    - `email` (EmailStr): Email.
    - `message` (string, min 10): Proposal content.
    - `website` (HttpUrl, optional): Company website.

### 3. Newsletter Subscription (`/newsletter-subscribe`)
Triggers a Telegram notification on the `newsletter` topic.

*   **URL**: `/api/v1/public/newsletter-subscribe`
*   **Method**: `POST`
*   **Body** (`NewsletterSubscribe`):
    - `email` (EmailStr): Email for subscription.

---

## 🎁 Recommendations

### 1. Generate Recommendations (`/generate`)
The main endpoint for the quiz.

*   **URL**: `/api/v1/recommendations/generate`
*   **Method**: `POST`
*   **Headers**: `X-Anon-Id` (UUID for anonymous session tracking).
*   **Body**: `RecommendationRequest` (quiz answers).
*   **Response**: `RecommendationResponse` (Hero gift and list of alternatives).

👉 For details on engine logic, see the [Recommendation Engine](../recommendation/engine.md) section.
