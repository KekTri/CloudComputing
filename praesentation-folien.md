# Präsentation – Smart Mobility Platform (Gruppe 2)

---

## Folie 1: Titel

**Smart Mobility Platform**
Gruppe 2 | Cloud Computing | DHBW

---

## Folie 2: Einleitung – User Story Analytics (2 min)

**User Story 3: Batch Analytics**

> Als Betreiber der Plattform möchte ich stündlich eine automatische Auswertung aller Fahrten der letzten 24 Stunden erhalten, damit ich Kennzahlen wie Gesamtanzahl der Fahrten, Durchschnittspreis und Statusverteilung einsehen kann. Die Ergebnisse sollen in einer NoSQL-Datenbank gespeichert und über eine API abfragbar sein.

*(User Stories „Fahrt buchen" und „Fahrerbenachrichtigung" werden hier nicht mehr beschrieben – technische Umsetzung folgt in den nächsten Kapiteln.)*

---

## Folie 3: Systemarchitektur – Microservice-Übersicht (3 min)

**[DIAGRAMM EINFÜGEN: Microservice-Map]**

Empfehlung: Rechteck pro Service mit Name, Aggregate und Aufgabe. Pfeile zeigen Kommunikation (sync/async markiert).

Inhalte des Diagramms:
- **customer-service** → Aggregate: Customer | Aufgabe: Kundenverwaltung
- **driver-service** → Aggregate: Driver | Aufgabe: Fahrerverwaltung, Zuweisung
- **ride-service** → Aggregate: Ride | Aufgabe: Fahrtbuchung, SAGA-Orchestrierung
- **payment-service** → Aggregate: Payment | Aufgabe: Zahlungsabwicklung
- **tracking-service** → Aggregate: Position | Aufgabe: GPS-Positionstracking
- **analytics-service** → Aggregate: AnalyticsResult | Aufgabe: Spark Batch Job (CronJob)
- **analytics-api** → Aggregate: AnalyticsResult | Aufgabe: Abfrage der Ergebnisse
- **Kafka** (zentral) → Event Bus zwischen Services
- **MongoDB** (je Service eigene Instanz) → Datenhaltung

Synchrone Kommunikation: REST (z.B. Client → ride-service: POST /rides)
Asynchrone Kommunikation: Kafka Events (z.B. ride-service → driver-service via `ride.created`)

---

## Folie 4: Kommunikationsdiagramm – User Story 1 (Fahrt buchen)

**[DIAGRAMM EINFÜGEN: Sequenzdiagramm US1]**

Empfehlung: Mermaid sequenceDiagram unter https://mermaidviewer.com/editor

```
sequenceDiagram
    actor Kunde
    participant ride-service
    participant Kafka
    participant driver-service
    participant payment-service

    Kunde->>ride-service: POST /rides (sync REST)
    ride-service->>Kafka: ride.created (async)
    Kafka->>driver-service: ride.created
    driver-service->>Kafka: driver.assigned (async)
    Kafka->>ride-service: driver.assigned
    ride-service->>Kafka: payment.requested (async)
    Kafka->>payment-service: payment.requested
    payment-service->>Kafka: payment.authorized (async)
    Kafka->>ride-service: payment.authorized
    Kunde->>ride-service: POST /rides/{id}/start (sync REST)
    Kunde->>ride-service: POST /rides/{id}/complete (sync REST)
```

---

## Folie 5: Kommunikationsdiagramm – User Story 2 (Fahrerbenachrichtigung)

**[DIAGRAMM EINFÜGEN: Sequenzdiagramm US2]**

```
sequenceDiagram
    actor Fahrer
    participant Kafka
    participant driver-service
    participant ride-service

    Kafka->>driver-service: ride.created
    Note over driver-service: Verfügbaren Fahrer suchen
    driver-service->>Kafka: driver.assigned
    Kafka->>ride-service: driver.assigned
    Note over ride-service: Status → DRIVER_ASSIGNED
    ride-service->>Kafka: ride.completed (nach Fahrt)
    Kafka->>driver-service: ride.completed
    Note over driver-service: Fahrer wieder AVAILABLE
```

---

## Folie 6: SAGA-Transaktion

**SAGA: Fahrt buchen (4 Schritte)**

| Schritt | Event | Aktion |
|---------|-------|--------|
| 1 | `ride.created` | ride-service erstellt Fahrt, sucht Fahrer |
| 2 | `driver.assigned` | driver-service weist Fahrer zu, ride-service fordert Zahlung an |
| 3 | `payment.requested` | payment-service autorisiert Zahlung |
| 4 | `payment.authorized` | ride-service setzt Status auf PAYMENT_AUTHORIZED |

**Compensating Transaction (Fehlerfall):**

- Kein Fahrer verfügbar → `driver.assignment.failed` → ride-service setzt Fahrt auf `CANCELLED`
- Zahlung schlägt fehl → `payment.failed` → ride-service setzt Fahrt auf `CANCELLED` + publiziert `driver.release` → driver-service setzt Fahrer zurück auf `AVAILABLE`

**[DIAGRAMM EINFÜGEN: Flowchart oder Sequenzdiagramm SAGA mit Fehlerfall]**

---

## Folie 7: Sync vs. Async Kommunikation

**Synchron (REST):**
- Client → ride-service: `POST /rides`, `POST /rides/{id}/start`, `POST /rides/{id}/complete`
- Vorteil: Sofortiges Feedback, einfaches Error-Handling
- Nachteil: Enge Kopplung, Sender wartet auf Antwort

**Asynchron (Kafka Events):**
- ride-service → driver-service → payment-service via Topics
- Vorteil: Lose Kopplung, Services unabhängig skalierbar, fault-tolerant
- Nachteil: Kein sofortiges Feedback, komplexeres Error-Handling (SAGA)

---

## Folie 8: Kubernetes Deployment (4 min)

**[SCREENSHOT EINFÜGEN: `kubectl get deployments -n mobility`]**

**[SCREENSHOT EINFÜGEN: `kubectl get services -n mobility`]**

Kurzbeschreibung: Jeder Microservice läuft als eigenes Deployment mit Rolling Update Strategy (`maxUnavailable: 0`, `maxSurge: 1`).

---

## Folie 9: Microservice mit eigener Datenbank

**Beispiel: ride-service + mongo-ride**

**[CODE-SCREENSHOT EINFÜGEN: Ausschnitt aus `k8s/ride-service.yaml`]**

Zeigen: MongoDB als separates Deployment mit eigenem PVC, ride-service referenziert mongo-ride via Service-Name.

Relevante Teile:
- `Deployment: mongo-ride` mit `image: mongo:7.0` und PVC-Mount
- `Deployment: ride-service` mit `MONGO_URL: mongodb://mongo-ride:27017`

---

## Folie 10: Zero-Downtime Update

**[SCREEN-RECORDING EINFÜGEN: ~30s Rolling Update]**

Aufnahme-Anleitung:
```bash
# Terminal 1: Watch pods
kubectl get pods -n mobility -w

# Terminal 2: Trigger rollout
kubectl rollout restart deployment/ride-service -n mobility
```

**Erklärung:**
- Rolling Update: Neuer Pod startet, bevor alter Pod beendet wird (`maxUnavailable: 0`)
- Vorteil: Kein Ausfall während Deployment
- Nachteil: Kurzzeitig doppelter Ressourcenverbrauch

---

## Folie 11: Containerisierung – Dockerfile

**[CODE-SCREENSHOT EINFÜGEN: `services/ride-service/Dockerfile`]**

*(Folie nur zeigen, nicht besprechen)*

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Folie 12: Big Data Analytics – Datenquelle (5 min)

**Datenquelle:**

- MongoDB Collection `ride_db.rides` (via ride-service befüllt)
- Felder: `ride_id`, `status`, `price_eur`, `distance_km`, `customer_id`, `driver_id`

**Spark-Job liest:**
- Alle Fahrten aus MongoDB via `pymongo`
- Übergibt Daten als DataFrame an externen Spark Cluster (Spark Connect)

**Verbindung:**
- Externer Spark Cluster: `sc://10.3.15.18:15012` (Spark Connect, kein lokales Java)
- CronJob läuft stündlich in Kubernetes

---

## Folie 13: Big Data Analytics – Spark Code

**[CODE-SCREENSHOT EINFÜGEN: Kern-Logik aus `services/analytics-service/analytics_job.py`]**

Relevanter Ausschnitt (Zeilen ~50-65):

```python
spark = SparkSession.builder.remote(connection_string).getOrCreate()

rides_df = spark.createDataFrame(all_rides)

total_rides = rides_df.count()
completed_rides = rides_df.filter(col("status") == "COMPLETED").count()
avg_price = rides_df.agg(avg("price_eur")).collect()[0][0] or 0.0
avg_distance = rides_df.agg(avg("distance_km")).collect()[0][0] or 0.0
status_counts_rows = rides_df.groupBy("status").agg(count("*").alias("count")).collect()
```

---

## Folie 14: Big Data Analytics – Ergebnisse

**Ergebnis landet in:** MongoDB `analytics_db.analytics_results`

**[SCREENSHOT EINFÜGEN: MongoDB-Dokument oder API-Response von `GET /analytics/latest`]**

Beispiel-Ergebnis:
```json
{
  "computed_at": "2026-04-15T18:00:00Z",
  "window_hours": 24,
  "total_rides": 12,
  "completed_rides": 8,
  "avg_price_eur": 14.50,
  "avg_distance_km": 8.73,
  "rides_by_status": {
    "COMPLETED": 8,
    "CANCELLED": 2,
    "ACTIVE": 2
  }
}
```

**[SCREENSHOT EINFÜGEN: Logs des ausgeführten Spark-Jobs (`kubectl logs`)]**

---

## Folie 15: Noteworthy (optional, 1 min)

**Besonderheiten:**

- **Kafka-Resilienz:** Alle Services starten auch ohne Kafka (non-blocking retry loop) — kein Crash bei Kafka-Ausfall
- **Spark Connect:** Analytics-Service nutzt externen Spark Cluster via gRPC (kein lokales Java im Container) → schlankes Image
- **Memory-optimiert:** MongoDB mit `--wiredTigerCacheSizeGB 0.1` → stabile Ausführung auf kleinem Cluster

---

## Checkliste: Was noch fehlt (TODO vor Abgabe)

- [ ] Diagramm Microservice-Map erstellen (Folie 3)
- [ ] Sequenzdiagramme US1 + US2 erstellen, z.B. mit mermaidviewer.com (Folien 4+5)
- [ ] SAGA-Diagramm mit Fehlerfall erstellen (Folie 6)
- [ ] Screenshot `kubectl get deployments/services -n mobility` machen (Folie 8)
- [ ] Screen-Recording Rolling Update aufnehmen (~30s) (Folie 10)
- [ ] Screenshot `analytics_job.py` Code (Folie 13)
- [ ] Screenshot MongoDB-Ergebnis oder API-Response (Folie 14)
- [ ] Screenshot Spark-Job Logs (Folie 14)
- [ ] Alle Screenshots/Videos in `assets/` Ordner ablegen
- [ ] README.md mit allem befüllen (Diagramme, Links, Screenshots)
- [ ] ZIP erstellen und im Moodle-Gruppenraum abgeben (Deadline: Mo 20.04. 9 Uhr)
- [ ] Slides als PDF spätestens 30min nach Präsentationsende abgeben
