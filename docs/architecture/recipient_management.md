# Recipient Management Refactoring

## Overview
This document describes the refactoring of the data models to separate the concepts of "User" (gift seeker) and "Recipient" (gift receiver), establishing a one-to-many relationship where a User can have multiple Recipients.

## Changes Made

### 1. Database Models (`app/models.py`)

#### New `Recipient` Model
```python
class Recipient(TimestampMixin, Base):
    __tablename__ = "recipients"
    
    id: UUID (primary key)
    user_id: UUID (foreign key to users.id)
    name: Optional[str]
    relation: Optional[str]  # friend, partner, etc.
    gender: Optional[str]
    age: Optional[int]
    birth_date: Optional[datetime]
    interests: List[str] (JSONB)
```

#### New `Interaction` Model
```python
class Interaction(TimestampMixin, Base):
    __tablename__ = "interactions"
    
    id: UUID (primary key)
    recipient_id: UUID (foreign key to recipients.id)
    session_id: str
    action_type: str  # like, dislike, view, purchase
    target_type: str  # hypothesis, product
    target_id: str
    value: Optional[str]
    metadata_json: Optional[dict] (JSONB)
```

### 2. Pydantic Models (`recommendations/models.py`)

- **Renamed**: `UserProfile` → `RecipientProfile`
- **Added fields**:
  - `id`: Optional[str]
  - `owner_id`: Optional[str]
  - `name`: Optional[str]

- **Updated**: `RecommendationSession.profile` → `RecommendationSession.recipient`

### 3. Services

#### New `RecipientService` (`app/services/recipient_service.py`)
Handles CRUD operations for recipients and their interactions:
- `create_recipient(user_id, profile)` - Create a new recipient
- `get_recipient(recipient_id)` - Get recipient by ID
- `get_user_recipients(user_id)` - Get all recipients for a user
- `update_recipient(recipient_id, ...)` - Update recipient info
- `save_interaction(recipient_id, session_id, interaction)` - Save interaction
- `get_recipient_interactions(recipient_id, limit)` - Get interaction history

#### Updated `DialogueManager` (`app/services/dialogue_manager.py`)
- Added `db: AsyncSession` parameter to constructor
- Added `user_id: Optional[UUID]` parameter to `init_session()`
- Automatically creates `Recipient` in database when session is initialized
- All references to `session.profile` updated to `session.recipient`

### 4. API Endpoints

#### New Recipients Router (`routes/recipients.py`)

- `GET /recipients/?user_id={uuid}` - List all recipients for a user
- `GET /recipients/{recipient_id}` - Get specific recipient
- `PUT /recipients/{recipient_id}` - Update recipient information
- `GET /recipients/{recipient_id}/history` - Get interaction history

#### Updated Recommendations Router
- `POST /recommendations/init` now accepts optional `user_id` parameter
- When `user_id` is provided, a `Recipient` record is created in the database

### 5. Configuration (`app/config.py`)

Added Docker-aware URL properties:
- `db_url` - Automatically uses `postgres` host when running in Docker
- `redis_connection_url` - Automatically uses `redis` host when running in Docker
- `rabbitmq_connection_url` - Automatically uses `rabbitmq` host when running in Docker

This allows the same `.env` file to work both locally and in Docker containers.

## Database Migration

Migration file: `alembic/versions/345ee831ac2a_add_recipients_and_interactions.py`

To apply:
```bash
alembic upgrade head
```

## Usage Example

### Creating a Session with Recipient Persistence

```python
# POST /recommendations/init
{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "quiz": {
        "recipient_age": 30,
        "interests": ["coffee", "books"],
        "budget": 5000,
        "language": "ru"
    }
}
```

This will:
1. Create a `RecipientProfile` in the session (Redis)
2. Create a `Recipient` record in PostgreSQL
3. Link the recipient to the user
4. Return a session with the recipient profile

### Viewing Recipient History

```python
# GET /recipients/{recipient_id}/history?limit=50
```

Returns all interactions for this recipient across all sessions.

## Benefits

1. **Persistent Recipient Profiles**: Recipients are now stored in the database, allowing for long-term tracking
2. **Multi-Recipient Support**: Users can manage multiple gift recipients
3. **Interaction History**: All user interactions are logged per recipient for better personalization
4. **Future Wishlist**: Foundation for implementing recipient-specific wishlists
5. **Better Analytics**: Can track gift-giving patterns per recipient type/relationship

## Next Steps

1. Implement wishlist functionality per recipient
2. Add recipient-specific recommendation tuning
3. Implement recipient search/filtering
4. Add recipient photo upload
5. Create recipient management UI in frontend
