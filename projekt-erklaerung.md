# Projektdokumentation – Smart Mobility Platform
## Gruppe 2 | Cloud Computing | DHBW

---

# 1. Was haben wir gebaut?

Eine **Ride-Sharing-Plattform** (ähnlich Uber) bestehend aus mehreren kleinen, unabhängigen Backend-Diensten. Es gibt kein Frontend — alles läuft über REST-API-Aufrufe.

**Zwei Nutzertypen:**
- **Kunden** — buchen Fahrten
- **Fahrer** — nehmen Fahrten an und führen sie durch

**Drei User Stories:**
1. Kunde bucht eine Fahrt → Fahrer wird zugewiesen → Zahlung erfolgt bei Ankunft
2. Fahrer erhält Benachrichtigung → nimmt Fahrt an → Fahrt abgeschlossen → Fahrer wieder verfügbar
3. Stündliche Batch-Analyse aller Fahrten → Ergebnisse in Datenbank gespeichert

---

# 2. Grundbegriffe: Docker & Container

## Was ist ein Container?
Ein Container ist ein abgeschlossenes, portables Paket das eine Anwendung + alle ihre Abhängigkeiten enthält. Er läuft isoliert vom Rest des Systems — egal ob auf einem Laptop, Server oder in der Cloud.

**Analogie:** Ein Container ist wie eine Schiffscontainer-Box: Der Inhalt ist immer gleich verpackt, egal auf welchem Schiff (Server) er transportiert wird.

## Was ist ein Docker-Image?
Ein Image ist die "Vorlage" für einen Container. Aus einem Image können beliebig viele Container gestartet werden.

**Analogie:** Image = Kuchenform, Container = der gebackene Kuchen

## Was ist ein Dockerfile?
Eine Textdatei, die beschreibt wie ein Image aufgebaut wird:

```dockerfile
FROM python:3.11-slim        # Basis-Image (Python vorinstalliert)
WORKDIR /app                 # Arbeitsverzeichnis im Container
COPY requirements.txt .      # Abhängigkeitsliste reinkopieren
RUN pip install -r requirements.txt  # Pakete installieren
COPY app/ app/               # Code reinkopieren
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]  # Startbefehl
```

---

# 3. Grundbegriffe: Kubernetes (K8s)

Kubernetes ist ein System zum **automatischen Verwalten von Containern** auf einem oder mehreren Servern (Nodes).

## Node
Ein einzelner Server (virtuelle Maschine), auf dem Container laufen. Unser Cluster hat einen Node: `group-2` (IP: `141.72.176.41`).

## Pod
Die kleinste Einheit in Kubernetes. Ein Pod enthält einen oder mehrere Container, die zusammen laufen. In der Regel: **1 Pod = 1 Container**.

```
Node group-2
├── Pod: ride-service       (enthält: ride-service Container)
├── Pod: mongo-ride         (enthält: MongoDB Container)
├── Pod: customer-service   (enthält: customer-service Container)
└── ...
```

**Wichtig:** Pods sind kurzlebig — wenn ein Pod abstürzt, startet Kubernetes automatisch einen neuen.

## Deployment
Ein Deployment beschreibt, **wie viele Pods** eines Services laufen sollen und **welches Image** benutzt wird. Kubernetes sorgt dafür, dass immer die gewünschte Anzahl läuft.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ride-service
spec:
  replicas: 1          # 1 Pod soll immer laufen
  template:
    spec:
      containers:
        - name: ride-service
          image: ghcr.io/kektri/cloudcomputing/ride-service:latest
```

## Service (Kubernetes)
Pods haben wechselnde IP-Adressen. Ein Kubernetes-Service ist eine **stabile Adresse** (DNS-Name), hinter der der Pod erreichbar ist.

```
customer-service-pod (IP wechselt bei Neustart)
       ↑
kubernetes Service "customer-service" (DNS: customer-service, Port: 80)
       ↑
ride-service fragt immer: http://customer-service/...
```

**Nicht verwechseln:** "Service" = Kubernetes-Objekt für Networking. Unser "ride-service" ist eine Anwendung (Microservice), die ebenfalls über ein Kubernetes-Service-Objekt erreichbar ist.

## Namespace
Ein logischer Bereich zur Trennung von Ressourcen. Unser Projekt läuft im Namespace `mobility`. Kubernetes-Systemkomponenten laufen in `kube-system`.

## PersistentVolumeClaim (PVC)
Ein Pod verliert seine Daten, wenn er neu startet. Ein PVC ist ein **dauerhafter Speicher** (wie eine externe Festplatte), der an einen Pod angehängt wird.

Unsere MongoDB-Instanzen nutzen je einen PVC, damit die Datenbank-Daten bei Pod-Neustart erhalten bleiben.

## CronJob
Ein Kubernetes-Objekt, das einen Job zu **bestimmten Zeitpunkten** automatisch ausführt (wie ein Cron-Job in Linux). Unser Analytics-Job läuft stündlich.

## Rolling Update
Beim Deployment einer neuen Version: Kubernetes startet erst den **neuen Pod**, wartet bis er bereit ist, und beendet erst dann den alten. Kein Ausfall während des Updates.

```
Vorher:  [Pod v1] läuft
Während: [Pod v1] läuft + [Pod v2] startet
Nachher: [Pod v2] läuft, [Pod v1] gestoppt
```

---

# 4. Unsere Microservices

## Was ist ein Microservice?
Statt einer großen Anwendung ("Monolith") zerlegen wir das System in **kleine, unabhängige Dienste**. Jeder Service:
- hat **eine klar definierte Aufgabe**
- hat seine **eigene Datenbank**
- kommuniziert mit anderen Services über **APIs oder Events**
- kann **unabhängig deployed** und skaliert werden

## Unsere 7 Services

### customer-service
- **Aufgabe:** Kundenverwaltung
- **Datenbank:** `mongo-customer` (MongoDB)
- **Endpunkte:**
  - `POST /customers` — Kunden anlegen
  - `GET /customers/{id}` — Kunden abrufen

### driver-service
- **Aufgabe:** Fahrerverwaltung, automatische Fahrerzuweisung
- **Datenbank:** `mongo-driver` (MongoDB)
- **Endpunkte:**
  - `POST /drivers` — Fahrer anlegen
  - `GET /drivers/{id}` — Fahrer abrufen
  - `GET /drivers?status=AVAILABLE` — Verfügbare Fahrer auflisten
  - `PATCH /drivers/{id}/location` — GPS-Position aktualisieren
- **Kafka:** Hört auf `ride.created` → sucht freien Fahrer → publiziert `driver.assigned`

### ride-service
- **Aufgabe:** Fahrtbuchung, SAGA-Orchestrierung
- **Datenbank:** `mongo-ride` (MongoDB)
- **Endpunkte:**
  - `POST /rides` — Fahrt buchen
  - `GET /rides/{id}` — Fahrt abrufen
  - `POST /rides/{id}/start` — Fahrt starten
  - `POST /rides/{id}/complete` — Fahrt abschließen
- **Kafka:** Publiziert `ride.created`, hört auf `driver.assigned`, `payment.authorized`, `payment.failed`

### payment-service
- **Aufgabe:** Zahlungsabwicklung
- **Datenbank:** `mongo-payment` (MongoDB)
- **Endpunkte:**
  - `GET /payments/{ride_id}` — Zahlung zu einer Fahrt abrufen
- **Kafka:** Hört auf `payment.requested` → publiziert `payment.authorized`
- **Vereinfachung:** Zahlung schlägt niemals fehl (immer `authorized`)

### tracking-service
- **Aufgabe:** GPS-Positionstracking während einer Fahrt
- **Datenbank:** `mongo-tracking` (MongoDB)
- **Endpunkte:**
  - `POST /tracking/position` — Position melden
  - `GET /tracking/{ride_id}/latest` — Letzte bekannte Position abrufen
- **Kafka:** Publiziert `position.updated`

### analytics-service (Spark Batch Job)
- **Aufgabe:** Stündliche Auswertung aller Fahrten
- **Läuft als:** Kubernetes CronJob (kein dauerhafter Service)
- **Liest:** Fahrtdaten aus `mongo-ride`
- **Schreibt:** Ergebnisse in `mongo-analytics`
- **Spark:** Verbindet sich mit externem Spark-Cluster via Spark Connect

### analytics-api
- **Aufgabe:** Analytics-Ergebnisse abrufbar machen
- **Datenbank:** `mongo-analytics` (MongoDB, read-only)
- **Endpunkte:**
  - `GET /analytics/latest` — Neueste Auswertung
  - `GET /analytics/results` — Letzte 10 Auswertungen

---

# 5. Kommunikation zwischen Services

## Synchron (REST)
Der Aufrufer wartet auf die Antwort.

```
Client → POST /rides → ride-service → Antwort mit Fahrtdaten
```

**Vorteil:** Einfach, direktes Feedback
**Nachteil:** Enge Kopplung — wenn ride-service down ist, schlägt der Request fehl

## Asynchron (Kafka Events)
Der Sender schickt eine Nachricht und wartet **nicht** auf Antwort. Der Empfänger verarbeitet die Nachricht, wenn er bereit ist.

```
ride-service → publiziert "ride.created" → Kafka Topic
                                               ↓
                              driver-service liest "ride.created"
                              driver-service → publiziert "driver.assigned"
```

**Vorteil:** Lose Kopplung — Services sind unabhängig, fault-tolerant
**Nachteil:** Kein direktes Feedback, komplexeres Error-Handling

## Was ist Kafka?
Apache Kafka ist ein **verteilter Event-Stream**. Services können Nachrichten in sogenannte **Topics** schreiben (publish) oder daraus lesen (consume).

```
Topics in unserem System:
- ride.created
- driver.assigned
- driver.assignment.failed
- payment.requested
- payment.authorized
- payment.failed
- driver.release
- ride.started
- ride.completed
- position.updated
```

Kafka ist auf unserem Cluster vorinstalliert (Strimzi Operator). Verbindung: `my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092`

---

# 6. SAGA-Transaktion

Eine SAGA ist ein Muster für **verteilte Transaktionen** über mehrere Services hinweg. Da wir keine gemeinsame Datenbank haben, koordinieren wir Aktionen über Events.

## Ablauf (Normalfall)

```
1. Kunde: POST /rides
   → ride-service erstellt Fahrt (Status: AWAITING_DRIVER)
   → publiziert: ride.created

2. driver-service empfängt ride.created
   → findet verfügbaren Fahrer
   → setzt Fahrer auf BUSY
   → publiziert: driver.assigned

3. ride-service empfängt driver.assigned
   → Fahrt bekommt Fahrer (Status: DRIVER_ASSIGNED)
   → publiziert: payment.requested

4. payment-service empfängt payment.requested
   → erstellt Zahlungsdatensatz
   → publiziert: payment.authorized

5. ride-service empfängt payment.authorized
   → Fahrt (Status: PAYMENT_AUTHORIZED)
   → Fahrt kann gestartet werden
```

## Fehlerfall: Kein Fahrer verfügbar

```
driver-service findet keinen Fahrer
→ publiziert: driver.assignment.failed
→ ride-service setzt Fahrt auf CANCELLED
```

## Fehlerfall: Zahlung schlägt fehl (Compensating Transaction)

```
payment-service: Zahlung fehlgeschlagen
→ publiziert: payment.failed
→ ride-service: Fahrt auf CANCELLED
→ ride-service publiziert: driver.release    ← COMPENSATING TRANSACTION
→ driver-service: Fahrer wieder auf AVAILABLE
```

Die **Compensating Transaction** (`driver.release`) macht die Aktion aus Schritt 2 (Fahrerzuweisung) rückgängig — der Fahrer wird wieder freigegeben.

---

# 7. Kubernetes-Deployment unserer Services

## Struktur im Namespace `mobility`

```
Namespace: mobility
│
├── Deployments (Anwendungen):
│   ├── customer-service    ← REST API
│   ├── driver-service      ← REST API + Kafka Consumer
│   ├── ride-service        ← REST API + Kafka Consumer (SAGA)
│   ├── payment-service     ← Kafka Consumer
│   ├── tracking-service    ← REST API
│   ├── analytics-api       ← REST API (read-only)
│   ├── mongo-customer      ← MongoDB
│   ├── mongo-driver        ← MongoDB
│   ├── mongo-ride          ← MongoDB
│   ├── mongo-payment       ← MongoDB
│   ├── mongo-tracking      ← MongoDB
│   └── mongo-analytics     ← MongoDB
│
├── CronJobs:
│   └── analytics-job       ← Spark Batch (stündlich)
│
├── Services (Networking):
│   ├── customer-service → Port 80 → Pod Port 8000
│   ├── driver-service   → Port 80 → Pod Port 8000
│   └── ... (je einen pro Deployment)
│
├── PersistentVolumeClaims (Speicher):
│   ├── mongo-ride-pvc      (2Gi)
│   ├── mongo-customer-pvc  (1Gi)
│   └── ... (je einen pro MongoDB)
│
├── HTTPRoutes (Gateway/Routing):
│   ├── /rides      → ride-service
│   ├── /customers  → customer-service
│   ├── /drivers    → driver-service
│   ├── /payments   → payment-service
│   ├── /tracking   → tracking-service
│   ├── /analytics  → analytics-api
│   └── /dashboard  → dashboard (nginx)
│
└── Secrets:
    └── spark-credentials   ← Spark Connect Token
```

## Wie kommen Requests von außen rein?

```
Internet/Client
     ↓
Traefik Gateway (Port 8000 am Node)
     ↓ (HTTPRoute: /rides → ride-service)
Kubernetes Service "ride-service" (Port 80)
     ↓
Pod: ride-service (Port 8000)
     ↓
FastAPI Anwendung
```

Da Port 8000 von außen geblockt ist, nutzen wir Port-Forward:
```bash
kubectl port-forward -n kube-system svc/traefik 8080:80
# Dann: http://localhost:8080/rides/docs
```

---

# 8. Big Data Analytics

## Architektur

```
mongo-ride (Fahrtdaten)
     ↓ (pymongo liest alle Fahrten)
analytics-service (Kubernetes CronJob, stündlich)
     ↓ (Spark Connect über gRPC)
Externer Spark Cluster (10.3.15.18:15012)
     ↓ (Berechnungen: count, avg, groupBy)
analytics-service (schreibt Ergebnis)
     ↓ (pymongo schreibt)
mongo-analytics (Ergebnisse)
     ↓ (REST API)
analytics-api → GET /analytics/latest
```

## Was berechnet Spark?

```python
total_rides = rides_df.count()
completed_rides = rides_df.filter(col("status") == "COMPLETED").count()
avg_price = rides_df.agg(avg("price_eur")).collect()[0][0]
avg_distance = rides_df.agg(avg("distance_km")).collect()[0][0]
status_counts = rides_df.groupBy("status").agg(count("*")).collect()
```

## Spark Connect
Normalerweise braucht PySpark lokal Java und die gesamte Spark-Runtime (~1GB). Mit **Spark Connect** verbindet sich der Client per gRPC mit einem entfernten Spark-Server — kein lokales Java nötig, schlankes Container-Image (~200MB).

---

# 9. Nützliche Befehle

```bash
# Cluster-Zugriff (kubeconfig global gesetzt)
kubectl get pods -n mobility           # Alle Pods anzeigen
kubectl get deployments -n mobility    # Alle Deployments
kubectl get services -n mobility       # Alle Services
kubectl logs <pod-name> -n mobility    # Logs eines Pods
kubectl describe pod <pod-name> -n mobility  # Details zu Pod

# Port-Forward (Zugriff auf Services)
kubectl port-forward -n kube-system svc/traefik 8080:80

# Rolling Update manuell auslösen
kubectl rollout restart deployment/ride-service -n mobility

# Analytics-Job manuell starten
kubectl create job --from=cronjob/analytics-job test-run -n mobility

# Node-Status
kubectl describe nodes
```

---

# 10. Image-Verwaltung (GHCR)

Unsere Docker-Images liegen auf GitHub Container Registry:
`ghcr.io/kektri/cloudcomputing/<service-name>:latest`

Workflow:
```bash
# 1. Image bauen
docker build --network=host -t ghcr.io/kektri/cloudcomputing/ride-service:latest services/ride-service/

# 2. Image pushen
docker push ghcr.io/kektri/cloudcomputing/ride-service:latest

# 3. Kubernetes zieht neues Image beim nächsten Rollout
kubectl rollout restart deployment/ride-service -n mobility
```

---

# 11. Bekannte Probleme & Lösungen

| Problem | Ursache | Lösung |
|---------|---------|--------|
| Disk Pressure | Große Images (PySpark JARs) füllen Node | JARs nach pip install löschen, `crictl rmi --prune` |
| OOM (Out of Memory) | MongoDB ohne Memory-Limit | `--wiredTigerCacheSizeGB 0.1` + Kubernetes Memory-Limits |
| Pods bleiben Pending | Disk/Memory Pressure Taint auf Node | Node bereinigen, warten bis Taint wegfällt |
| Kafka nicht erreichbar | Bootstrap-Server falsch konfiguriert | `my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092` |
| Cluster nicht erreichbar | VPN nicht aktiv oder Node down | VPN prüfen, Supervisor kontaktieren |
