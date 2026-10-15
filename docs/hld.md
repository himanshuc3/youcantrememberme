## HLD basics

What are the basic expectations from the interview:

1. Functional & non-functional requirements
   - Specify out-of-scope
2. API Contracts with failure/success responses
3. Entities
4. Overall architecture
5. Wrapping everything to satisfy non-functional requirements.

### Common attributes

- Breaking down ambiguous systems to simple ones that can be navigated through. Reason tradeoffs, communication usually helps with explaining and possibly reaching a better solution.
- Consistency vs availability
- Performance: latency vs throughput
- Read/write heavy
- Security compliance: hashing, tokenization, encryption
- Idempotency: for preventing duplication

- Trace ID vs Idempotency key/ID vs Request ID

### Payment Gateway interface

1. Functional requirements:
   - Client should be able to initiate
   - Transaction status tracking
   - Temporary session creation (time-bound)
   - Secure PCI-DSS compliance for card data handling
2. OOS: part payment, returns and refund
3. Non-functional requirements:
   - Scale - Ask the interviewer or estimate based on user-count: 10k TPS
   - Transactions have to be durable, so consistency and atomicity has to be followed
   - Latency: P99-200ms (room for burst requests like sales & festivals)
   - Security: end-to-end encryption, PCI Level 1 compliance
4. Core Entities:
   - Merchant/cients, Customer/Users
   - Transaction, PaymentMethod
   - WebhookEvent
   - PaymentSession
5. Misc:
   - Payment intent (id) when it is initiated from the client
   - Session creation happens by linking it to payment intent id
   - Pay request after entering the details
6. API Contracts
   - POST /v1/payment-intents
   - POST /v1/payment-sessions
   - POST /v1/checkout/pay
   - GET /v1/payments/{payment_id}
7. Architecture
   - Users -> client/merchant
   - client/merchant -> api gateway & load balancer
   - api gateway -> payment intent svc -> paymentintentDB
   - api-gateway -> paymentsession svc (returns a checkout page)
   - api-gateway -> paymentprocessor/backend svc -> external processor svc
8. Deep dive designing:
   - PaymentIntentDB
     - intent_id
     - amount
     - currency
     - merchant
     - customer
     - order_id
     - payment_method_type
     - ...metadata
   - Creating checkout session in redis for the sake of latency with session_id and redirect_url
   - Checkout frontend service (from client to load balancer to this service)
   - Checkout processor service:
     - validate session exists
     - intent valid
     - merhcant matched
     - session state is active
   - Checkour processor calls PCI Zone (tokenization)

## Core concepts

- Websockets & SSE maintain stateful persistent connections and therefore bypasses load balancer; consistent hashing for mapping to the same server
- gRPC uses binary serialization/deserialization and HTTP/2 useful for service-to-service communication; multiple req/res over the same TCP connection (reduces connecting pooling), binary over plain-text
- Load balancers work on different layers: 7 for routing requests and 4 is faster but dumber. For websockets, we are use layer 4 load balancers.
- API design: pagination (cursor based is preferred for real-time data writes, otherwise offset-based), rate limiting (for genuine burst requests, bot/spam prevention)
- Relational database: great with structured data, clear relationships, strong consistency (read is consistent with latest writes) and schema, normalization to prevent duplication/redundancy
- NoSQL db: dynamodb, mongodb - flexible schemas, scales horizontally easily, partition key, sort key
- Start with normalized relational models and denormalize specific hot paths if read performance needs to be improved
- Indexing: b-tree based for range queries, hash indexes (not used because can't get ranges), full-text indexes (for searching), geospatial indexes, Elasticsearch, PostGIS, syncing from SSOT via CDC for such secondary databases
- Caching: cache-aside Redis (with TTL), updating cache with updates to db (update cache, short TTLs, some staleness)
  - Cache stampedes means when a popular cache expires, misses happen and db is overloaded (thundering herd); prevent using locks where only 1 request rehydrates the entry and others wait or early recomputation (refresh entires before expiry); staggering TTLSs so entries don't all expire at once
  - If redis goes down: in-process/in-memory fallback cache, ciruit breakers to shed load (exponential backoff + jitter) or graceful degradation
  - CDN caching for static assets is easy peasy lemon squeazy
- Sharding: when a single database instance has outgrown storage limits, write throughput (>10k writes/second), read throughput that even replicas can't handle (scaling required based on the numbers that are calculated)
  - Shard key: based on which data/queries are routed to the database instance (often a tradeoff for queries, slow for X, fast for Y)
  - Consistent hashing helps prevent moving data stored across n shards when we remove/add shard etc and prevents massive data migrations
  - Distributed caches like Memcached/Redis cluster
- CAP theorem:
  - Availability is often kept at a priority unless in highly specialized cases like money movement, Ticketing systems, inventory management etc.
  - Social media feeds, recommendation systems, analytics dashboards, Calendar management, notifications work fine with eventual consistency different from weak consistency which doesn't guarantee convergence
  - YAT (yet another theorem) - PACELC: during partition choose between availability/consistency, else choose latency/consistency
- Numbers to know:
  - If let's say we get 50k requests/sec, maybe each server can handle 5k requests, which means we might need 10 servers

## Technologies

- Databases (think outside the tables; think NoSQL)
  - NoSQL: Data models (kv stores, document stores, column-family, graph), contrary to popular beliefs they have indexing and partitioning, use embedding and denormalization to store data inplace (could lead to a ton of problems)
  - DynamoDB, Cassandra, MongoDB
- Blob storage:
  - Basic flow: client -> server -> get a presigned url -> upload blob -> a notification to the server to update in DB (use multipart uploads)
  - Features: durability, scalability, cost, security, upload/download directly from the client, chunking
- Search optimized DB:
  - Uses indexing, tokenization, stemming, fuzzy search to make queries fast and efficient (preprocessing), builds inverted indexes
  - Elasticsearch, postgres supports GIN indexes
- API Gateway:
  - Sits in front of a microservice, handles routing based on service that needs to handle it, auth, rate-limiting, logging
- Load balancer:
  - Sits between the API gateway and the service
  - For persistent connections like websocket, L4 load balancer handles it
- Queues:
  - Helps dequeue the producer/consumer, async work handled by workers
  - Examples: Uber (when surges happen in ride requests)
  - Features: message ordering (FIFO, priority, time etc.), retry mechanisms (max-attempts), dead-letter queues (cannot be processed, useful for auditing and debugging), paritioning across servers (with partition key), backpressure (dropping further requests or slow down the rate of accepting new requests)
  - Kafka and SQS
- Streams / Event sourcing:
  - Changes in application state are stored as a sequence of events, retain data
  - Real-time analytics or ticker systems (Apache flink / Spark Streaming / Kafka)
  - Features: Scaling with paritioning, multiple consumer groups, replication, windowing (batch processing)
- Distributed locks:
  - SQL uses transaction locks but not useful for longer-term locking
  - Implemented using Redis / Zookeeper
  - Examples: e-commerce checkout system, ride-sharing/allocation, distributed cron-jobs
  - Features: Locking mechanisms (redlock using redis), expiry, granularity, deadlocks
- Distributed cache:
  - Features: eviction policy, cache invalidation (read-write consistency), write strategy (write-through, write-around, write-back)
  - Redis / Memcaches. Caching internals like sorting by most popular events etc. needs to be presented in order to help see the use of it.
- CDN:
  - Features: Not necessarily for just static content (can cache dynamic content that changes rarely), eviction policies
  - CloudFlare, Akamai, AWS CloudFront

## Common patterns

- Dealing with contention:
  - Ensure data consistency and prevent race conditions
  - Use database-level approaches like pessimistic and optimistic locking
  - For distribution systems, we need distributed locks, two-phase commit protocols and queue-based serialization
- Scaling reads:
  - Indexing, scale horizontally with read replicas, caching with Redis and CDN
  - Problems: cache invalidation (data consistency), replication lag in read replicas, dealing with hot keys/hot paths of requests
- Scaling writes:
  - Sharding, batching, intelligent load management
  - For burst handling: write queues to buffer temporary spikes, batching
- Multi-step processes:
  - Survive failures, retries, external deps
- General:
  - RESTFUL: Url paths shouldn't create verbs
  - HTTP Code 301: cached permanently, 302: not cached, can be used for analytics, expiration etc.
  - Base62 encoding is bijection
  - Redis: single threaded, atomic operations, eliminates race conditions, alternatives can be caching using CDN/edge computing; good option if infrequent writes aka invalidations; An alternative, but mostly an addition to this step is making our DBs faster by going through search patterns and partitioning to prevent full scan of rows
  - Prevent race conditions and data inconsistency: Row locks in sql help data consistency; Singular postgres transactions (SERIALIZABLE transactions, unrelated rows aren't blocked); ACID properties are easier to maintain when data is stored in a single DB instead of across different DBs
  - For geographical problems, could extend to graph databases, computational geometry datastructures suit this very well.
  - A quantitative estimation where a potential bottleneck is spotted helps narrow down to solving the cause for that scale
  - Database isolation levels: Read uncommitted (dirty reads), Read committed, Repeatable read, Serializable (strongest, prevents phantom reads); Database triggers to notify the caching system of data changes
  - High-frequency flash sales in booking systems: Like offline stores, places users in a virtual queues (can be maintained in sorted order according to timestamps in redis) with SSE updating the position of the user based on bookings/expiry
  - Timeseries DB: Timescale/InfluxDB

## Locking and contention

- Lock contention: Long running database locks aren't preferred; maintaining status and expiration time for locking atomic things like tickets with cron jobs acting to free up on expiry (doesn't work with inventory); Transaction with expiration time updates; distributed locks using redis with a TTL (using Lua sripts to make multi-lock acquisition atomic)
- Multi-step approach from easiest to most efficient:
  - Executing a single SQL query which is conditional: RDMS takes care of it
  - Row-level locks: SELECT ... FOR UPDATE; FOR NO KEY UPDATE; FOR SHARE; FOR KEY SHARE;
