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
│   └── analytics-service/   # Spark Batch Job (historische Auswertung, MongoDB)
├── k8s/
│   ├── namespace.yaml
│   ├── kafka-config.yaml
│   ├── gateway.yaml
│   ├── customer-service.yaml
│   ├── driver-service.yaml
│   ├── ride-service.yaml
│   ├── payment-service.yaml
│   ├── tracking-service.yaml
│   └── analytics-cronjob.yaml
├── dashboard/               # Einfaches HTML-Dashboard (Nginx)
└── docker-compose.yml       # Lokale Entwicklungsumgebung
```

## Architektur

- **Kommunikation:** synchron via REST (service-to-service), asynchron via Kafka (Events)
- **Datenbanken:** je ein eigenes MongoDB-Deployment pro Service
- **SAGA:** Fahrtbuchung (ride-service) orchestriert eine SAGA-Transaktion über mind. 3 Schritte inkl. Compensating Transaction
- **Analytics:** Spark Batch Job liest historische Fahrtdaten aus Kafka/MongoDB, speichert Ergebnisse in MongoDB
- **Deployment:** Kubernetes (K3s), Rolling Update für Zero-Downtime

## User Stories

1. **Fahrt buchen** — Kunde bucht Fahrt, bekommt Preis/Zeit, Fahrer akzeptiert, Position wird getrackt, Zahlung bei Ankunft
2. **Fahrerbenachrichtigung** — Fahrer erhält Angebot, akzeptiert, schließt Fahrt ab, wird danach wieder verfügbar
3. **Analytics (Batch)** — periodische Auswertung der letzten 24h, Ergebnisse abrufbar z.B. für Pricing

## Lokale Entwicklung

```bash
docker-compose up --build
```

| Service          | Port  |
|------------------|-------|
| ride-service     | 8001  |
| driver-service   | 8002  |
| customer-service | 8003  |
| tracking-service | 8004  |
| payment-service  | 8005  |
| dashboard        | 8080  |
| kafka            | 9092  |

## Kubernetes Deployment

```bash
export KUBECONFIG=gruppe-2-kubeconfig.yaml

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
```
