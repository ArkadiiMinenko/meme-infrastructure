#!/bin/bash

set -e

echo "Starting Kubernetes cluster setup..."

export ANSIBLE_HOST_KEY_CHECKING=False

echo "1. Installing dependencies and preparing nodes..."
ansible-playbook -i inventory.ini k8s-prep.yml

echo "2. Initializing cluster..."
ansible-playbook -i inventory.ini k8s-cluster.yml

echo "3. Installing addons (MetalLB, Ingress)..."
ansible-playbook -i inventory.ini k8s-addons.yml

echo "4. Configuring local kubectl..."
mkdir -p ~/.kube
scp -o StrictHostKeyChecking=no -i tf-key ubuntu@192.168.0.61:~/.kube/config ~/.kube/config

echo "Done. Cluster is ready."
kubectl get nodes