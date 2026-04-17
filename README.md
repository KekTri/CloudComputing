# Smart Mobility Platform

Gruppe 2 — Universitätsprojekt Cloud Computing

Uber-ähnliches Ride-Sharing-System auf Basis von Microservices, Kafka und Kubernetes.

## Projektstruktur

```
.
├── services/
│   ├── customer-service/    # Kundenverwaltung (REST API, MongoDB)
│   ├── driver-service/      # Fahrerverwaltung (REST API, MongoDB, Kafka)
│   ├── ride-service/        # Fahrtbuchung & SAGA-Orchestrierung (MongoDB, Kafka)
│   ├── payment-service/     # Zahlungsabwicklung (MongoDB, Kafka)
│   ├── tracking-service/    # Positionsverfolgung während der Fahrt (MongoDB, Kafka)
│   ├── analytics-service/   # Spark Batch Job (historische Auswertung, MongoDB)
│   └── analytics-api/       # REST API zum Abrufen der Analytics-Ergebnisse
└── k8s/
    ├── namespace.yaml
    ├── mongo-shared.yaml    # Gemeinsame MongoDB-Instanz für alle Services
    ├── kafka-config.yaml
    ├── gateway.yaml
    ├── customer-service.yaml
    ├── driver-service.yaml
    ├── ride-service.yaml
    ├── payment-service.yaml
    ├── tracking-service.yaml
    └── analytics-cronjob.yaml
```

## Architektur

- **Kommunikation:** synchron via REST (Client → Service), asynchron via Kafka (Service → Service)
- **Datenbank:** eine gemeinsame MongoDB-Instanz, jeder Service nutzt eine eigene Datenbank darin
- **SAGA:** Fahrtbuchung (ride-service) orchestriert eine SAGA-Transaktion über 4 Schritte inkl. Compensating Transaction
- **Analytics:** Spark Batch Job (CronJob) liest historische Fahrtdaten aus MongoDB, speichert Ergebnisse in MongoDB; Fallback auf lokale Python-Berechnung wenn Spark nicht erreichbar
- **Deployment:** Kubernetes (K3s), Rolling Update für Zero-Downtime

## User Stories

1. **Fahrt buchen** — Kunde bucht Fahrt, bekommt Preis/Zeit-Schätzung, Fahrer akzeptiert via Kafka, Position wird getrackt, Zahlung bei Ankunft
2. **Fahrerbenachrichtigung** — Fahrer erhält Fahrtangebot via Kafka, akzeptiert, schließt Fahrt ab, wird danach wieder verfügbar
3. **Analytics (Batch)** — stündliche Auswertung der letzten 24h (Anzahl Fahrten, Ø Preis, Ø Distanz), Ergebnisse abrufbar via `GET /analytics/latest`

## Kafka Events (SAGA-Ablauf)

```
ride.created  →  driver.assigned  →  payment.requested  →  payment.authorized
                                                         ↘  payment.failed (Compensating)
```

## Kubernetes Deployment

```bash
export KUBECONFIG=gruppe-2-kubeconfig.yaml

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
```

## API-Übersicht

| Service          | Endpunkte                                              |
|------------------|--------------------------------------------------------|
| customer-service | POST /customers, GET /customers/{id}                   |
| driver-service   | POST /drivers, GET /drivers/{id}, PATCH /drivers/{id}/status |
| ride-service     | POST /rides, GET /rides/{id}, POST /rides/{id}/complete |
| tracking-service | POST /tracking/position, GET /tracking/{ride_id}       |
| payment-service  | GET /payments/{ride_id}                                |
| analytics-api    | GET /analytics/latest                                  |
