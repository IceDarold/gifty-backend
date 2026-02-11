# Auth API Reference 🔐

Gifty's authentication system is built on **OAuth 2.0 with PKCE**. We support login via Google, Yandex, and VK. Sessions are stored in Redis and delivered to the client via HttpOnly Secure cookies.

---

## 🚀 Authentication Flow

For frontend developers, the login process works as follows:
1. Redirect the user to `/auth/{provider}/start`.
2. The backend redirects the user to the provider's login page.
3. After a successful login, the provider returns the user to our Callback URL.
4. The backend sets the `gifty_session` cookie and redirects the user back to the frontend.

---

## 🔑 Endpoints

### 1. Start Authorization (`/{provider}/start`)
Initiates the login process.

*   **URL**: `/api/v1/auth/{provider}/start`
*   **Method**: `GET`
*   **Parameters**:
    - `provider`: `google`, `yandex`, or `vk`.
    - `return_to` (query, optional): The URL on the frontend to return the user to after login (default is `/`).
*   **Result**: 302 Redirect.

### 2. Current User Info (`/me`)
Checks the current user's status.

*   **URL**: `/api/v1/auth/me`
*   **Method**: `GET`
*   **Response**: `UserDTO`
*   **Errors**:
    - `401 Unauthorized`: If the session is invalid or missing.

### 3. Logout (`/logout`)
Ends the session.

*   **URL**: `/api/v1/auth/logout`
*   **Method**: `POST`
*   **Result**: Deletes the cookie and clears data in Redis.

---

## 🛡 Security

*   **Cookies**: The `gifty_session` cookie is set with `HttpOnly`, `Secure`, `SameSite=Lax` flags.
*   **PKCE**: Used to protect against authorization code interception.
*   **State**: Protection against CSRF attacks via state verification.
