# Kubernetes quickstart

Prerequisites: Docker, kubectl, and a Kubernetes cluster with a default StorageClass.
The examples below use a local **kind** cluster. They create a namespace, a 1 GiB
persistent volume claim, one Pod containing the checker and dashboard, and an
internal dashboard Service.

## 1. Build and load the image

Run from the repository root:

```bash
docker build -t api-health-checker:local .
kind create cluster --name api-monitor
kind load docker-image api-health-checker:local --name api-monitor
kubectl config current-context
```

The expected context is `kind-api-monitor`. If you already created this cluster,
skip `kind create cluster`. For another cluster, push the image to a registry it
can access and change `images.newName` and `images.newTag` in `kustomization.yaml`.
Use a unique image tag for each release.

## 2. Configure and deploy

Edit `k8s/endpoints.json` for your endpoints and the interval/timeout literals in
`k8s/kustomization.yaml`. Endpoint authentication refers to environment-variable
names; keep actual credentials out of these files.

```bash
kubectl apply -k k8s
kubectl -n api-monitor rollout status deployment/api-health-checker --timeout=120s
kubectl -n api-monitor get pods,pvc,svc
```

Optional email/API credentials: put the environment values into an ignored local
`.env` file, then create the Secret (do not commit that file):

```bash
kubectl -n api-monitor create secret generic monitoring-secrets --from-env-file=.env
kubectl -n api-monitor rollout restart deployment/api-health-checker
```

For checker email delivery, include `BREVO_API_KEY`, `ALERT_SENDER_EMAIL` and
`ALERT_RECIPIENT_EMAIL` in that file. Use a Brevo-verified sender address.
The checker receives this optional Secret; the dashboard does not. Without an
email key, monitoring works but email notifications cannot be delivered.

## 3. Open the dashboard

```bash
kubectl -n api-monitor port-forward service/dashboard 8080:8000
```

Keep that terminal open and visit **http://127.0.0.1:8080**. Wait for the checker's
first cycle, then refresh. Port-forwarding stops when the command ends or its Pod
is replaced; restart it after a deployment update.

## Troubleshooting

```bash
kubectl -n api-monitor logs deployment/api-health-checker -c checker --tail=100
kubectl -n api-monitor logs deployment/api-health-checker -c dashboard --tail=100
kubectl -n api-monitor describe pods
kubectl -n api-monitor describe pvc monitoring-data
```

- `ImagePullBackOff`: load the image into kind or configure a reachable registry.
- PVC `Pending`: ensure the cluster has a default StorageClass, or set
  `storageClassName` in `storage.yaml` to an available one.
- No monitoring data: inspect checker logs and endpoint configuration.
- After endpoint/config changes, apply again. Kustomize generates a new ConfigMap
  name and updates the Pod automatically. Secret changes require a rollout restart.

Keep **one replica**. The file-based checker needs one writer; both containers
share the same PVC within one Pod. `Recreate` prevents overlapping writers during
an update, at the cost of brief dashboard downtime. Readiness/liveness checks test
the dashboard server, not the availability of monitored third-party APIs.
History, report files, failure counters, and logs survive Pod replacement.
The PVC requests 1 GiB; CSV history grows indefinitely, so monitor disk usage and
archive older history as needed.

These are local learning manifests: the Service is internal, with no Ingress or
public URL. Deleting the namespace or kind cluster may delete the stored data;
back up history before removing either.
