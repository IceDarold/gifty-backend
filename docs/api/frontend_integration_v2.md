# Frontend Integration Guide: Discovery Engine v2

This document describes how the frontend (Web App / Mobile) should interact with the Gifty Discovery Engine.

## 1. High-Level Flow

The discovery process is a dialogue-driven state machine. Unlike a simple search, it guides the user through psychological hypotheses (Gaps) and interactive steps.

1.  **Init**: Send Quiz data -> Obtain `session_id` and initial state.
2.  **Dialogue Step (Optional)**: If the system returns a `current_probe`, show a question with options.
3.  **Overview**: Show "Topic Tracks". Each track contains several "Hypothesis Cards" with product previews.
4.  **Interaction**: User likes/dislikes/interacts with hypotheses.
5.  **Deep Dive**: If the user clicks on a hypothesis title/preview, fetch a full list of products for that specific idea.

---

## 2. Interface Definitions (TypeScript Style)

### RecommendationSession
The main object returned by almost every endpoint.

```typescript
interface RecommendationSession {
  session_id: string;
  recipient: {
    id: string;
    name?: string;
  };
  
  // Parallel topics explored
  tracks: TopicTrack[];
  
  // Discovery Helpers (Suggesting new directions)
  topic_hints: Array<{
    id: string;
    title: string;
    description: string;
  }>;

  // Active Dialogue (If not null, MUST show this to the user as a blocking screen)
  current_probe?: DialogueStep;

  // Selected state (for deep dive context)
  selected_topic_id?: string;
  selected_hypothesis_id?: string;
}

interface TopicTrack {
  topic_id: string;
  title: string;
  hypotheses: GiftHypothesis[];
}

interface GiftHypothesis {
  id: string;
  title: string;
  description: string;
  preview_products: GiftDTO[]; // Array of 3 items for preview
}

interface DialogueStep {
  question: string;
  options: string[];
  can_skip: boolean;
  type: 'topic_clarification' | 'gap_refinement' | 'pivot';
}

interface GiftDTO {
  id: string;
  title: string;
  description: string;
  price: number;
  currency: string;
  product_url: string;
  image_url?: string;
  store_name?: string;
}
```

---

## 3. Endpoints & Actions

### 1. Initialize Session
`POST /api/v1/recommendations/init`

Call this after the user completes the initial landing quiz.

**Request:**
```json
{
  "answers": {
    "age": 30,
    "gender": "male",
    "relation": "friend",
    "interests": "coffee, tech, travel",
    "budget": 5000
  }
}
```

**Behavior:**
- Creates a `RecipientProfile` in the database.
- Starts the AI analysis.
- Returns the first `RecommendationSession`. 

**Action Item:**
Check if `current_probe` is present. If yes -> Show question. If no -> Show tracks.

---

### 2. Interaction (The Heart of Discovery)
`POST /api/v1/recommendations/interact`

This endpoint handles ANY button click in the UI.

**Action Matrix:**

| User Action | `action` param | `value` param | Description |
| :--- | :--- | :--- | :--- |
| **Answer Probe** | `answer_probe` | Selected option text | Submits answer to AI question. |
| **Select Topic** | `select_track` | `topic_id` | Highlights a specific topic track. |
| **Suggest Topics**| `suggest_topics`| (empty) | Force AI to generate new `topic_hints`. |
| **Manual Refine** | `refine_topic` | `topic_id` | Triggers a clarification probe for topic. |

**Request Example:**
```json
{
  "session_id": "...",
  "action": "answer_probe",
  "value": "Play board games often"
}
```

---

### 3. Record Reactions
`POST /api/v1/recommendations/hypothesis/{hypothesis_id}/react`

Use this for the small ❤️ / 👎 buttons on cards. It doesn't trigger a dialogue transition immediately but helps the AI learn.

**Params:**
- `reaction`: `"like"`, `"dislike"`, `"shortlist"`

---

### 4. Deep Dive (Full Product List)
`GET /api/v1/recommendations/hypothesis/{hypothesis_id}/products`

When a user wants to see MORE than 3 items for an idea.

**Response:**
Returns `List[GiftDTO]` (usually 15-20 items).

---

## 4. UI Transition Logic (Frontend pseudocode)

```javascript
function handleSessionUpdate(session) {
    // 1. Check for Active Dialogue
    if (session.current_probe) {
        renderProbeModal(session.current_probe);
        return;
    }

    // 2. Render Main View
    if (session.tracks.length > 0) {
        renderHorizontalTracks(session.tracks);
    } else {
        // Fallback or "Thinking" state
        renderEmptyDiscoveryState();
    }

    // 3. Render Helpers
    if (session.topic_hints.length > 0) {
        renderRecommendationShortcuts(session.topic_hints);
    }
}
```

## 5. Security & Delimiters

**IMPORTANT**: All user inputs provided through the UI are sanitized on the backend. If you attempt to send tags like `<system>` or `<user_data>` in answers, they will be stripped.

- Max input length: 500 chars (truncated automatically).
- Suspicious patterns (e.g. "ignore instructions") trigger aggressive filtering.

## 6. Error Handling

- **404 Not Found**: Session expired or invalid ID. Frontend should redirect to the start of the quiz.
- **422 Validation Error**: Malformed JSON or invalid action type.
- **500 Internal Error**: AI failure or DB issue. Show a "Our brain is a bit tired, try again in a moment" message.
