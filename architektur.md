# Architekturübersicht – Smart Mobility Platform

Gruppe 2 — Universitätsprojekt Cloud Computing

---

## Microservice-Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster (K3s)                     │
│                          Namespace: mobility                         │
│                                                                     │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │  customer-service│   │  driver-service  │   │  ride-service  │  │
│  │  POST /customers │   │  POST /drivers   │   │  POST /rides   │  │
│  │  GET  /customers │   │  GET  /drivers   │   │  GET  /rides   │  │
│  │                  │   │  PATCH /status   │   │  POST /complete│  │
│  │  DB: customer_db │   │  DB: driver_db   │   │  DB: ride_db   │  │
│  └──────────────────┘   └────────┬─────────┘   └───────┬────────┘  │
│                                  │ Kafka                │ Kafka     │
│  ┌──────────────────┐   ┌────────▼─────────┐   ┌───────▼────────┐  │
│  │  analytics-api   │   │ payment-service  │   │tracking-service│  │
│  │  GET /analytics  │   │  GET /payments   │   │  POST /position│  │
│  │  /latest         │   │                  │   │  GET /tracking │  │
│  │  DB: analytics_db│   │  DB: payment_db  │   │  DB: tracking_db│ │
│  └──────────────────┘   └──────────────────┘   └────────────────┘  │
│           ▲                                                          │
│  ┌────────┴─────────┐                                               │
│  │ analytics-service│   (Kubernetes CronJob, stündlich)             │
│  │  Spark Batch Job │                                               │
│  │  → analytics_db  │                                               │
│  └──────────────────┘                                               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  MongoDB (shared, 1 Instanz)                  │   │
│  │  customer_db │ driver_db │ ride_db │ payment_db │ tracking_db │  │
│  │                          │ analytics_db                        │  │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  Kafka (pre-installed)                        │   │
│  │  Topics: ride.created │ driver.assigned │ payment.requested   │  │
│  │          payment.authorized │ payment.failed                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Kommunikationsdiagramm

### Synchron (REST)

```
Client ──REST──▶ ride-service
Client ──REST──▶ customer-service
Client ──REST──▶ driver-service
Client ──REST──▶ tracking-service
Client ──REST──▶ analytics-api
```

### Asynchron (Kafka)

```
ride-service ──publish──▶ ride.created
                               │
                               ▼
                         driver-service ──publish──▶ driver.assigned
                                                           │
                                                           ▼
                                                     ride-service ──publish──▶ payment.requested
                                                                                      │
                                                                                      ▼
                                                                               payment-service ──publish──▶ payment.authorized
                                                                                                       └──▶ payment.failed
```

---

## SAGA-Transaktion: Fahrt buchen

```
Schritt 1:  POST /rides
            → ride-service erstellt Fahrt (Status: REQUESTED)
            → publiziert: ride.created

Schritt 2:  driver-service empfängt ride.created
            → weist Fahrer zu (Status: ASSIGNED)
            → publiziert: driver.assigned

Schritt 3:  ride-service empfängt driver.assigned
            → aktualisiert Fahrt (Status: DRIVER_ASSIGNED)
            → publiziert: payment.requested

Schritt 4:  payment-service empfängt payment.requested
            → verarbeitet Zahlung
            → publiziert: payment.authorized  ✓
              oder:        payment.failed      ✗ (Compensating Transaction)

Compensating: bei payment.failed
            → ride-service setzt Fahrt auf CANCELLED
            → driver-service setzt Fahrer auf AVAILABLE
```

---

## Analytics-Architektur (Batch / Lambda)

```
MongoDB (ride_db)
        │
        ▼
analytics-service (Kubernetes CronJob, stündlich)
        │
        ├──▶ Spark Connect (sc://10.3.15.18:15012)  ← primär (extern)
        │         falls nicht erreichbar:
        └──▶ lokale Python-Berechnung               ← Fallback (identische Logik)
        │
        ▼
MongoDB (analytics_db)
        │
        ▼
analytics-api  ──REST──▶  GET /analytics/latest
```

**Metriken:** Anzahl Fahrten, abgeschlossene Fahrten, Ø Preis (EUR), Ø Distanz (km), Fahrten nach Status — jeweils für die letzten 24h.

---

## Kubernetes-Deployment

```
Namespace: mobility
│
├── Deployments
│   ├── customer-service    (1 Replica, Rolling Update)
│   ├── driver-service      (1 Replica, Rolling Update)
│   ├── ride-service        (1 Replica, Rolling Update)
│   ├── payment-service     (1 Replica, Rolling Update)
│   ├── tracking-service    (1 Replica, Rolling Update)
│   ├── analytics-api       (1 Replica, Rolling Update)
│   └── mongo               (1 Replica, shared für alle Services)
│
├── CronJob
│   └── analytics-job       (stündlich, Spark Batch Job)
│
├── Services (ClusterIP)
│   └── je ein Service pro Deployment
│
└── Gateway (HTTPRoute)
    └── externer Zugang über Gateway Controller
```

**Zero-Downtime:** alle Service-Deployments nutzen Rolling Update Strategy (`maxSurge: 1, maxUnavailable: 0`).
