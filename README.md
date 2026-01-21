# 🚀 DevOps Homelab: Meme-as-a-Service on Kubernetes

<p align="center">
  <img src="https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white" alt="Terraform" />
  <img src="https://img.shields.io/badge/Ansible-EE0000?style=for-the-badge&logo=ansible&logoColor=white" alt="Ansible" />
  <img src="https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white" alt="Kubernetes" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/Proxmox-E57000?style=for-the-badge&logo=proxmox&logoColor=white" alt="Proxmox" />
</p>

> **Philosophy:** Infrastructure that behaves like **production**, not a demo. No managed services. No hidden automation. Full control.

## 📖 Context

This project is a journey to build a complete platform from bare metal (virtualized) to a distributed microservices application. The goal was to establish a solid foundation using **Infrastructure as Code (IaC)** before touching any application logic.

The end result is a **Meme-as-a-Service** platform running on a self-bootstrapped Kubernetes cluster.

---

## 🗺️ Project Roadmap & Engineering Log

### 🚀 Step 1: Infrastructure Foundation
**Stack:** Terraform × Proxmox

The goal was to make `terraform apply` produce a usable VM every time, eliminating UI-driven configuration.

#### 🧱 What Was Built
* **Proxmox:** Custom Ubuntu cloud-init template (SeaBIOS, virtio).
* **Terraform:** Single source of truth. Defined CPU, RAM, static IPs, and SSH keys in code.

#### ⚠️ Challenges & Solutions
| Issue | Symptom | Root Cause & Fix |
|-------|---------|------------------|
| **Hanging Creation** | Terraform waits indefinitely. | **Missing QEMU Agent.** <br>✅ Fixed by enabling agent in Proxmox and Template. |
| **Boot Failure** | Drops to PXE, `Boot failed: could not read the boot disk`. | **Provider Bug.** Disk attached as `unused0`. <br>✅ Fixed by provider configuration adjustments. |
| **Instability** | Provider crashes, inconsistent state. | **Tool Reliability.** <br>🧠 **Decision:** Switched Terraform provider implementation for stability. |

> **Key Takeaway:** Infrastructure as Code does not hide platform behavior — it reveals it.

---

### ⚙️ Step 2: Configuration & K8s Bootstrap
**Stack:** Terraform × Ansible × Kubernetes

Turning raw compute into a cluster without manual SSH access ("Zero-Touch Deployment").

#### 🧱 What Was Built
* **Dynamic Inventory:** Terraform generates `inventory.ini` for Ansible automatically.
* **OS Prep:** Ansible disables SWAP, loads kernel modules (`overlay`, `br_netfilter`), installs `containerd`.
* **Cluster Lifecycle:** Automated `kubeadm init`, CNI (Flannel) installation, and worker joining.

#### ⚠️ Challenges & Solutions
* **SSH Failure:** One node refused connection due to an **IP conflict** with an IoT device on the home network.
    * *Fix:* Moved cluster to a dedicated IP range.
* **Zombie CNI Config:** Pods stuck in `ContainerCreating` after reset.
    * *Fix:* Added explicit cleanup of `cni0` interfaces in Ansible reset playbook.

> **Outcome:** `terraform apply` + `ansible-playbook` = Ready-to-use Kubernetes Cluster.

---

### 🧩 Step 3: Platform Networking
**Stack:** MetalLB × Nginx Ingress

Adding the minimal platform services required for real traffic flow.

#### 🛠 Implementation
1.  **MetalLB (Layer 2):** Provides a virtual IP address (VIP) inside the local network to expose `LoadBalancer` services.
2.  **Ingress NGINX:** Acts as the single entry point, routing HTTP traffic based on hostnames.

#### ✅ Verification
* External Traffic → VIP → Ingress → Service → Pod.
* No manual port forwarding or SSH tunneling required.

---

### 🎨 Step 4: Application Layer (MVP)
**Stack:** Python (FastAPI) × RabbitMQ × MinIO × Docker Compose

Transitioning from infrastructure to a deployable, testable microservice system: **Meme-as-a-Service**.

#### 🏗 Architecture
* **Frontend:** Nginx serving static assets.
* **API:** FastAPI handling requests.
* **Message Broker:** RabbitMQ for decoupling generation tasks.
* **Worker:** Python + Pillow for image processing (smart text wrapping implemented).
* **Storage:** MinIO (S3-compatible) for persisting generated memes.

#### 🧠 Key Engineering Features
* **Auto-Configuration:** Worker automatically initializes MinIO buckets and policies on startup.
* **Resilience:** Services implement retry logic (Self-healing) waiting for RabbitMQ/MinIO readiness.
* **Load Testing:** Custom `stress_test.py` validates the full pipeline under concurrency.

---

### 🚢 Step 5: Kubernetes Migration, CI/CD & GitOps
**Stack:** GitHub Actions × ArgoCD × HPA × K8s Manifests

The "Big Migration." Moving the application from local Docker Compose to a production-grade Kubernetes environment, establishing a full automated pipeline, and proving resilience via stress testing.

#### 🧱 What Was Built
* **CI/CD Pipeline:** GitHub Actions automatically builds and tags Docker images on every push to `master`, pushing them to Docker Hub.
* **GitOps (ArgoCD):** The cluster state is synchronized with the Git repository. No manual `kubectl apply` for application logic.
* **Autoscaling (HPA):** Configured HorizontalPodAutoscaler and metrics-server. The API scales from 1 to 5 pods based on CPU load.
* **Storage Strategy:** Implemented `local-path-provisioner` storage class to allow StatefulSets (Postgres, MinIO, RabbitMQ) to bind to bare-metal disk storage.

#### 🔥 Disaster Recovery (DR) Test
To verify the robustness of the setup, a full Disaster Recovery simulation was performed:

1.  **Action:** `kubectl delete namespace meme-app` (Total destruction of the environment).
2.  **Recovery:** Re-applied infrastructure secrets (`regcred`, `app-secrets`) and StorageClasses manually.
3.  **Result:** ArgoCD detected the missing state and automatically redeployed the entire stack. The system returned to full functionality within minutes.

#### ⚠️ Challenges & Solutions
| Issue | Symptom | Root Cause & Fix |
|-------|---------|------------------|
| **Pending PVCs** | DBs stuck in `Pending` state. | **Missing StorageClass.** Bare metal K8s doesn't have a default provisioner. <br>✅ Fixed by installing `rancher.io/local-path`. |
| **CI/CD Failure** | GitHub Action failed on git push. | **Branch Mismatch.** Workflow tried pushing to `main`, repo used `master`. <br>✅ Fixed workflow config. |
| **HPA Unknown** | HPA showed `<unknown>/50%`. | **TLS Error.** Metrics Server couldn't talk to Kubelet. <br>✅ Fixed by adding `--kubelet-insecure-tls`. |

> **Key Takeaway:** Automation is great, but understanding the "manual" foundational layers (Secrets, Storage, Networking) is critical for recovery.

---

### 🛡️ Step 6: Observability, Guardrails & "Production-Grade" Stability
**Stack:** Prometheus × Grafana × Loki × Alertmanager × Telegram

The final boss: ensuring the cluster survives heavy load and tells me when it hurts. Transitioning from "it works" to "it stays up."

#### 🧱 What Was Built
* **PLG Stack (Prometheus, Loki, Grafana):** Full visibility into metrics and logs. No more grepping `kubectl logs` across multiple pods.
* **Alerting Pipeline:** Configured Alertmanager to send critical notifications (High CPU, CrashLoops, Log Errors) directly to Telegram.
* **Resource Guardrails:** Implemented strict `requests` and `limits` for all microservices. A rogue pod gets throttled (0.1 CPU cap), preventing it from starving the Node.
* **Probes Tuning:** Optimized `liveness` and `readiness` probes to handle slow startups under strict CPU throttling without triggering false-positive restarts.

#### 🔥 The Survival Test (Load Testing)
I ran a custom Python DDoS script generating concurrent traffic to the API (20+ concurrent users).

**Outcome:**
1.  **Scaling:** HPA detected the spike and scaled API replicas from **1 → 15**.
2.  **Stability:** Resource Limits held firm. The API slowed down, but the Nodes remained **Ready**.
3.  **Resilience:** Critical Services (Postgres, RabbitMQ, MinIO) experienced **0 restarts** and **0 downtime**.
4.  **Observability:** Grafana fired alerts to Telegram instantly. Once load stopped, the cluster scaled back down.

#### ⚠️ Challenges & Solutions
| Issue | Symptom | Root Cause & Fix |
|-------|---------|------------------|
| **Node Death** | Nodes went `NotReady`, SSH died during load test. | **Resource Exhaustion.** No limits set. <br>✅ Fixed by implementing strict `resources: limits` in Helm/Kustomize. |
| **Death Spiral** | Pods stuck in `CrashLoopBackOff` under load. | **Probe Timeout.** 0.1 CPU limit made startup slow (>10s). <br>✅ Fixed by increasing `initialDelaySeconds` to 60s. |

> **Key Takeaway:** Observability isn't just looking at graphs; it's about trusting the system to heal itself under pressure without human intervention.