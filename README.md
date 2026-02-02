# InstaLive Project

A comprehensive Live Streaming application backend built with **FastAPI**, **MongoDB (Beanie)**, and **LiveKit**. This project supports real-time video streaming, interactive chat, virtual gifting, user authentication, and administrative controls.

## 🚀 Core Features

1.  **Authentication & User Management**
    *   Secure Signup/Login with JWT and OTP verification.
    *   Google OAuth integration.
    *   Profile management (Avatar, Cover, Bio).
    *   **KYC Verification**: Users can submit ID documents for verification.

2.  **Live Streaming (LiveKit Integration)**
    *   **Start Stream**: Hosts can start streams with optional **Premium** access (Entry Fee).
    *   **Join Stream**: Viewers can join streams. Premium streams allow a 3-second free preview before payment is required.
    *   **Real-time Interaction**: Webhooks handle room events (start/end).

3.  **Monetization & Finance**
    *   **Virtual Currency (Coins)**: Economy system for transactions.
    *   **Gifting**: Viewers can send coin gifts to hosts during streams.
    *   **Pay-per-View**: Entry fees for premium streams.
    *   **Transaction History**: Full audit trail of all credits and debits.

4.  **Social Interactions**
    *   **Live Chat**: Real-time comments during streams.
    *   **Likes**: TikTok/Bigo-style like system.
    *   **Messenger**: Real-time private messaging with image support, replies, and reactions.
    *   **Reporting**: Users can report streams (e.g., Nudity, Violence); Moderators review these reports.

5.  **Admin & Moderation**
    *   **Feature Toggles**: Admin can enable/disable features (Registration, Gifting, Paid Streams, etc.) via System Config.
    *   **Moderators**: Dedicated role with granular permissions (Ban users, Review KYC, Manage Reports).
    *   **Audit Logs**: Tracks all sensitive actions.
    *   **Statistics**: Admin dashboard stats (Monthly user growth, active streams).

---

## 🛠 Technology Stack

*   **Language**: Python 3.x
*   **Framework**: FastAPI
*   **Database**: MongoDB (with Beanie ODM & Motor)
*   **Streaming**: LiveKit (WebRTC)
*   **Real-time Auth**: JWT
*   **Deployment**: Docker ready (implied)

---

## 📚 API Documentation

### Base URL: `/api/v1`

### 1. Authentication (`/auth`)

#### Signup
*   **Endpoint**: `POST /auth/signup`
*   **Body**: JSON
    ```json
    {
      "first_name": "John",
      "last_name": "Doe",
      "email": "user@example.com",
      "password": "securePassword123"
    }
    ```
*   **Response**: `201 Created`
    ```json
    {
      "id": "507f1f77bcf86cd799439011",
      "email": "user@example.com",
      "account_status": "active",
      "is_verified": false,
      ...
    }
    ```

#### Login
*   **Endpoint**: `POST /auth/login`
*   **Body**: Form Data (`OAuth2PasswordRequestForm`)
    *   `username`: email or phone
    *   `password`: password
*   **Response**: `200 OK`
    ```json
    {
      "access_token": "eyJhbGciOi...",
      "token_type": "bearer"
    }
    ```

#### OTP Verification
*   **Endpoint**: `POST /auth/otp-verify`
*   **Body**: JSON
    ```json
    {
      "email": "user@example.com",
      "otp": "123456"
    }
    ```

### 2. User Management (`/users`)

#### Get My Profile
*   **Endpoint**: `GET /users/my_profile`
*   **Headers**: `Authorization: Bearer <token>`
*   **Response**: `200 OK`
    ```json
    {
      "id": "...",
      "first_name": "John",
      "coins": 100.0,
      "past_streams": [],
      "kyc": { "status": "approved", ... }
    }
    ```

#### Update Profile
*   **Endpoint**: `PATCH /users/my_profile/update`
*   **Body**: JSON
    ```json
    {
      "bio": "Hello world!",
      "country": "USA"
    }
    ```

#### Upload Profile Image
*   **Endpoint**: `POST /users/my_profile/upload-profile-image`
*   **Body**: Multipart/Form-Data (`image`)

#### KYC Submit
*   **Endpoint**: `POST /users/kyc/submit`
*   **Body**: Multipart/Form-Data (`id_front`, `id_back`)

### 3. Live Streaming (`/streaming`)

#### Start Stream
*   **Endpoint**: `POST /streaming/start`
*   **Query Parameters**:
    *   `is_premium`: `true` or `false`
    *   `entry_fee`: Amount (e.g., `10`)
    *   `title`: Stream Title
    *   `category`: Stream Category
*   **Response**: `201 Created`
    ```json
    {
      "live_id": "...",
      "livekit_token": "eyJ...",
      "channel_name": "live_user_123_..."
    }
    ```

#### Join Stream produces Token
*   **Endpoint**: `POST /streaming/join/{session_id}`
*   **Response**: `200 OK`
    ```json
    {
      "livekit_token": "...",
      "room_name": "...",
      "balance": 50.0,
      "is_premium": true,
      "has_paid": false,
      "entry_fee": 10.0
    }
    ```

#### Pay Entry Fee
*   **Endpoint**: `POST /streaming/pay/{session_id}`
*   **Description**: Deduced coins for premium stream after preview.

#### Active Streams
*   **Endpoint**: `GET /streaming/active`
*   **Response**: List of active stream objects.

### 4. Interactions & Social (`/streaming/interactions`)

#### Like Stream
*   **Endpoint**: `POST /streaming/interactions/like`
*   **Query Parameters**: `session_id`

#### Comment
*   **Endpoint**: `POST /streaming/interactions/comment`
*   **Query Parameters**: `session_id`, `content`

#### Report Stream
*   **Endpoint**: `POST /streaming/interactions/report`
*   **Query Parameters**: `session_id`, `category`, `description`

### 5. Chat (`/chat`)

#### Active Chat Users
*   **Endpoint**: `GET /chat/active-users`

#### Chat History
*   **Endpoint**: `GET /chat/history/{receiver_id}`

#### Conversations List
*   **Endpoint**: `GET /chat/conversations`
*   **Response**: List of recent conversations with last message and unread count.

### 6. Finance (`/finance`)

#### Transaction History
*   **Endpoint**: `GET /finance/history`
*   **Response**: List of transactions (credits/debits).

### 7. Admin (`/admin`)

#### Monthly User Stats
*   **Endpoint**: `GET /admin/stats/users/monthly?year=2024`

#### System Config
*   **Endpoint**: `GET /admin/config`
*   **Response**:
    ```json
    {
      "registration_enabled": true,
      "gifting_enabled": true,
      "paid_streams_enabled": true,
      ...
    }
    ```

---

## 📈 Scopes for Improvement

1.  **Scalability**:
    *   Current WebSocket implementation uses in-memory `ConnectionManager`. To scale across multiple server instances, integrate **Redis Pub/Sub** to broadcast messages across nodes.
    
2.  **Payment Gateway**:
    *   Implement real payment gateways (Stripe, PayPal, BKash) to allow users to purchase Coins. Currently, coins are only circulated internally or via manual admin top-up.

3.  **Code Structure**:
    *   Move query parameters in POST requests (Live/Interactions) to **Pydantic Body Models** for better validation, documentation (Swagger), and client generation.
    *   Add comprehensive **Unit and Integration Tests** using `pytest`.

4.  **Notifications**:
    *   Implement Push Notifications (FCM/OneSignal) for "User went live" or "New Message" alerts.

5.  **Documentation**:
    *   Utilize FastAPI's auto-generated `/docs` (Swagger UI) effectively by adding more `response_model` examples and descriptions.

---

## 🏁 Getting Started

1.  **Clone the Repository**
2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    # or if using poetry
    poetry install
    ```
3.  **Environment Setup**
    Create a `.env` file with:
    ```env
    MONGO_URL=mongodb://localhost:27017
    LIVEKIT_API_KEY=...
    LIVEKIT_API_SECRET=...
    SECRET_KEY=...
    ```
4.  **Run the Server**
    ```bash
    uvicorn instalive_live_app.main:app --reload
    ```
    Access API Docs at `http://localhost:8000/docs`
