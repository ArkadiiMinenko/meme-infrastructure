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

## 🔮 Future Steps

* [ ] Migrate Docker Compose services to Kubernetes Helm Charts.
* [ ] Implement GitOps (ArgoCD) for continuous delivery.
* [ ] Set up monitoring (Prometheus/Grafana).

---