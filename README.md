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

## API-Übersicht

| Service          | Endpunkte                                                    |
|------------------|--------------------------------------------------------------|
| customer-service | POST /customers, GET /customers/{id}                         |
| driver-service   | POST /drivers, GET /drivers/{id}, PATCH /drivers/{id}/status |
| ride-service     | POST /rides, GET /rides/{id}, POST /rides/{id}/complete      |
| tracking-service | POST /tracking/position, GET /tracking/{ride_id}             |
| payment-service  | GET /payments/{ride_id}                                      |
| analytics-api    | GET /analytics/latest                                        |

## Deployment

Container Images sind auf GHCR unter `ghcr.io/kektri/cloudcomputing/<service>:latest` verfügbar.

> **Hinweis:** Für den Analytics-Job wird zusätzlich `k8s/spark-secret.yaml` benötigt (enthält den Spark-Token, nicht im Repository enthalten).

```bash
export KUBECONFIG=gruppe-2-kubeconfig.yaml

# Spark-Secret zuerst anwenden (separat bereitgestellt)
kubectl apply -f k8s/spark-secret.yaml

# Namespace + Infrastruktur
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/mongo-shared.yaml
kubectl apply -f k8s/kafka-config.yaml
kubectl apply -f k8s/gateway.yaml

# Services
kubectl apply -f k8s/customer-service.yaml
kubectl apply -f k8s/driver-service.yaml
kubectl apply -f k8s/ride-service.yaml
kubectl apply -f k8s/payment-service.yaml
kubectl apply -f k8s/tracking-service.yaml

# Analytics (CronJob + API)
kubectl apply -f k8s/analytics-cronjob.yaml
kubectl scale deployment analytics-api -n mobility --replicas=1
kubectl patch cronjob analytics-job -n mobility -p '{"spec":{"suspend":false}}'
```

### Images selbst bauen (optional)

```bash
docker build -t ghcr.io/kektri/cloudcomputing/customer-service:latest services/customer-service/
docker build -t ghcr.io/kektri/cloudcomputing/driver-service:latest services/driver-service/
docker build -t ghcr.io/kektri/cloudcomputing/ride-service:latest services/ride-service/
docker build -t ghcr.io/kektri/cloudcomputing/payment-service:latest services/payment-service/
docker build -t ghcr.io/kektri/cloudcomputing/tracking-service:latest services/tracking-service/
docker build -t ghcr.io/kektri/cloudcomputing/analytics-service:latest services/analytics-service/
docker build -t ghcr.io/kektri/cloudcomputing/analytics-api:latest services/analytics-api/
```
