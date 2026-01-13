terraform {
  required_providers {
    proxmox = {
      source = "bpg/proxmox"
      version = "0.46.1"
    }
  }
}

variable "proxmox_api_url" { 
  type = string 
}

variable "proxmox_api_token_id" { 
  type = string 
}

variable "proxmox_api_token_secret" { 
  type = string
  sensitive = true
}

provider "proxmox" {
  endpoint = var.proxmox_api_url
  api_token = "${var.proxmox_api_token_id}=${var.proxmox_api_token_secret}"
  insecure = true
  
  ssh {
    agent = true
    
  }
}