# Deploy-Anleitung – Was noch zu tun ist

Alle Befehle aus dem Projektverzeichnis ausführen:
```bash
cd /home/kek/Documents/dh/CcProjekt/CloudComputing
```

---

## Schritt 1: Images bauen und pushen

### 1a. Geänderte Services (Code wurde bereinigt)
```bash
docker build --network=host -t ghcr.io/kektri/cloudcomputing/customer-service:latest services/customer-service/
docker build --network=host -t ghcr.io/kektri/cloudcomputing/driver-service:latest services/driver-service/
docker build --network=host -t ghcr.io/kektri/cloudcomputing/payment-service:latest services/payment-service/
docker build --network=host -t ghcr.io/kektri/cloudcomputing/tracking-service:latest services/tracking-service/

docker push ghcr.io/kektri/cloudcomputing/customer-service:latest
docker push ghcr.io/kektri/cloudcomputing/driver-service:latest
docker push ghcr.io/kektri/cloudcomputing/payment-service:latest
docker push ghcr.io/kektri/cloudcomputing/tracking-service:latest
```

### 1b. Analytics-Service (Dockerfile geändert: Java + JARs entfernt)
```bash
docker build --network=host -t ghcr.io/kektri/cloudcomputing/analytics-service:latest services/analytics-service/
docker push ghcr.io/kektri/cloudcomputing/analytics-service:latest
```

### 1c. Analytics-API (neuer Service, noch nie gepusht)
```bash
docker build --network=host -t ghcr.io/kektri/cloudcomputing/analytics-api:latest services/analytics-api/
docker push ghcr.io/kektri/cloudcomputing/analytics-api:latest
```

> ride-service muss NICHT neu gebaut werden (keine Code-Änderungen).

---

## Schritt 2: Kubernetes-Manifeste anwenden

```bash
kubectl apply -f k8s/spark-secret.yaml
kubectl apply -f k8s/ride-service.yaml
kubectl apply -f k8s/customer-service.yaml
kubectl apply -f k8s/driver-service.yaml
kubectl apply -f k8s/payment-service.yaml
kubectl apply -f k8s/tracking-service.yaml
kubectl apply -f k8s/analytics-cronjob.yaml
```

---

## Schritt 3: Analytics aktivieren

Analytics-API hochskalieren und CronJob fortsetzen (beides war wegen Disk-Problemen deaktiviert):
```bash
kubectl scale deployment analytics-api -n mobility --replicas=1
kubectl patch cronjob analytics-job -n mobility -p '{"spec":{"suspend":false}}'
```

---

## Schritt 4: Prüfen ob alles läuft

```bash
kubectl get pods -n mobility
```

Erwartetes Ergebnis: alle Pods `Running` (außer analytics-job, der läuft nur stündlich).

---

## Schritt 5: Analytics-Job einmal manuell triggern (für Screenshot)

```bash
kubectl create job --from=cronjob/analytics-job analytics-manual-1 -n mobility
kubectl logs -n mobility -l job-name=analytics-manual-1 -f
```

---

## Schritt 6: Screenshots für Präsentation und README

```bash
# Für Folie 8 + README
kubectl get deployments -n mobility
kubectl get pods -n mobility
kubectl get services -n mobility

# Alles auf einmal (alle Namespaces):
kubectl get deployments,pods,services -A
```

Outputs kopieren / Screenshot machen.

---

## Schritt 7: Screen-Recording Rolling Update (~30s)

Zwei Terminals öffnen:

**Terminal 1** (beobachten):
```bash
kubectl get pods -n mobility -w
```

**Terminal 2** (auslösen):
```bash
kubectl rollout restart deployment/ride-service -n mobility
```

Recording starten bevor Terminal 2 ausgeführt wird.

---

## Schritt 8: Analytics-Ergebnis für Screenshot

Sobald analytics-manual-1 durch ist:
```bash
kubectl port-forward -n kube-system svc/traefik 8080:80
curl http://localhost:8080/analytics/latest | python3 -m json.tool
```

Output als Screenshot für Folie 14 + README.
