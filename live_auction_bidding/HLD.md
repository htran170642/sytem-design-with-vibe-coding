┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│  Web/Mobile Apps ←─── WebSocket ───→ Real-time Updates              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      LOAD BALANCER (L7)                              │
│                    (Sticky sessions for WebSocket)                   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      API GATEWAY LAYER                               │
│            Rate Limiting | Authentication | Routing                  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
        ┌────────────────────┴────────────────────┐
        ↓                                          ↓
┌──────────────────┐                    ┌──────────────────┐
│  Bidding Service │                    │  WebSocket       │
│  (Stateless)     │                    │  Service         │
│  - Bid validation│                    │  (Stateful)      │
│  - Proxy bidding │                    │  - Push updates  │
└──────────────────┘                    └──────────────────┘
        ↓                                          ↑
┌──────────────────────────────────────────────────────────┐
│                    REDIS CLUSTER                          │
│  • Distributed Locks (Redlock)                           │
│  • Current Bid Cache                                     │
│  • Auto-bid Queue                                        │
│  • Pub/Sub for real-time events                         │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│              PRIMARY DATABASE (PostgreSQL)                │
│  • Auction data (ACID transactions)                      │
│  • Bid history (append-only event log)                  │
│  • User data                                             │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│           MESSAGE QUEUE (Kafka/RabbitMQ)                 │
│  • Async processing                                      │
│  • Event sourcing                                        │
│  • Analytics pipeline                                    │
└──────────────────────────────────────────────────────────┘